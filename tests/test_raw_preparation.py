import unittest
import hashlib
import os
import shutil
from dataclasses import replace
from threading import Event
from unittest.mock import patch

import h5py
import numpy as np
from service_fixture import setup_case
from tofscope.api.app import build_services
from tofscope.science.raw_peaks import integrate_peak_table


class RawPreparationTests(unittest.TestCase):
    def setUp(self):
        setup_case(self)
        self.path = self.settings.data_root / 'a.h5'
        with h5py.File(self.path, 'r+') as f:
            del f['PeakData/PeakData']
            # Three completed writes and a deliberately nonempty spare event slot.
            f.attrs['NbrWrites'] = 3
        self.digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.s = build_services(self.settings)
        self.addCleanup(self.s.jobs.shutdown)
        self.addCleanup(self.s.analyses.close_all)

    def preview(self):
        return self.s.preparations.inspect('a', 'a.h5')

    def submit(self, name='prepared.h5'):
        return self.s.preparations.submit('a', 'a.h5', 'acquisition', self.preview().generation, name)

    def test_confirmation_preflight_does_not_modify_or_start_work(self):
        p = self.preview()
        self.assertTrue(p.requires_preparation)
        self.assertEqual(p.shape, (3, 1, 2, 2))
        self.assertGreater(p.required_bytes, self.path.stat().st_size)
        self.assertEqual(self.s.jobs.jobs, {})
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), self.digest)

    def test_initial_inspection_retries_a_first_read_identity_change(self):
        from tofscope.storage import raw_preparation
        original = raw_preparation.h5py.File
        changed = False
        def hydrate(path, *args, **kwargs):
            nonlocal changed
            result = original(path, *args, **kwargs)
            if not changed and str(path) == str(self.path):
                changed = True
                st = self.path.stat()
                os.utime(self.path, ns=(st.st_atime_ns, st.st_mtime_ns + 1000000))
            return result
        with patch.object(raw_preparation.h5py, 'File', side_effect=hydrate):
            p = self.preview()
        self.assertTrue(p.requires_preparation)
        self.assertEqual(p.generation, self.s.repository.identity(self.path))

    def test_continuously_changing_initial_inspection_is_bounded(self):
        from tofscope.storage import raw_preparation
        from tofscope.storage.acquisitions import SourceChanged
        original = raw_preparation.h5py.File
        calls = 0
        def changing(path, *args, **kwargs):
            nonlocal calls
            result = original(path, *args, **kwargs)
            calls += 1
            st = self.path.stat()
            os.utime(self.path, ns=(st.st_atime_ns, st.st_mtime_ns + 1000000))
            return result
        with patch.object(raw_preparation.h5py, 'File', side_effect=changing):
            with self.assertRaises(SourceChanged): self.preview()
        self.assertEqual(calls, 3)

    def test_reader_defaults_require_acknowledgment_and_are_recorded_in_copy(self):
        with h5py.File(self.path, 'r+') as f:
            del f['FullSpectra'].attrs['ClockPeriod']
            del f.attrs['Configuration File Contents']
        p = self.preview()
        self.assertEqual(len(p.assumptions), 2)
        with self.assertRaises(ValueError): self.submit()
        job = self.s.preparations.submit('a', 'a.h5', 'acquisition', p.generation, 'assumed.h5', accept_assumptions=True)
        done = self.s.jobs.wait('a', job.id, 5)
        self.assertEqual(done.status, 'succeeded', done.safe_error)
        target = self.s.saves.files.path('a', done.saved_file.id)
        with h5py.File(target, 'r') as f:
            import json
            from tofscope.storage.explorer import integration_parameters
            self.assertEqual(integration_parameters(f), (1, 2))
            self.assertEqual(json.loads(f['ToFScope/Preparation'].attrs['assumptions']), list(p.assumptions))
        with h5py.File(self.path, 'r') as f:
            self.assertNotIn('ClockPeriod', f['FullSpectra'].attrs)
            self.assertNotIn('Configuration File Contents', f.attrs)

    def test_reader_defaults_do_not_decode_unrelated_attributes(self):
        from types import SimpleNamespace
        from tofscope.storage.explorer import integration_parameters
        class Attributes:
            def __init__(self, values): self.values = values
            def __contains__(self, key): return key in self.values
            def __getitem__(self, key): return self.values[key]
            def get(self, key, default=None): return self.values.get(key, default)
            def __iter__(self): raise AssertionError('Unrelated attributes must not be decoded.')
        class Source:
            attrs = Attributes({'NbrWaveforms': 2})
            def __getitem__(self, key):
                assert key == 'FullSpectra'
                return SimpleNamespace(attrs=Attributes({'SampleInterval': 64.}))
        self.assertEqual(integration_parameters(Source(), reader_defaults=True), (1, 2))

    def test_prepare_float_values_completed_frames_and_self_contained_reopen(self):
        j = self.submit()
        done = self.s.jobs.wait('a', j.id, 5)
        self.assertEqual(done.status, 'succeeded', done.safe_error)
        self.assertEqual(done.kind, 'preparation')
        with self.assertRaises(KeyError): self.s.jobs.get('b', j.id)
        target = self.s.saves.files.path('a', done.saved_file.id)
        with h5py.File(target, 'r') as f:
            values = f['PeakData/PeakData'][:]
            self.assertEqual(values.shape, (3, 1, 2, 2))
            self.assertEqual(values.dtype, np.float32)
            np.testing.assert_array_equal(values[:, 0, 0, :], [[1., .5]] * 3)
            np.testing.assert_array_equal(values[:, 0, 1, :], [[.25, .5], [.5, .5], [.75, .5]])
            self.assertIn('FullSpectra/EventList', f)
            self.assertEqual(f.attrs['NbrPeaks'], 2)
        ref = self.s.repository.open('a', done.saved_file.id, 'saved')
        a = self.s.analyses.create_analysis('a', ref)
        self.assertEqual(a.shape, values.shape)
        self.assertFalse(self.s.preparations.inspect('a', done.saved_file.id, 'saved').requires_preparation)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), self.digest)
        self.assertEqual(self.s.cache.budget.users.get('a', 0), 0)

    def test_source_changes_and_name_collisions_are_rejected(self):
        p = self.preview()
        with h5py.File(self.path, 'r+') as f: f.attrs['changed'] = True
        with self.assertRaises(ValueError):
            self.s.preparations.submit('a', 'a.h5', 'acquisition', p.generation, 'changed.h5')
        done = self.s.jobs.wait('a', self.submit().id, 5)
        self.assertEqual(done.status, 'succeeded', done.safe_error)
        with self.assertRaises(FileExistsError): self.submit()
        self.assertEqual(len(self.s.saves.files.list('a')), 1)

    def test_cancelled_preparation_never_publishes_and_releases_memory(self):
        entered, release = Event(), Event()
        self.addCleanup(release.set)
        from tofscope.storage import raw_preparation
        original = raw_preparation.integrate_peak_table
        def pause(*args, **kwargs):
            entered.set(); release.wait(3)
            return original(*args, **kwargs)
        with patch.object(raw_preparation, 'integrate_peak_table', side_effect=pause):
            j = self.submit()
            self.assertTrue(entered.wait(2))
            self.s.jobs.cancel('a', j.id)
            release.set()
            self.assertEqual(self.s.jobs.wait('a', j.id, 5).status, 'cancelled')
        self.assertEqual(self.s.saves.files.list('a'), [])
        self.assertFalse(list(self.s.saves.files.owner_root('a').glob('.tmp-*')))
        self.assertEqual(self.s.cache.budget.users.get('a', 0), 0)

    def test_kernel_counts_overlaps_endpoints_fractional_values_and_unsorted_windows(self):
        events = np.empty((1, 2), dtype=object)
        events[0, 0] = np.array([0, 64, 128, 192, 256, 320, 99999], dtype='uint32')
        events[0, 1] = np.array([], dtype='uint32')
        windows = [(3., 5.), (1., 3.), (2., 4.)]
        actual = integrate_peak_table(events, np.arange(6.), 64, 4, windows)
        np.testing.assert_array_equal(actual, [[[.75, .75, .75], [0, 0, 0]]])

    def test_kernel_matches_rosettasciio_for_disjoint_windows(self):
        from rsciio.tofwerk._reconstruction import compute_peak_data_from_eventlist
        events = np.empty((1, 2, 3), dtype=object)
        rng = np.random.default_rng(4)
        for idx in np.ndindex(events.shape):
            events[idx] = rng.integers(0, 500, size=25, dtype='uint32')
        windows = [(2.5, 3.5), (.5, 1.5), (4.5, 5.5)]
        table = [dict(mass=(lo+hi)/2, lower_integration_limit=lo, upper_integration_limit=hi) for lo,hi in windows]
        expected = compute_peak_data_from_eventlist(events, np.arange(6.), 6, 64, 4, table, False, np.float32)
        np.testing.assert_array_equal(integrate_peak_table(events[0], np.arange(6.), 64, 4, windows), expected[0])

    def test_disk_or_memory_exhaustion_cleans_up_without_publication(self):
        usage = shutil.disk_usage(self.path.parent)
        with patch('tofscope.storage.saved_files.shutil.disk_usage', return_value=usage._replace(free=0)):
            done = self.s.jobs.wait('a', self.submit().id, 5)
            self.assertEqual(done.status, 'failed')
        self.s.cache.budget.settings = replace(self.settings, analysis_bytes=256 * 1024)
        done = self.s.jobs.wait('a', self.submit('memory.h5').id, 5)
        self.assertEqual(done.status, 'failed')
        self.assertEqual(self.s.saves.files.list('a'), [])
        self.assertFalse(list(self.s.saves.files.owner_root('a').glob('.tmp-*')))
        self.assertEqual(self.s.cache.budget.physical_bytes, 0)

    def test_consumed_copy_space_is_not_reserved_again_during_frame_writes(self):
        usage = shutil.disk_usage(self.path.parent)
        calls = 0
        def free_space(_):
            nonlocal calls
            calls += 1
            # Simulate copying the source leaving only enough for the next
            # compressed frame. The already-consumed copy must not count twice.
            return usage._replace(free=(100 if calls == 1 else 70) * 1024**2)
        with patch('tofscope.storage.saved_files.shutil.disk_usage', side_effect=free_space):
            done = self.s.jobs.wait('a', self.submit().id, 5)
        self.assertEqual(done.status, 'succeeded', done.safe_error)

    def test_shared_queue_limit_applies_to_other_preparations(self):
        from tofscope.application.analyses import CapacityError
        from tofscope.application import preparations
        self.s.jobs.settings = replace(self.settings, jobs_global=1)
        with h5py.File(self.settings.data_root / 'b.h5', 'r+') as f:
            del f['PeakData/PeakData']
        second = self.s.preparations.inspect('b', 'b.h5')
        entered, release = Event(), Event()
        self.addCleanup(release.set)
        original = preparations.prepare_copy
        def pause(*args, **kwargs):
            # Pause before HDF5 access: pausing inside the integration kernel
            # holds h5py's global lock and blocks the second submission's inspect.
            entered.set()
            release.wait()
            return original(*args, **kwargs)
        with patch.object(preparations, 'prepare_copy', side_effect=pause):
            first = self.submit()
            try:
                self.assertTrue(entered.wait(5))
                self.assertEqual(self.s.jobs.get('a', first.id).status, 'running')
                with self.assertRaises(CapacityError):
                    self.s.preparations.submit('b', 'b.h5', 'acquisition', second.generation, 'second.h5')
            finally:
                release.set()
            self.assertEqual(self.s.jobs.wait('a', first.id, 5).status, 'succeeded')

    def test_changing_source_during_integration_prevents_publication(self):
        from tofscope.storage import raw_preparation
        original = raw_preparation.integrate_peak_table
        def change(*args, **kwargs):
            result = original(*args, **kwargs)
            os.utime(self.path, ns=(self.path.stat().st_atime_ns, self.path.stat().st_mtime_ns + 1000000))
            return result
        with patch.object(raw_preparation, 'integrate_peak_table', side_effect=change):
            done = self.s.jobs.wait('a', self.submit().id, 5)
        self.assertEqual(done.status, 'obsolete')
        self.assertEqual(self.s.saves.files.list('a'), [])
        self.assertEqual(self.s.cache.budget.physical_bytes, 0)

    def test_kernel_respects_event_batch_offsets_and_random_overlaps(self):
        from tofscope.science.integration import EventBatch
        events = EventBatch(np.array([999, 64, 128, 999, 192], dtype='uint32'),
                            np.array([1, 4]), np.array([2, 1]), (1, 2))
        np.testing.assert_array_equal(integrate_peak_table(events, np.arange(6.), 64, 4, [(1,3)]), [[[.5], [.25]]])
        rng = np.random.default_rng(5)
        cells = np.empty((3, 4), dtype=object)
        for idx in np.ndindex(cells.shape): cells[idx] = rng.integers(0, 600, size=40, dtype='uint32')
        windows = [(1., 3.), (2., 5.), (0., 2.), (1., 2.), (2., 4.)]
        actual = integrate_peak_table(cells, np.arange(6.), 64, 4, windows)
        for idx in np.ndindex(cells.shape):
            samples = cells[idx] // 64
            masses = np.arange(6.)[samples[samples < 6]]
            expected = [np.count_nonzero((masses >= lo) & (masses <= hi)) / 4 for lo,hi in windows]
            np.testing.assert_array_equal(actual[idx], expected)

    def test_prepared_copy_reclaims_unused_space_and_uses_channel_chunks(self):
        with h5py.File(self.path, 'r+') as f:
            # Keep a live object after the deleted allocation so the source
            # cannot simply truncate its unused tail on close.
            f.create_dataset('orphan', data=np.ones(4 * 1024**2, dtype='uint8'))
            f.create_dataset('tail', data=np.arange(10))
            del f['orphan']
            f['MassAlias'] = f['FullSpectra/MassAxis']
            f['AEventAlias'] = f['FullSpectra/EventList']
            f['SpectrumLink'] = h5py.SoftLink('/FullSpectra/SumSpectrum')
        before = self.path.stat().st_size
        done = self.s.jobs.wait('a', self.submit().id, 5)
        self.assertEqual(done.status, 'succeeded', done.safe_error)
        target = self.s.saves.files.path('a', done.saved_file.id)
        self.assertLess(target.stat().st_size, before / 2)
        with h5py.File(self.path, 'r') as src, h5py.File(target, 'r') as dst:
            peak = dst['PeakData/PeakData']
            self.assertEqual(peak.chunks, (1, 1, 2, 1))
            self.assertEqual(peak.compression, 'gzip')
            self.assertEqual(peak.compression_opts, 1)
            self.assertFalse(peak.shuffle)
            self.assertEqual(dst['MassAlias'].id, dst['FullSpectra/MassAxis'].id)
            self.assertEqual(dst['AEventAlias'].id, dst['FullSpectra/EventList'].id)
            self.assertIsInstance(dst.get('SpectrumLink', getlink=True), h5py.SoftLink)
            np.testing.assert_array_equal(dst['tail'][:], src['tail'][:])
            for idx in np.ndindex(src['FullSpectra/EventList'].shape):
                np.testing.assert_array_equal(dst['FullSpectra/EventList'][idx], src['FullSpectra/EventList'][idx])

    def test_compact_copy_remaps_object_and_region_attributes(self):
        with h5py.File(self.path, 'r+') as f:
            tail = f.create_dataset('tail', data=np.arange(10))
            f.attrs['dataset_ref'] = tail.ref
            tail.attrs['group_ref'] = f['FullSpectra'].ref
            tail.attrs['region_ref'] = tail.regionref[2:7:2]
            compound = np.zeros((), dtype=[('targets', h5py.ref_dtype, (2,)), ('index', 'i4')])
            compound['targets'][0] = tail.ref
            compound['targets'][1] = f['FullSpectra'].ref
            compound['index'] = 7
            f.attrs['compound_refs'] = compound
            f.attrs.create('array_refs', np.array([tail.ref, tail.ref], dtype=h5py.ref_dtype),
                           dtype=np.dtype((h5py.ref_dtype, (2,))))
            f.attrs.create('array_numbers', np.array([2, 9], dtype='i4'),
                           dtype=np.dtype(('i4', (2,))))
        done = self.s.jobs.wait('a', self.submit().id, 5)
        self.assertEqual(done.status, 'succeeded', done.safe_error)
        target = self.s.saves.files.path('a', done.saved_file.id)
        with h5py.File(target, 'r') as f:
            self.assertEqual(f[f.attrs['dataset_ref']].name, '/tail')
            refs = f.attrs['compound_refs']
            self.assertEqual(f[refs['targets'][0]].name, '/tail')
            self.assertEqual(f[refs['targets'][1]].name, '/FullSpectra')
            self.assertEqual(refs['index'], 7)
            self.assertEqual(f[f.attrs['array_refs'][1]].name, '/tail')
            self.assertEqual(f.attrs.get_id('array_refs').shape, ())
            np.testing.assert_array_equal(f.attrs['array_numbers'], [2, 9])
            self.assertEqual(f.attrs.get_id('array_numbers').dtype.subdtype, (np.dtype('i4'), (2,)))
            self.assertEqual(f[f['tail'].attrs['group_ref']].name, '/FullSpectra')
            np.testing.assert_array_equal(f['tail'][f['tail'].attrs['region_ref']], [2, 4, 6])

    def test_compact_metadata_string_limit_rejects_without_publishing(self):
        from tofscope.storage.compact_copy import ATTRIBUTE_STRING_BYTES
        with h5py.File(self.path, 'r+') as f:
            f.attrs['oversized_note'] = 'x' * (ATTRIBUTE_STRING_BYTES + 10)
        done = self.s.jobs.wait('a', self.submit().id, 5)
        self.assertEqual(done.status, 'failed')
        self.assertEqual(self.s.saves.files.list('a'), [])
        self.assertFalse(list(self.s.saves.files.owner_root('a').glob('.tmp-*')))
        self.assertEqual(self.s.cache.budget.physical_bytes, 0)

    def test_compact_copy_preserves_unicode_metadata(self):
        with h5py.File(self.path, 'r+') as f:
            f.attrs['notes'] = 'Platinum α — measurement'
        done = self.s.jobs.wait('a', self.submit().id, 5)
        self.assertEqual(done.status, 'succeeded', done.safe_error)
        with h5py.File(self.s.saves.files.path('a', done.saved_file.id), 'r') as f:
            self.assertEqual(f.attrs['notes'], 'Platinum α — measurement')

    def test_cancellation_during_compact_copy_leaves_no_result(self):
        from tofscope.storage import compact_copy
        original = compact_copy.write_events
        entered, release = Event(), Event()
        self.addCleanup(release.set)
        def pause(*args, **kwargs):
            entered.set(); release.wait(3)
            return original(*args, **kwargs)
        with patch.object(compact_copy, 'write_events', side_effect=pause):
            job = self.submit()
            self.assertTrue(entered.wait(2))
            self.s.jobs.cancel('a', job.id)
            release.set()
            self.assertEqual(self.s.jobs.wait('a', job.id, 5).status, 'cancelled')
        self.assertEqual(self.s.saves.files.list('a'), [])
        self.assertFalse(list(self.s.saves.files.owner_root('a').glob('.tmp-*')))
        self.assertEqual(self.s.cache.budget.physical_bytes, 0)
