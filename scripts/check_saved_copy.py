"""Qualify saved-copy numerical/content fidelity without writing original data."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time
import h5py
import numpy as np
from tofscope.api.app import build_services
from tofscope.application.commands import CommandEnvelope
from tofscope.application.jobs import IntegrationSpec
from tofscope.config import Settings


def digest_file(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(8 * 1024**2): value.update(chunk)
    return value.hexdigest()


def normalized(value):
    if isinstance(value, np.ndarray):
        return dict(dtype=str(value.dtype), shape=value.shape,
                    data=value.tobytes().hex() if not value.dtype.hasobject else normalized(value.tolist()))
    if isinstance(value, np.generic): return normalized(value.item())
    if isinstance(value, bytes): return {'bytes': value.hex()}
    if isinstance(value, (list, tuple)): return [normalized(v) for v in value]
    return value


def vendor_digest(path):
    digest = hashlib.sha256()
    count = 0
    def add(value): digest.update(json.dumps(normalized(value), sort_keys=True, default=str).encode())
    with h5py.File(path, 'r') as h:
        def visit(name, item):
            nonlocal count
            if name == 'ToFScope' or name.startswith('ToFScope/'): return
            add([name, sorted((key, normalized(value)) for key, value in item.attrs.items())])
            if isinstance(item, h5py.Dataset):
                add([item.shape, str(item.dtype), item.chunks, item.compression, item.fillvalue])
                if item.chunks:
                    def chunk(info):
                        nonlocal count
                        mask, content = item.id.read_direct_chunk(info.chunk_offset)
                        add([info.chunk_offset, mask]); digest.update(content); count += 1
                    item.id.chunk_iter(chunk)
                elif item.ndim:
                    for i in range(item.shape[0]): add(item[i])
                else: add(item[()])
        visit('', h)
        h.visititems(visit)
    return digest.hexdigest(), count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.file.resolve()
    identity = source.stat()
    before_hash = digest_file(source)
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='tofscope-save-qualification-') as scratch:
        root = Path(scratch)
        config = Settings(source.parent, runtime_dir=root / 'runtime', output_root=root / 'saved')
        services = build_services(config)
        high_water = [0]
        reserve = services.cache.budget.reserve
        def measured_reserve(*args, **kwargs):
            allocation = reserve(*args, **kwargs)
            high_water[0] = max(high_water[0], services.cache.budget.physical_bytes)
            return allocation
        services.cache.budget.reserve = measured_reserve
        def shutdown(s):
            s.analyses.close_all(); s.jobs.shutdown(); s.cache.clear()
        try:
            state = services.analyses.create_analysis('qualified', services.repository.open('qualified', source.name))
            independent = services.analyses.create_analysis('other-owner', services.repository.open('other-owner', source.name))
            from unittest.mock import patch
            from threading import Event
            with services.cache.load('other-owner', independent.id, independent.dataset, independent.signals[0].recipe) as lease:
                assert lease.array.shape[0] == state.shape[0]
            try:
                services.analyses.get('qualified', independent.id)
                raise AssertionError('Foreign analysis was accessible')
            except KeyError: pass
            def command(payload):
                nonlocal state
                state = services.explore.apply('qualified', state.id, CommandEnvelope(str(state.revision), state.revision, state.dataset.generation, payload))
            envelope = CommandEnvelope('raw', state.revision, state.dataset.generation, {'type': 'set_depth', 'depth': {'mode': 'all'}})
            t = time.perf_counter()
            job = services.jobs.submit('qualified', state.id, envelope, IntegrationSpec(((26.5, 27.5), (47.5, 48.5)), (0, state.shape[0] - 1), 'Saved union'))
            outcome = services.jobs.wait('qualified', job.id, 180)
            assert outcome.status == 'succeeded', outcome
            integration_seconds = time.perf_counter() - t
            state = services.analyses.get('qualified', state.id)
            row = state.signals[-1]
            command({'type': 'select_image_signal', 'signal_id': row.id})
            command({'type': 'set_profile_visible', 'signal_id': state.signals[0].id, 'visible': False})
            command({'type': 'set_roi', 'roi': [1, state.shape[2] - 2, 1, state.shape[1] - 2]})
            with services.cache.load('qualified', state.id, state.dataset, row.recipe) as lease:
                expected = np.array(lease.array, copy=True)
            expected_csv = services.exports.render('qualified', state.id, 'csv').content
            envelope = CommandEnvelope('save', state.revision, state.dataset.generation, {'type': 'set_depth', 'depth': {'mode': 'all'}})
            t = time.perf_counter()
            saved = services.saves.submit('qualified', state.id, envelope, 'qualified.h5')
            saved = services.jobs.wait('qualified', saved.id, 180)
            assert saved.status == 'succeeded', saved
            save_seconds = time.perf_counter() - t
            assert services.analyses.get('other-owner', independent.id).revision == independent.revision
            entered, release = Event(), Event()
            original_verify = services.saves.files._verify
            def paused_verify(*args):
                entered.set()
                assert release.wait(30)
                return original_verify(*args)
            try:
                with patch.object(services.saves.files, '_verify', side_effect=paused_verify):
                    cancel_env = CommandEnvelope('cancel-save', state.revision, state.dataset.generation, {'type': 'set_depth', 'depth': {'mode': 'all'}})
                    cancelled = services.saves.submit('qualified', state.id, cancel_env, 'cancelled.h5')
                    assert entered.wait(60)
                    services.jobs.cancel('qualified', cancelled.id)
                    release.set()
                    assert services.jobs.wait('qualified', cancelled.id, 60).status == 'cancelled'
            finally: release.set()
            assert [f.name for f in services.saves.files.list('qualified')] == ['qualified.h5']
            assert services.saves.files.list('other-owner') == []
            assert high_water[0] <= config.global_bytes
            path = services.saves.files.path('qualified', saved.saved_file.id)
            vendor_original, chunks = vendor_digest(source)
            vendor_copy, copy_chunks = vendor_digest(path)
            assert (vendor_original, chunks) == (vendor_copy, copy_chunks)
            stored_bytes = path.stat().st_size
            portable = root / 'portable'; portable.mkdir()
            shutil.move(path, portable / 'moved.h5')
            shutdown(services)
            restored_services = build_services(Settings(portable, runtime_dir=root / 'runtime-new', output_root=root / 'saved-new'))
            try:
                from unittest.mock import patch
                with patch('tofscope.storage.acquisitions.custom_peak_windows', side_effect=AssertionError('Restore must not reintegrate')):
                    restored = restored_services.analyses.create_analysis('new-owner', restored_services.repository.open('new-owner', 'moved.h5'))
                    restored_row = restored.signals[-1]
                    with restored_services.cache.load('new-owner', restored.id, restored.dataset, restored_row.recipe, materialization_id=restored_row.materialization_id) as actual:
                        np.testing.assert_array_equal(actual.array, expected)
                    assert restored_services.exports.render('new-owner', restored.id, 'csv').content == expected_csv
                    assert len(restored.signals) == 2 and len(restored.profile_signal_ids) == 1
                    assert restored.saved_revision == restored.revision
                    assert restored.roi == state.roi and restored.display == state.display
                    raw_hash = hashlib.sha256(expected.tobytes()).hexdigest()
            finally: shutdown(restored_services)
        finally: shutdown(services)
    after = source.stat()
    assert (identity.st_ino, identity.st_size, identity.st_mtime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns)
    assert digest_file(source) == before_hash
    result = dict(source=source.name, source_bytes=identity.st_size, shape=state.shape,
        original_sha256=before_hash, original_unchanged=True, vendor_chunk_count=chunks,
        vendor_payload_sha256=vendor_original, vendor_payloads_exact=True,
        custom_volume_sha256=raw_hash, custom_values_exact=True, exact_restored_csv=True,
        hidden_signals_restored=True, fresh_owner_and_moved_copy=True, restore_without_reintegration=True,
        two_owners_independent=True, cancelled_save_not_published=True, managed_bytes_high_water=high_water[0], managed_bytes_limit=config.global_bytes,
        integration_seconds=integration_seconds, save_seconds=save_seconds, saved_bytes=stored_bytes,
        elapsed_seconds=time.perf_counter() - started,
        limitations=['Filesystem/NFS crash durability not qualified.', 'Commercial software round trip not tested.', 'Real original remains in place; literal source removal is covered by disposable installed-package checks.'])
    (args.output / 'saved-copy.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__': main()
