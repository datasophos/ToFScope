import hashlib
import json
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
from tofscope.application.analyses import AnalysisService
from tofscope.application.models import SignalSnapshot
from tofscope.science.signals import SignalRecipe
from tofscope.storage.analysis_document import encode_document, read_document
from tofscope.storage.saved_files import SavedFileStore


class SavedFilesTests(unittest.TestCase):
    def setUp(self):
        setup_case(self)
        self.settings = replace(self.settings, output_root=self.settings.data_root / 'outputs')
        self.store = SavedFileStore(self.settings)
        ws = AnalysisService(self.repo, self.settings)
        self.analysis = ws.create_analysis('a', self.dataset)
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

    def test_save_includes_full_frame_disjoint_channel_and_warns_about_bounds(self):
        stored = replace(self.analysis.signals[0], name='Al 27')
        custom = replace(self.analysis.signals[-1], name='Disjoint test', recipe=SignalRecipe(intervals=((1., 2.), (3., 4.)), frames=(0, 2)))
        self.analysis = replace(self.analysis, signals=(stored, custom))
        self.document = encode_document(self.analysis)
        self.values = np.arange(6, dtype='float32').reshape(3, 1, 2)
        result = self.save()
        saved = self.store.path('a', result.id)
        with h5py.File(self.source, 'r') as original, h5py.File(saved, 'r') as copy:
            table = copy['PeakData/PeakTable'][:]
            self.assertEqual(table[stored.recipe.stored_index]['label'], b'nominal 4')
            self.assertEqual(table[-2]['label'], b'Al 27')
            np.testing.assert_array_equal(copy['PeakData/PeakData'][:, :, :, -2], original['PeakData/PeakData'][:, :, :, stored.recipe.stored_index])
            self.assertEqual(table[-1]['label'], b'Disjoint: Disjoint test')
            report = json.loads(bytes(copy['ToFScope/Analysis/native_export_json'][:]).decode())
            self.assertEqual(next(x for x in report['signals'] if x['name'] == 'Disjoint test')['intervals'], [[1., 2.], [3., 4.]])
            self.assertTrue(any('bounds' in warning for warning in report['warnings']))
            self.assertEqual(float(table[-1]['lower integration limit']), 1.)
            self.assertEqual(float(table[-1]['upper integration limit']), 4.)
            np.testing.assert_array_equal(copy['PeakData/PeakData'][:, :, :, -1], self.values)
            np.testing.assert_array_equal(copy['PeakData/PeakData'][:, :, :, :2], original['PeakData/PeakData'][:])
        self.assertTrue(any('Disjoint test' in w and 'bounds' in w for w in result.compatibility_warnings))
        self.assertEqual(read_document(saved, self.settings).signals[-1].recipe.intervals, ((1., 2.), (3., 4.)))
        self.assertEqual(self.before, hashlib.sha256(self.source.read_bytes()).hexdigest())

    def test_partial_frame_signal_is_retained_and_reported_unavailable(self):
        result = self.save()
        self.assertTrue(any('Hidden union' in warning and 'not available' in warning for warning in result.compatibility_warnings))
        with h5py.File(self.store.path('a', result.id), 'r') as saved:
            self.assertEqual(saved['PeakData/PeakData'].shape[-1], 2)
            np.testing.assert_array_equal(saved[f'ToFScope/Integrations/{self.document.signals[-1].materialization_id}/data'][:], self.values)

    def test_repeated_save_does_not_accumulate_native_channels(self):
        custom = replace(self.analysis.signals[-1], name='Full peak', recipe=SignalRecipe(intervals=((1., 2.),), frames=(0, 2)))
        self.analysis = replace(self.analysis, signals=(self.analysis.signals[0], custom))
        self.document = encode_document(self.analysis)
        self.values = np.arange(6, dtype='float32').reshape(3, 1, 2)
        first = self.save()
        self.source = self.store.path('a', first.id)
        self.document = read_document(self.source, self.settings)
        second = self.save('second.h5')
        with h5py.File(self.store.path('a', second.id), 'r') as saved:
            self.assertEqual(saved['PeakData/PeakData'].shape[-1], 3)
            self.assertEqual(list(saved['PeakData/PeakTable']['label']).count(b'Full peak'), 1)
            np.testing.assert_array_equal(saved['PeakData/PeakData'][:, :, :, -1], self.values)

    def test_matching_repeated_save_does_not_reserve_a_native_rebuild(self):
        custom = replace(self.analysis.signals[-1], name='Full peak', recipe=SignalRecipe(intervals=((1., 2.),), frames=(0, 2)))
        self.analysis = replace(self.analysis, signals=(self.analysis.signals[0], custom))
        self.document = encode_document(self.analysis)
        self.values = np.arange(6, dtype='float32').reshape(3, 1, 2)
        first = self.save()
        self.source = self.store.path('a', first.id)
        self.document = read_document(self.source, self.settings)
        available = self.source.stat().st_size + 65 * 1024**2
        with patch('tofscope.storage.saved_files.shutil.disk_usage', return_value=type('Usage', (), {'free': available})()):
            second = self.save('repeated.h5')
        self.assertTrue(self.store.path('a', second.id).exists())

    def test_removing_custom_signal_preserves_native_peak_and_reports_it(self):
        custom = replace(self.analysis.signals[-1], name='Full peak', recipe=SignalRecipe(intervals=((1., 2.),), frames=(0, 2)))
        self.analysis = replace(self.analysis, signals=(self.analysis.signals[0], custom))
        self.document = encode_document(self.analysis)
        self.values = np.arange(6, dtype='float32').reshape(3, 1, 2)
        first = self.save()
        self.source = self.store.path('a', first.id)
        restored = read_document(self.source, self.settings)
        self.document = restored.model_copy(update={'signals': (restored.signals[0],)})
        second = self.save('removed.h5')
        with h5py.File(self.store.path('a', second.id), 'r') as saved:
            self.assertEqual(saved['PeakData/PeakData'].shape[-1], 3)
            self.assertIn(b'Full peak', saved['PeakData/PeakTable']['label'])
        self.assertTrue(any('Full peak' in w and 'may remain' in w for w in second.compatibility_warnings))
        self.source = self.store.path('a', second.id)
        self.document = read_document(self.source, self.settings)
        third = self.save('again.h5')
        self.assertTrue(any('Full peak' in w and 'may remain' in w for w in third.compatibility_warnings))

    def test_forged_native_indices_never_remove_vendor_data(self):
        with h5py.File(self.source, 'r+') as handle:
            handle.require_group('ToFScope/NativeExport').attrs['managed_indices'] = '[0, 1]'
        self.before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        result = self.save()
        with h5py.File(self.source, 'r') as original, h5py.File(self.store.path('a', result.id), 'r') as saved:
            np.testing.assert_array_equal(saved['PeakData/PeakData'][:], original['PeakData/PeakData'][:])
            np.testing.assert_array_equal(saved['PeakData/PeakTable'][:], original['PeakData/PeakTable'][:])

    def test_renaming_stored_signal_back_restores_native_label(self):
        stored = self.analysis.signals[0]
        self.analysis = replace(self.analysis, signals=(replace(stored, name='Al 27'),))
        self.document = encode_document(self.analysis)
        first = self.save()
        self.source = self.store.path('a', first.id)
        doc = read_document(self.source, self.settings)
        row = doc.signals[0]
        self.document = doc.model_copy(update={'signals': (row.model_copy(update={'name': row.recipe.label}),)})
        second = self.save('restored-label.h5')
        with h5py.File(self.store.path('a', second.id), 'r') as handle:
            self.assertEqual(handle['PeakData/PeakTable'][row.recipe.stored_index]['label'], b'nominal 4')

    def test_unsupported_native_layout_lists_each_affected_signal(self):
        with h5py.File(self.source, 'r+') as handle:
            table = handle['PeakData/PeakTable']
            records = table[:]
            del handle['PeakData/PeakTable']
            dtype = np.dtype([('label', 'S64'), ('mass', 'f4'), ('lower integration limit', 'f4'), ('upper integration limit', 'f4'), ('extra', 'i4')])
            rows = np.zeros(len(records), dtype=dtype)
            for field in records.dtype.names:
                rows[field] = records[field]
            handle['PeakData'].create_dataset('PeakTable', data=rows)
        renamed = replace(self.analysis.signals[0], name='Al 27')
        self.analysis = replace(self.analysis, signals=(renamed, self.analysis.signals[-1]))
        self.document = encode_document(self.analysis)
        result = self.save()
        self.assertTrue(any('Al 27' in w and 'unavailable' in w for w in result.compatibility_warnings))
        self.assertTrue(any('Hidden union' in w and 'unavailable' in w for w in result.compatibility_warnings))

    def test_sparse_multichannel_chunks_preserve_fill_and_original_values(self):
        with h5py.File(self.source, 'r+') as handle:
            del handle['PeakData/PeakData']
            data = handle['PeakData'].create_dataset('PeakData', shape=(3, 1, 2, 2), dtype='float32', chunks=(1, 1, 1, 2), compression='gzip', fillvalue=7)
            data[0, 0, 0, :] = [1, 2]
            original = data[:]
        self.analysis = replace(self.analysis, signals=(replace(self.analysis.signals[0], name='Alias'), self.analysis.signals[-1]))
        self.document = encode_document(self.analysis)
        result = self.save()
        with h5py.File(self.store.path('a', result.id), 'r') as saved:
            np.testing.assert_array_equal(saved['PeakData/PeakData'][:, :, :, :2], original)
            np.testing.assert_array_equal(saved['PeakData/PeakData'][:, :, :, -1], original[:, :, :, self.analysis.signals[0].recipe.stored_index])

    def test_native_peak_count_keeps_original_attribute_type(self):
        with h5py.File(self.source, 'r+') as handle:
            handle.attrs.create('NbrPeaks', np.int32(2))
        self.before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        custom = replace(self.analysis.signals[-1], name='Full peak', recipe=SignalRecipe(intervals=((1., 2.),), frames=(0, 2)))
        self.analysis = replace(self.analysis, signals=(self.analysis.signals[0], custom))
        self.document = encode_document(self.analysis)
        self.values = np.arange(6, dtype='float32').reshape(3, 1, 2)
        result = self.save()
        with h5py.File(self.store.path('a', result.id), 'r') as saved:
            self.assertEqual(saved.attrs.get_id('NbrPeaks').dtype, np.dtype('int32'))
            self.assertEqual(saved.attrs['NbrPeaks'], 3)

    def test_partial_stored_signal_is_not_aliased_and_is_reported(self):
        stored = self.analysis.signals[0]
        partial = replace(stored, name='Partial stored', recipe=replace(stored.recipe, frames=(1, 2)))
        self.analysis = replace(self.analysis, signals=(partial, self.analysis.signals[-1]))
        self.document = encode_document(self.analysis)
        result = self.save()
        with h5py.File(self.store.path('a', result.id), 'r') as saved:
            self.assertNotIn(b'Partial stored', saved['PeakData/PeakTable']['label'])
        self.assertTrue(any('Partial stored' in w and 'selected frames' in w for w in result.compatibility_warnings))

    def test_stored_alias_preserves_missing_samples(self):
        with h5py.File(self.source, 'r+') as handle:
            handle['PeakData/PeakData'][0, 0, 0, self.analysis.signals[0].recipe.stored_index] = np.nan
        self.before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.analysis = replace(self.analysis, signals=(replace(self.analysis.signals[0], name='Aliased'), self.analysis.signals[-1]))
        self.document = encode_document(self.analysis)
        result = self.save()
        with h5py.File(self.store.path('a', result.id), 'r') as saved:
            self.assertTrue(np.isnan(saved['PeakData/PeakData'][0, 0, 0, -1]))

    def test_renamed_custom_reports_old_vendor_peak_may_remain(self):
        custom = replace(self.analysis.signals[-1], name='Old peak', recipe=SignalRecipe(intervals=((1., 2.),), frames=(0, 2)))
        self.analysis = replace(self.analysis, signals=(self.analysis.signals[0], custom))
        self.document = encode_document(self.analysis)
        self.values = np.arange(6, dtype='float32').reshape(3, 1, 2)
        first = self.save()
        self.source = self.store.path('a', first.id)
        doc = read_document(self.source, self.settings)
        row = doc.signals[-1].model_copy(update={'name': 'New peak'})
        self.document = doc.model_copy(update={'signals': (doc.signals[0], row)})
        second = self.save('renamed.h5')
        self.assertTrue(any('Old peak' in w and 'may remain' in w for w in second.compatibility_warnings))

    def test_renamed_labeled_peak_keeps_original_vendor_label(self):
        index = self.analysis.signals[0].recipe.stored_index
        with h5py.File(self.source, 'r+') as handle:
            table = handle['PeakData/PeakTable'][:]
            table[index]['label'] = b'[194Pt]'
            handle['PeakData/PeakTable'][:] = table
        self.analysis = replace(self.analysis, signals=(replace(self.analysis.signals[0], name='User alias'), self.analysis.signals[-1]))
        self.document = encode_document(self.analysis)
        result = self.save()
        with h5py.File(self.store.path('a', result.id), 'r') as saved:
            labels = saved['PeakData/PeakTable']['label'][:]
            self.assertIn(b'[194Pt]', labels)
            self.assertIn(b'User alias', labels)
            np.testing.assert_array_equal(saved['PeakData/PeakData'][:, :, :, index], saved['PeakData/PeakData'][:, :, :, -1])

    def test_control_characters_are_reported_not_written_to_vendor_labels(self):
        self.analysis = replace(self.analysis, signals=(replace(self.analysis.signals[0], name='Al\x00hidden'), self.analysis.signals[-1]))
        self.document = encode_document(self.analysis)
        result = self.save()
        self.assertTrue(any('label unavailable' in warning for warning in result.compatibility_warnings))
        with h5py.File(self.store.path('a', result.id), 'r') as saved:
            self.assertEqual(saved['PeakData/PeakData'].shape[-1], 2)

    def test_oversized_native_chunk_is_reported_without_decompression(self):
        from tofscope.storage.native_saved_copy import prepare_native_channels
        path = self.settings.data_root / 'large-chunk.h5'
        dtype = np.dtype([('label', 'S64'), ('mass', 'f4'), ('lower integration limit', 'f4'), ('upper integration limit', 'f4')])
        with h5py.File(path, 'w') as handle:
            handle.create_dataset('PeakData/PeakData', shape=(3, 512, 512, 3), dtype='float32', chunks=(3, 512, 512, 3), compression='gzip')
            handle.create_dataset('PeakData/PeakTable', data=np.zeros(3, dtype=dtype))
            handle.require_group('ToFScope/Analysis')
            document, warnings = prepare_native_channels(handle, self.document, lambda: None, lambda *args: None)
            self.assertEqual(document, self.document)
            self.assertTrue(any('Hidden union' in w and 'chunks exceed' in w for w in warnings))
            self.assertEqual(handle['PeakData/PeakData'].id.get_num_chunks(), 0)

    def test_integer_native_bounds_leave_custom_signal_in_tofscope_with_notice(self):
        with h5py.File(self.source, 'r+') as handle:
            records = handle['PeakData/PeakTable'][:]
            del handle['PeakData/PeakTable']
            dtype = np.dtype([('label', 'S64'), ('mass', 'i4'), ('lower integration limit', 'i4'), ('upper integration limit', 'i4')])
            rows = np.zeros(len(records), dtype=dtype)
            for field in records.dtype.names:
                rows[field] = records[field]
            handle['PeakData'].create_dataset('PeakTable', data=rows)
        self.analysis = replace(self.analysis, signals=(self.analysis.signals[0], replace(self.analysis.signals[-1], recipe=SignalRecipe(intervals=((1.1, 2.1),), frames=(0, 2)))))
        self.document = encode_document(self.analysis)
        self.values = np.arange(6, dtype='float32').reshape(3, 1, 2)
        result = self.save()
        self.assertTrue(any('Hidden union' in warning and 'unavailable' in warning for warning in result.compatibility_warnings))
        with h5py.File(self.store.path('a', result.id), 'r') as saved:
            np.testing.assert_array_equal(saved[f'ToFScope/Integrations/{self.document.signals[-1].materialization_id}/data'][:], self.values)

    def test_native_export_retains_sparse_compressed_chunks(self):
        with h5py.File(self.source, 'r+') as handle:
            values = handle['PeakData/PeakData'][:]
            del handle['PeakData/PeakData']
            data = handle['PeakData'].create_dataset('PeakData', data=values, chunks=(1, 1, 2, 1), compression='gzip')
            original_chunk = data.id.read_direct_chunk((0, 0, 0, 0))
        self.before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        custom = replace(self.analysis.signals[-1], name='Full peak', recipe=SignalRecipe(intervals=((1., 2.),), frames=(0, 2)))
        self.analysis = replace(self.analysis, signals=(self.analysis.signals[0], custom))
        self.document = encode_document(self.analysis)
        self.values = np.arange(6, dtype='float32').reshape(3, 1, 2)
        result = self.save()
        with h5py.File(self.store.path('a', result.id), 'r') as saved:
            self.assertEqual(saved['PeakData/PeakData'].id.read_direct_chunk((0, 0, 0, 0)), original_chunk)
            np.testing.assert_array_equal(saved['PeakData/PeakData'][:, :, :, -1], self.values)

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
            with reserve_disk(self.store.owner_root('a'), 20):
                with self.assertRaises(OSError):
                    with reserve_disk(self.store.owner_root('a'), 30): pass
            with reserve_disk(self.store.owner_root('a'), 30): pass

    def test_nonfinite_results_and_external_links_rejected(self):
        self.values[0, 0, 0] = np.nan
        with self.assertRaises(ValueError): self.save()
        self.assertEqual(list(self.store.owner_root('a').iterdir()), [])
        with h5py.File(self.source, 'r+') as handle:
            handle['external'] = h5py.ExternalLink('b.h5', '/')
        with self.assertRaises(ValueError): self.save()
        self.assertEqual(list(self.store.owner_root('a').iterdir()), [])

    def test_large_copy_keeps_only_one_admitted_buffer(self):
        import tracemalloc
        from tofscope.storage.saved_files import COPY_BYTES
        with h5py.File(self.source, 'r+') as h:
            data = h.create_dataset('Payload', (24 * 1024**2,), dtype='uint8')
            for start in range(0, data.size, COPY_BYTES):
                data[start:start + COPY_BYTES] = 0
        tracemalloc.start()
        try:
            self.save()
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, COPY_BYTES + 2 * 1024**2)
