import shutil
import unittest
from dataclasses import replace
from threading import Event
from uuid import uuid4
from unittest.mock import patch
import h5py
import numpy as np
from service_fixture import setup_case
from tofscope.api.app import build_services
from tofscope.application.models import SignalSnapshot
from tofscope.science.signals import SignalRecipe
from tofscope.storage.analysis_document import encode_document
from tofscope.storage.saved_files import SavedFileStore


class RestoreTests(unittest.TestCase):
    def setUp(self):
        setup_case(self)
        self.settings = replace(self.settings, output_root=self.settings.data_root / 'outputs')
        services = build_services(self.settings)
        self.addCleanup(services.jobs.shutdown)
        self.addCleanup(services.analyses.close_all)
        a = services.analyses.create_analysis('a', services.repository.open('a', 'a.h5'))
        custom = SignalSnapshot(str(uuid4()), 'Raw union', 2, SignalRecipe(intervals=((1., 2.), (3., 4.)), frames=(1, 2)))
        hidden = SignalSnapshot(str(uuid4()), 'Hidden raw', 3, SignalRecipe(intervals=((2., 3.),), frames=(0, 0)))
        a = replace(a, signals=(*a.signals, custom, hidden), image_signal_id=custom.id, next_style_index=4)
        self.values = {custom.id: np.arange(4, dtype='float32').reshape(2, 1, 2), hidden.id: np.full((1, 1, 2), 19., dtype='float32')}
        document = encode_document(a)
        store = SavedFileStore(self.settings)
        result = store.publish_copy('a', self.settings.data_root / 'a.h5', document, lambda sid: iter(self.values[sid]), 'saved.h5', Event(), lambda *a: None, lambda: None)
        shutil.copyfile(store.path('a', result.id), self.settings.data_root / 'portable.h5')
        self.original = a
        self.document = document
        services.analyses.close_all()
        services.cache.clear()
        (self.settings.data_root / 'a.h5').unlink()

    def restart(self, **changes):
        s = build_services(replace(self.settings, **changes))
        self.addCleanup(s.jobs.shutdown)
        self.addCleanup(s.analyses.close_all)
        self.addCleanup(s.cache.clear)
        return s

    def test_restart_relocation_fresh_owner_and_eviction_need_no_raw_integration(self):
        s = self.restart()
        with patch('tofscope.storage.acquisitions.custom_peak_windows', side_effect=AssertionError('must not reintegrate')):
            a = s.analyses.create_analysis('fresh', s.repository.open('fresh', 'portable.h5'))
            self.assertEqual([x.name for x in a.signals], [x.name for x in self.original.signals])
            self.assertTrue(set(x.id for x in a.signals).isdisjoint(x.id for x in self.original.signals))
            panel = s.presenter.snapshot('fresh', a.id, {'ion', 'front', 'profile'})
            self.assertEqual(panel.panels['ion'].values, [[2., 4.]])
            self.assertEqual(panel.panels['profile'].series[0].values, [None, .5, 2.5])
            for row in a.signals[1:]:
                with s.cache.load('fresh', a.id, a.dataset, row.recipe, materialization_id=row.materialization_id) as lease:
                    np.testing.assert_array_equal(lease.array, self.values[self.original.signals[a.signals.index(row)].id])
                s.cache.clear()
            self.assertEqual(s.cache.budget.users['fresh'], 0)

    def test_oversized_result_metadata_is_rejected_before_restore(self):
        import json
        path = self.settings.data_root / 'portable.h5'
        key = f'ToFScope/Integrations/{self.document.signals[-1].materialization_id}/recipe_json'
        with h5py.File(path, 'r+') as h:
            stored = h[key][()]
            metadata = json.loads(stored.decode() if isinstance(stored, bytes) else bytes(stored).decode())
            metadata['derivation']['label'] = 'x' * (5 * 1024**2)
            del h[key]
            h.create_dataset(key, data=json.dumps(metadata), dtype=h5py.string_dtype('utf-8'))
        s = self.restart(global_bytes=128 * 1024, user_bytes=128 * 1024, analysis_bytes=128 * 1024)
        with self.assertRaises(ValueError):
            s.analyses.create_analysis('a', s.repository.open('a', 'portable.h5'))
        self.assertEqual(s.analyses.entries, {})
        self.assertEqual(s.cache.budget.physical_bytes, 0)

    def test_bounded_result_metadata_still_requires_decode_admission(self):
        import json
        path = self.settings.data_root / 'portable.h5'
        key = f'ToFScope/Integrations/{self.document.signals[-1].materialization_id}/recipe_json'
        with h5py.File(path, 'r+') as h:
            metadata = json.loads(h[key][:].tobytes())
            metadata['derivation']['label'] = 'x' * 20000
            del h[key]
            h.create_dataset(key, data=np.frombuffer(json.dumps(metadata).encode(), dtype='uint8'))
        s = self.restart(global_bytes=128 * 1024, user_bytes=128 * 1024, analysis_bytes=128 * 1024)
        with patch('tofscope.storage.integration_store._read_info', side_effect=AssertionError('parsed before admission')) as reader:
            with self.assertRaisesRegex(ValueError, 'Memory budget'):
                s.analyses.create_analysis('a', s.repository.open('a', 'portable.h5'))
            reader.assert_not_called()
        self.assertEqual(s.cache.budget.physical_bytes, 0)

    def test_missing_hidden_result_and_invalid_values_fail_open(self):
        path = self.settings.data_root / 'portable.h5'
        with h5py.File(path, 'r+') as h:
            del h[f'ToFScope/Integrations/{self.document.signals[-1].materialization_id}']
        s = self.restart()
        with self.assertRaises(ValueError):
            s.analyses.create_analysis('a', s.repository.open('a', 'portable.h5'))
        self.assertEqual(len(s.analyses.entries), 0)

    def test_restored_signals_respect_owner_quota(self):
        s = self.restart(signals_per_user=2)
        with self.assertRaises(ValueError):
            s.analyses.create_analysis('a', s.repository.open('a', 'portable.h5'))
        self.assertEqual(len(s.analyses.entries), 0)

    def test_changed_saved_values_fail_checksum_validation(self):
        path = self.settings.data_root / 'portable.h5'
        with h5py.File(path, 'r+') as h:
            h[f'ToFScope/Integrations/{self.document.signals[-1].materialization_id}/data'][0, 0, 0] = 22.
        s = self.restart()
        with self.assertRaisesRegex(ValueError, 'checksum'):
            s.analyses.create_analysis('a', s.repository.open('a', 'portable.h5'))

    def test_successful_edit_replaces_materialization_but_rename_retains_it(self):
        from tofscope.application.commands import CommandEnvelope
        from tofscope.application.jobs import IntegrationSpec
        s = self.restart()
        a = s.analyses.create_analysis('a', s.repository.open('a', 'portable.h5'))
        row = a.signals[1]
        renamed = s.explore.apply('a', a.id, CommandEnvelope('rename', a.revision, a.dataset.generation, {'type': 'rename_signal', 'signal_id': row.id, 'name': 'Renamed'}))
        self.assertEqual(renamed.signals[1].materialization_id, row.materialization_id)
        envelope = CommandEnvelope('edit', renamed.revision, a.dataset.generation, {'type': 'set_depth', 'depth': {'mode': 'all'}})
        job = s.jobs.submit('a', a.id, envelope, IntegrationSpec(((1., 2.),), (1, 2), 'Edited', row.id, row.recipe_version))
        self.assertEqual(s.jobs.wait('a', job.id, 3).status, 'succeeded')
        changed = s.analyses.get('a', a.id).signals[1]
        self.assertIsNone(changed.materialization_id)
        self.assertEqual(changed.id, row.id)
