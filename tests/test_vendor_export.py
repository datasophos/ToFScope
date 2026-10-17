"""Native copies append eligible channels without altering the source cube."""
import tempfile
import unittest
from pathlib import Path
import h5py
import numpy as np
from signals import SignalRecipe
from vendor_export import export_native_copy
from test_signal_recipes import make_acquisition


class NativeExportTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.source=self.root/'source.h5';make_acquisition(self.source)
        with h5py.File(self.source,'r+') as f:
            f.create_group('TimingData');f.create_group('AcquisitionLog');f.attrs['TofDAQ Version']=[1.99];f.attrs['NbrWrites']=3

    def test_native_copy_round_trip_and_official_reader(self):
        recipe=SignalRecipe(intervals=((1,2),),frames=(0,2),label='ToFScope_test')
        destination=self.root/'native.h5';source_bytes=self.source.read_bytes()
        export_native_copy(self.source,destination,[recipe])
        self.assertEqual(self.source.read_bytes(),source_bytes)
        with h5py.File(self.source,'r') as original,h5py.File(destination,'r') as saved:
            self.assertEqual(saved['PeakData/PeakData'].shape,(3,1,2,2));self.assertEqual(saved.attrs['NbrPeaks'],2)
            np.testing.assert_array_equal(saved['PeakData/PeakData'][:,:,:,:1],original['PeakData/PeakData'][:])
            np.testing.assert_array_equal(saved['PeakData/PeakData'][:,:,:,1],[[[.75,0]],[[.75,.25]],[[.75,.5]]])
            self.assertEqual(saved['PeakData/PeakTable'][1]['label'],b'ToFScope_test')
        from rsciio.tofwerk import file_reader
        rows=file_reader(destination,signal='additional_peak_data',lazy=False,show_progressbar=False)
        self.assertTrue(rows);self.assertEqual(rows[0]['data'].shape[-1],1)
        np.testing.assert_array_equal(rows[0]['data'][...,0],[[[.75,0]],[[.75,.25]],[[.75,.5]]])

    def test_reject_semantic_shortcuts_and_existing_destination(self):
        for recipe in [SignalRecipe(intervals=((1,2),(4,5)),frames=(0,2)),SignalRecipe(intervals=((1,2),),frames=(1,2))]:
            with self.assertRaises(ValueError):export_native_copy(self.source,self.root/'bad.h5',[recipe])
        destination=self.root/'existing.h5';destination.write_bytes(b'keep')
        recipe=SignalRecipe(intervals=((1,2),),frames=(0,2),label='test')
        with self.assertRaises(FileExistsError):export_native_copy(self.source,destination,[recipe])
        self.assertEqual(destination.read_bytes(),b'keep')
