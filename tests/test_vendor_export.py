"""Native copies append eligible channels without altering the source cube."""
import tempfile
import unittest
from pathlib import Path
import h5py
import numpy as np
import subprocess
import sys
from filelock import Timeout
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

    def test_sparse_compressed_chunks_and_link_cycles(self):
        with h5py.File(self.source,'r+') as f:
            del f['PeakData/PeakData']
            data=f['PeakData'].create_dataset('PeakData',shape=(3,1,2,1),dtype='float32',chunks=(1,1,2,1),compression='gzip',fillvalue=7)
            data[0]=3
        recipe=SignalRecipe(intervals=((1,2),),frames=(0,2),label='test')
        destination=self.root/'sparse.h5';export_native_copy(self.source,destination,[recipe])
        with h5py.File(self.source,'r') as a,h5py.File(destination,'r') as b:
            self.assertEqual(a['PeakData/PeakData'].id.read_direct_chunk((0,0,0,0)),b['PeakData/PeakData'].id.read_direct_chunk((0,0,0,0)))
            np.testing.assert_array_equal(a['PeakData/PeakData'][:],b['PeakData/PeakData'][:,:,:,:1])
        with h5py.File(self.source,'r+') as f:f['cycle']=f['/']
        with self.assertRaises(ValueError):export_native_copy(self.source,self.root/'cycle.h5',[recipe])

    def test_rejects_nested_references_attributes_and_external_storage(self):
        from vendor_export import validate_native_layout
        with h5py.File(self.source,'r+') as f:
            dtype=np.dtype([('target',h5py.ref_dtype),('number','i4')])
            data=np.zeros(1,dtype=dtype);data['target'][0]=f['FullSpectra/MassAxis'].ref
            f.create_dataset('references',data=data)
            with self.subTest(kind='compound dataset'),self.assertRaises(ValueError):validate_native_layout(f)
            del f['references']
            f.attrs['axis_reference']=f['FullSpectra/MassAxis'].ref
            with self.subTest(kind='root reference attribute'),self.assertRaises(ValueError):validate_native_layout(f)
            del f.attrs['axis_reference']
            f.attrs.create('compound_reference',data,dtype=dtype)
            with self.subTest(kind='compound attribute'),self.assertRaises(ValueError):validate_native_layout(f)
            del f.attrs['compound_reference']
            f.create_dataset('external',shape=(2,),dtype='float32',external=[(str(self.root/'external.bin'),0,8)])
            with self.subTest(kind='external dataset'),self.assertRaises(ValueError):validate_native_layout(f)
            del f['external']
            layout=h5py.VirtualLayout(shape=(6,),dtype='float64')
            layout[:]=h5py.VirtualSource(str(self.root/'external.h5'),'axis',shape=(6,))
            f.create_virtual_dataset('virtual',layout)
            with self.subTest(kind='virtual dataset'),self.assertRaises(ValueError):validate_native_layout(f)

    def test_public_copy_obeys_source_lock_even_with_prepared_values(self):
        script="from dataset_io import dataset_lock;import sys,time\nwith dataset_lock(sys.argv[1]):\n print('locked',flush=True)\n time.sleep(.6)"
        process=subprocess.Popen([sys.executable,'-c',script,str(self.source)],stdout=subprocess.PIPE,text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(),'locked')
            recipe=SignalRecipe(intervals=((1,2),),frames=(0,2),label='test')
            with self.assertRaises(Timeout):export_native_copy(self.source,self.root/'locked.h5',[recipe],volumes=[np.ones((3,1,2),dtype=np.float32)])
        finally:process.wait(timeout=3);process.stdout.close()
