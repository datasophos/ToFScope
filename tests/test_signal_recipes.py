"""Streamed multi-window reads and controller/export coverage on disposable data."""
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock

import h5py
import numpy as np

from tofscope.science.integration import custom_peak_windows
from tofscope.science.signals import SignalRecipe,read_signal
from tofscope.storage.explorer import custom_peak,integrate_events



def make_acquisition(path):
    with h5py.File(path,'w') as f:
        f.attrs['NbrWaveforms']=2
        f.attrs['Configuration File Contents']=b'Ch1Record=1\nCh2Record=1'
        fs=f.create_group('FullSpectra');fs.attrs['SampleInterval']=64.;fs.attrs['ClockPeriod']=1.
        fs.create_dataset('MassAxis',data=np.arange(6.));fs.create_dataset('SumSpectrum',data=np.ones(6))
        raw=fs.create_dataset('EventList',(4,1,2),dtype=h5py.vlen_dtype(np.dtype('uint32')))
        for z in range(4):
            raw[z,0,0]=np.array([1,2,2,3,4],dtype=np.uint32)*64
            raw[z,0,1]=np.array([1]*z+[3,5],dtype=np.uint32)*64
        peak=f.create_group('PeakData')
        peak.create_dataset('PeakData',data=np.arange(6,dtype=np.float32).reshape(3,1,2,1))
        dtype=np.dtype([('label','S64'),('mass','f4'),('lower integration limit','f4'),('upper integration limit','f4')])
        peak.create_dataset('PeakTable',data=np.array([(b'nominal',2.,1.,3.)],dtype=dtype))


class SignalReadTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'acquisition.h5';make_acquisition(self.path)

    def test_composite_excludes_gap_and_reads_each_frame_once(self):
        progress=[]
        result=custom_peak_windows(self.path,[(1,2),(4,5)],0,2,lambda done,total:progress.append((done,total)))
        np.testing.assert_array_equal(result[:,0,:],[[1,.25],[1,.5],[1,.75]])
        self.assertEqual(progress,[(1,3),(2,3),(3,3)])

    def test_one_interval_matches_existing_integrator_and_never_reads_extra_write(self):
        with h5py.File(self.path,'r') as f:
            expected=np.stack([integrate_events(f['FullSpectra/EventList'][z],np.arange(6.),64,4,1,3) for z in range(3)])
        np.testing.assert_array_equal(custom_peak(self.path,1,3,0,2),expected)
        with self.assertRaises(ValueError):custom_peak_windows(self.path,[(1,2)],0,3)

    def test_reader_crops_stored_and_custom_to_absolute_frames(self):
        stored=SignalRecipe(source='stored',stored_index=0,intervals=((1,3),),frames=(1,2))
        np.testing.assert_array_equal(read_signal(self.path,stored)[:,0,:],[[2,3],[4,5]])
        custom=SignalRecipe(source='custom',intervals=((1,2),(4,5)),frames=(1,2))
        np.testing.assert_array_equal(read_signal(self.path,custom)[:,0,:],[[1,.5],[1,.75]])
        with self.assertRaises(ValueError):read_signal(self.path,SignalRecipe(source='custom',intervals=((1,2),),frames=(0,3)))


    def test_invalid_input_and_source_unchanged(self):
        before=self.path.read_bytes()
        for intervals in [[],[(1,7)],[(4,2)]]:
            with self.assertRaises(ValueError):custom_peak_windows(self.path,intervals,0,2)
        custom_peak_windows(self.path,[(1,2),(4,5)],0,2)
        self.assertEqual(self.path.read_bytes(),before)


