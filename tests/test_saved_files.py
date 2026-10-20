import hashlib
import os
from pathlib import Path
from threading import Event
import unittest
from unittest.mock import patch
from dataclasses import replace
from uuid import uuid4
import h5py
import numpy as np
from service_fixture import setup_case
from tofscope.application.workspaces import WorkspaceService
from tofscope.application.models import SignalSnapshot
from tofscope.science.signals import SignalRecipe
from tofscope.storage.analysis_document import encode_document, read_document
from tofscope.storage.saved_files import SavedFileStore


class SavedFilesTests(unittest.TestCase):
    def setUp(self):
        setup_case(self)
        self.settings = replace(self.settings, output_root=self.settings.data_root / 'outputs')
        self.store = SavedFileStore(self.settings)
        ws = WorkspaceService(self.repo, self.settings)
        self.analysis = ws.create_analysis('a', ws.create('a').id, self.dataset)
        custom = SignalSnapshot(str(uuid4()), 'Hidden union', 4, SignalRecipe(intervals=((1., 2.), (3., 4.)), frames=(1, 2)))
        self.analysis = replace(self.analysis, signals=(*self.analysis.signals, custom), next_style_index=5)
        self.document = encode_document(self.analysis)
        self.values = np.arange(4, dtype='float32').reshape(2, 1, 2)
        self.source = self.settings.data_root / 'a.h5'
        with h5py.File(self.source, 'r+') as h:
            h.create_dataset('ToFScope/Unrelated', data=[42])
        self.before = hashlib.sha256(self.source.read_bytes()).hexdigest()

    def save(self, name='result.h5', **kwargs):
        return self.store.publish_copy('a', self.source, self.document, lambda sid: iter(self.values), name, kwargs.pop('cancel', Event()), lambda *args: None, kwargs.pop('before_publish', lambda: None))

    def test_saved_copy_preserves_source_vendor_data_and_hidden_custom_result(self):
        result = self.save()
        dest = self.store.path('a', result.id)
        self.assertEqual(result.size, dest.stat().st_size)
        self.assertEqual(self.before, hashlib.sha256(self.source.read_bytes()).hexdigest())
        doc = read_document(dest, self.settings)
        self.assertEqual(doc, self.document)
        with h5py.File(self.source, 'r') as source, h5py.File(dest, 'r') as saved:
            np.testing.assert_array_equal(source['PeakData/PeakData'][:], saved['PeakData/PeakData'][:])
            np.testing.assert_array_equal(saved['ToFScope/Unrelated'][:], [42])
            key = doc.signals[-1].materialization_id
            np.testing.assert_array_equal(saved[f'ToFScope/Integrations/{key}/data'][:], self.values)
            self.assertEqual(dict(source.attrs), dict(saved.attrs))
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.store.path('another owner', result.id)

    def test_cancel_failure_conflict_and_space_leave_no_output(self):
        stopped = Event(); stopped.set()
        with self.assertRaises(ValueError): self.save(cancel=stopped)
        with self.assertRaises(ValueError): self.save(before_publish=lambda: (_ for _ in ()).throw(ValueError('stale')))
        with patch('tofscope.storage.saved_files.shutil.disk_usage', return_value=type('Usage', (), {'free': 1})()):
            with self.assertRaises(OSError): self.save()
        with patch('tofscope.storage.saved_files.write_integration_group', side_effect=OSError('disk write failed')):
            with self.assertRaises(OSError): self.save()
        with patch.object(self.store, '_verify', side_effect=ValueError('corrupt')):
            with self.assertRaises(ValueError): self.save()
        self.assertEqual(list(self.store.owner_root('a').iterdir()), [])
        self.assertEqual(self.before, hashlib.sha256(self.source.read_bytes()).hexdigest())

    def test_names_aliases_and_collisions(self):
        for name in ['../a.h5', '/a.h5', 'a/b.h5', 'a\\b.h5', '.hidden.h5', 'result.txt', 'a\x00.h5']:
            with self.subTest(name=name), self.assertRaises(ValueError): self.save(name)
        os.link(self.source, self.store.owner_root('a') / 'alias.h5')
        with self.assertRaises(FileExistsError): self.save('alias.h5')
        result = self.save()
        before = self.store.path('a', result.id).read_bytes()
        with self.assertRaises(FileExistsError): self.save()
        self.assertEqual(before, self.store.path('a', result.id).read_bytes())

    def test_repeat_save_replaces_only_document_owned_records(self):
        first = self.save()
        self.source = self.store.path('a', first.id)
        with h5py.File(self.source, 'r+') as h:
            h.create_group('ToFScope/Integrations/unrelated-record')
        second = self.save('next.h5')
        with h5py.File(self.store.path('a', second.id), 'r') as h:
            self.assertEqual(len(h['ToFScope/Integrations']), 2)
            self.assertIn('unrelated-record', h['ToFScope/Integrations'])
        self.assertLess(second.size, first.size + 65536)

    def test_concurrent_same_name_has_one_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        def attempt(_):
            try: return self.save()
            except FileExistsError: return None
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(sum(x is not None for x in results), 1)
        self.assertEqual(len(list(self.store.owner_root('a').iterdir())), 1)

    def test_disk_reservations_prevent_concurrent_overcommit_and_release(self):
        from tofscope.storage.saved_files import reserve_disk
        with patch('tofscope.storage.saved_files.shutil.disk_usage', return_value=type('Usage', (), {'free': 40})()):
            with reserve_disk(self.store.root, 20):
                with self.assertRaises(OSError):
                    with reserve_disk(self.store.root, 30): pass
            with reserve_disk(self.store.root, 30): pass

    def test_nonfinite_results_and_external_links_rejected(self):
        self.values[0, 0, 0] = np.nan
        with self.assertRaises(ValueError): self.save()
        self.assertEqual(list(self.store.owner_root('a').iterdir()), [])
        with h5py.File(self.source, 'r+') as handle:
            handle['external'] = h5py.ExternalLink('b.h5', '/')
        with self.assertRaises(ValueError): self.save()
        self.assertEqual(list(self.store.owner_root('a').iterdir()), [])
