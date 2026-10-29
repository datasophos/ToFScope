"""Private, self-contained saved copies with bounded copying and exclusive publication."""
import base64
from contextlib import contextmanager, ExitStack
from dataclasses import dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
from threading import RLock
from uuid import uuid4

import h5py
import numpy as np

from tofscope import __version__
from tofscope.storage.acquisitions import AcquisitionRepository, content_identity
from tofscope.storage.analysis_document import ROOT, MAX_DOCUMENT_BYTES, read_document
from tofscope.storage.integration_store import IntegrationRecord, write_integration_group, _read_info

COPY_BYTES = 8 * 1024**2
_disk_lock = RLock()
_disk_reservations = {}


@dataclass(frozen=True)
class SavedFile:
    id: str
    name: str
    size: int
    compatibility_warnings: tuple[str, ...] = ()


def filename(value):
    if not isinstance(value, str) or not value or value.startswith('.') or any(x in value for x in ('/', '\\', '\x00')) or not value.endswith('.h5') or len(value.encode('utf-8')) > 240 or any(ord(c) < 32 for c in value):
        raise ValueError('Choose a plain .h5 filename without directory components.')
    return value


def file_id(name):
    return base64.urlsafe_b64encode(name.encode()).decode().rstrip('=')


@contextmanager
def reserve_disk(path, size):
    key = path.stat().st_dev
    with _disk_lock:
        held = _disk_reservations.get(key, 0)
        if shutil.disk_usage(path).free - held < size:
            raise OSError('Not enough free space for a complete saved copy.')
        _disk_reservations[key] = held + size
    try:
        yield
    finally:
        with _disk_lock:
            _disk_reservations[key] -= size


class SavedFileStore:
    def __init__(self, settings):
        self.settings = settings
        self.root = settings.output_root

    def owner_path(self, owner):
        if not isinstance(owner, str) or not owner:
            raise PermissionError('An authenticated owner is required.')
        # Local mode authenticates one operating-system user. Its visible save
        # folder is the physical destination; hosted identities remain isolated.
        if self.settings.mode == 'local' and owner == 'local':
            return self.root
        return self.root / hashlib.sha256(owner.encode()).hexdigest()

    def owner_root(self, owner):
        path = self.owner_path(owner)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink():
            raise ValueError('Saved-file directory cannot be a symbolic link.')
        path.mkdir(exist_ok=True, mode=0o700)
        return path

    def directory(self, owner, directory='', location='saved', *, writable=False):
        if location == 'acquisition':
            if self.settings.mode != 'local' or owner != 'local':
                raise ValueError('Save within your saved-files folder.')
            root = self.settings.data_root
        elif location == 'saved':
            root = self.owner_root(owner)
        else:
            raise ValueError('Unknown save location.')
        if not isinstance(directory, str) or '\x00' in directory or '\\' in directory:
            raise ValueError('Choose a folder within the configured location.')
        relative = Path(directory)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Choose a folder within the configured location.')
        target = root
        for part in relative.parts:
            target = target / part
            if target.is_symlink():
                raise ValueError('Save folders cannot be symbolic links.')
        target = target.resolve()
        if not target.is_relative_to(root):
            raise ValueError('Save folder is outside the configured location.')
        if not target.is_dir():
            raise FileNotFoundError('Save folder is unavailable.')
        if writable and not os.access(target, os.W_OK | os.X_OK):
            raise PermissionError('The server cannot write to this folder.')
        return target

    def identifier(self, owner, target):
        root = self.owner_root(owner)
        if target.is_relative_to(root):
            return file_id(target.relative_to(root).as_posix())
        if self.settings.mode == 'local' and owner == 'local' and target.is_relative_to(self.settings.data_root):
            return file_id(str(target))
        raise ValueError('File must stay within a configured save location.')

    def path(self, owner, identifier):
        try:
            decoded = base64.urlsafe_b64decode(identifier + '=' * (-len(identifier) % 4)).decode()
            if file_id(decoded) != identifier:
                raise ValueError('Invalid saved file ID.')
            name = Path(decoded)
            filename(name.name)
            if name.is_absolute():
                if self.settings.mode != 'local' or owner != 'local' or not name.is_relative_to(self.settings.data_root):
                    raise ValueError('Invalid saved file ID.')
                parent = self.directory(owner, str(name.parent.relative_to(self.settings.data_root)), 'acquisition')
            else:
                parent = self.directory(owner, str(name.parent))
            target = parent / name.name
        except (ValueError, UnicodeError, TypeError) as exc:
            raise ValueError('Invalid saved file ID.') from exc
        if target.is_symlink() or not target.is_file():
            raise FileNotFoundError('Saved file unavailable.')
        return target

    def browse(self, owner, directory='', location='saved', *, query='', offset=0, limit=100, folders_only=False):
        if len(query) > 256 or offset < 0 or not 1 <= limit <= 100:
            raise ValueError('Invalid folder listing limits.')
        target = self.directory(owner, directory, location)
        root = self.settings.data_root if location == 'acquisition' else self.owner_root(owner)
        entries = []
        for child in target.iterdir():
            if child.name.startswith('.') or query.casefold() not in child.name.casefold() or child.is_symlink():
                continue
            try:
                if child.is_dir():
                    entries.append(dict(name=child.name, path=child.relative_to(root).as_posix(), kind='directory', size=0))
                elif not folders_only and child.is_file() and child.suffix == '.h5':
                    entries.append(dict(name=child.name, path=self.identifier(owner, child), kind='file', size=child.stat().st_size))
            except OSError:
                continue
        entries.sort(key=lambda row: (row['kind'] != 'directory', row['name'].casefold(), row['name']))
        relative = target.relative_to(root).as_posix()
        relative = '' if relative == '.' else relative
        parent = str(Path(relative).parent) if relative else None
        return dict(path=relative, full_path=str(target), parent='' if parent == '.' else parent,
                    entries=entries[offset:offset + limit], total=len(entries),
                    next_offset=offset + limit if offset + limit < len(entries) else None)

    def create_directory(self, owner, directory, location, name):
        if not name or name.startswith('.') or len(name.encode()) > 240 or any(c in name for c in ('/', '\\', '\x00')) or any(ord(c) < 32 for c in name):
            raise ValueError('Choose a plain folder name.')
        parent = self.directory(owner, directory, location, writable=True)
        try:
            (parent / name).mkdir(mode=0o700)
        except FileExistsError:
            raise ValueError('A file or folder with that name already exists. Choose another name.') from None
        root = self.settings.data_root if location == 'acquisition' else self.owner_root(owner)
        return dict(path=(parent / name).relative_to(root).as_posix())

    def list(self, owner):
        return [SavedFile(file_id(p.name), p.name, p.stat().st_size)
                for p in sorted(self.owner_root(owner).iterdir())
                if not p.name.startswith('.') and p.suffix == '.h5' and p.is_file() and not p.is_symlink()]

    def publish_copy(self, owner, source, document, frames, name, cancel, progress, before_publish, directory='', destination_location='saved'):
        name = filename(name)
        directory = self.directory(owner, directory, destination_location, writable=True)
        destination = directory / name
        if os.path.lexists(destination):
            raise FileExistsError('Output already exists; choose a new name.')
        source = Path(source)
        initial = source.stat()
        source_identity = content_identity(initial)
        def check():
            if cancel.is_set():
                raise ValueError('Save cancelled.')
            now = source.stat()
            if content_identity(now) != source_identity:
                raise ValueError('Source changed while saving.')
        check()
        previous_stale = ()
        with h5py.File(source, 'r') as handle:
            AcquisitionRepository.validate_layout(handle)
            report_path = 'ToFScope/Analysis/native_export_json'
            if report_path in handle:
                try:
                    report = handle[report_path]
                    if not isinstance(report, h5py.Dataset) or report.ndim != 1 or report.dtype != np.uint8 or report.size > MAX_DOCUMENT_BYTES:
                        raise ValueError('Invalid report encoding.')
                    stored = json.loads(report[:].tobytes())
                    entries = stored.get('historical_warnings', [])
                    if not isinstance(entries, list) or len(entries) > 1024 or any(not isinstance(w, str) or len(w) > 1024 for w in entries):
                        raise ValueError('Invalid historical notices.')
                    previous_stale = tuple(entries)
                except (ValueError, TypeError, AttributeError, UnicodeError, KeyError, RecursionError):
                    previous_stale = ('Earlier TOFexplorer peaks may remain; the prior compatibility report could not be read.',)
            peak_data = handle['PeakData/PeakData']
            native_bytes = peak_data.size * peak_data.dtype.itemsize
            chunk_overhead = 0
            if peak_data.chunks:
                from math import prod
                largest_shape = (*peak_data.shape[:-1], peak_data.shape[-1] + len(document.signals))
                chunk_count = prod((size + chunk - 1) // chunk for size, chunk in zip(largest_shape, peak_data.chunks))
                chunk_overhead = chunk_count * 512
        previous = read_document(source, self.settings)
        encoded = document.model_dump_json().encode()
        if len(encoded) > MAX_DOCUMENT_BYTES:
            raise ValueError('Analysis metadata exceeds save limits.')
        custom_bytes = sum((s.recipe.frames[1] - s.recipe.frames[0] + 1) * document.shape[1] * document.shape[2] * 4 for s in document.signals if s.materialization_id)
        # Rebuilding sparse multi-channel chunks can materialize the entire cube.
        # Reserve for uncompressed native data and overhead, not just its current compressed size.
        aliases = sum(1 for s in document.signals if s.recipe.source == 'stored' and s.name != s.recipe.label)
        alias_bytes = aliases * document.shape[0] * document.shape[1] * document.shape[2] * 4
        rebuild_bytes = native_bytes + custom_bytes + alias_bytes + chunk_overhead + initial.st_size
        needed = initial.st_size + custom_bytes + max(64 * 1024**2, custom_bytes // 10) + len(encoded) * 2
        temporary = directory / f'.tmp-{uuid4()}.h5'
        checksums = {}
        with ExitStack() as reservations, ExitStack() as copy_reservation:
            copy_reservation.enter_context(reserve_disk(directory, needed))
            def reserve_rebuild():
                # The temporary copy is already reflected in disk_usage().
                # Transfer the reservation atomically rather than counting it twice.
                with _disk_lock:
                    copy_reservation.close()
                    reservations.enter_context(reserve_disk(directory, rebuild_bytes + max(64 * 1024**2, rebuild_bytes // 10)))
            try:
                copied = 0
                with source.open('rb') as src, temporary.open('xb') as out:
                    os.chmod(temporary, 0o600)
                    buffer = bytearray(COPY_BYTES)
                    while True:
                        check()
                        count = src.readinto(buffer)
                        if not count:
                            break
                        out.write(memoryview(buffer)[:count])
                        copied += count
                        progress('Copying acquisition', copied, initial.st_size)
                    out.flush()
                    os.fsync(out.fileno())
                del buffer
                check()
                with h5py.File(temporary, 'r+') as handle:
                    if previous:
                        for row in previous.signals:
                            key = f'ToFScope/Integrations/{row.materialization_id}'
                            if row.materialization_id and key in handle:
                                del handle[key]
                    if ROOT in handle:
                        del handle[ROOT]
                    group = handle.require_group(ROOT)
                    group.attrs.update(schema_version=document.schema_version, complete=False)
                    group.create_dataset('state_json', data=np.frombuffer(encoded, dtype='uint8'))
                    for row in document.signals:
                        if row.materialization_id is None:
                            continue
                        check()
                        digest = hashlib.sha256()
                        def checked_frames():
                            for i, values in enumerate(frames(row.id)):
                                check()
                                values = np.asarray(values)
                                digest.update(values.tobytes(order='C'))
                                progress('Saving ' + row.name, i + 1, row.recipe.frames[1] - row.recipe.frames[0] + 1)
                                yield values
                        record = IntegrationRecord(row.materialization_id, row.recipe.model_dump(mode='json'), document.shape[1:3], {}, {'kind': 'original_values'}, app_version=__version__)
                        write_integration_group(handle, record, checked_frames())
                        checksums[row.materialization_id] = digest.hexdigest()
                        handle[f'ToFScope/Integrations/{row.materialization_id}'].attrs['sha256'] = digest.hexdigest()
                    from tofscope.storage.native_saved_copy import prepare_native_channels
                    document, compatibility_warnings = prepare_native_channels(
                        handle, document, check, progress, previous,
                        reserve_rebuild, previous_stale,
                    )
                    encoded = document.model_dump_json().encode()
                    if len(encoded) > MAX_DOCUMENT_BYTES:
                        raise ValueError('Analysis metadata exceeds save limits.')
                    del group['state_json']
                    group.create_dataset('state_json', data=np.frombuffer(encoded, dtype='uint8'))
                    group.attrs['complete'] = True
                    handle.flush()
                self._verify(temporary, document, checksums, check)
                with temporary.open('rb') as stream:
                    os.fsync(stream.fileno())
                check()
                # The caller holds its revision lock across validation and publication.
                # A callback may return a context manager to make that interval explicit.
                from contextlib import nullcontext
                result = SavedFile(self.identifier(owner, destination), name, temporary.stat().st_size, tuple(compatibility_warnings))
                guard = before_publish()
                with guard if guard is not None else nullcontext():
                    check()
                    os.link(temporary, destination)
                # Publication is committed; cleanup cannot turn a completed copy into failure.
                return result
            finally:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    logging.getLogger(__name__).warning('Could not remove a private save temporary file.')

    def _verify(self, path, document, checksums, check):
        if read_document(path, self.settings) != document:
            raise ValueError('Saved analysis verification failed.')
        with h5py.File(path, 'r') as handle:
            for row in document.signals:
                if not row.materialization_id:
                    continue
                group = handle[f'ToFScope/Integrations/{row.materialization_id}']
                _read_info(group)
                digest = hashlib.sha256()
                for values in group['data']:
                    check()
                    if not np.isfinite(values).all():
                        raise ValueError('Saved results contain invalid values.')
                    digest.update(values.tobytes(order='C'))
                if digest.hexdigest() != checksums[row.materialization_id]:
                    raise ValueError('Saved result checksum verification failed.')
