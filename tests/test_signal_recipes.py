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

from integration import custom_peak_windows
from signals import SignalRecipe,read_signal
from explorer import custom_peak,integrate_events
from workspace import ExplorerWorkspace


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

    def test_comparison_missing_on_both_sides_with_nonzero_frame_origin(self):
        with patch('workspace.get_plotlyjs',return_value=''),patch.object(ExplorerWorkspace,'figures',return_value={}):
            w=ExplorerWorkspace(self.path);w.send=Mock();w.frames=(9,13)
            w.meta['shape']=(14,1,2,1)
            with patch('workspace.read_signal',return_value=np.array([1.,2.,3.],dtype=np.float32)[:,None,None]*np.ones((1,1,2))):
                w.handle_message(None,dict(event='comparison_add',payload=dict(intervals=[[1,2],[4,5]],frames=[10,12])),None)
            self.assertNotIn('error',w.send.call_args.args[0])
            np.testing.assert_allclose(w.comparison_curves()[0][1],[np.nan,1.,2.,3.,np.nan],equal_nan=True)

    def test_invalid_input_and_source_unchanged(self):
        before=self.path.read_bytes()
        for intervals in [[],[(1,7)],[(4,2)]]:
            with self.assertRaises(ValueError):custom_peak_windows(self.path,intervals,0,2)
        custom_peak_windows(self.path,[(1,2),(4,5)],0,2)
        self.assertEqual(self.path.read_bytes(),before)

    def test_controller_applies_composite_and_exports_every_interval(self):
        with patch('workspace.get_plotlyjs',return_value=''),patch.object(ExplorerWorkspace,'figures',return_value={}):
            w=ExplorerWorkspace(self.path);w.send=Mock()
            w.handle_message(None,dict(event='integrate',payload=dict(intervals=[[1,2],[4,5]],frames=[1,2])),None)
            response=w.send.call_args.args[0];self.assertNotIn('error',response,response)
            np.testing.assert_array_equal(w.volume[:,0,:],[[1,.5],[1,.75]])
            self.assertEqual(w.active_recipe.intervals,((1.,2.),(4.,5.)))
            self.assertIsNone(response['state']['low'])
            w.export('json');recipe=json.loads(w.send.call_args.args[0]['download']['text'])
            self.assertEqual(recipe['schema_version'],3)
            self.assertEqual(recipe['intervals'],[[1,2],[4,5]])
            w.export('csv');rows=list(csv.reader(io.StringIO(w.send.call_args.args[0]['download']['text'])))
            self.assertEqual(rows[1],['1','0.75'])
            self.assertEqual(rows[2],['2','0.875'])
            active=w.volume
            w.handle_message(None,dict(event='integrate',payload=dict(intervals=[],frames=[0,2])),None)
            self.assertIn('error',w.send.call_args.args[0]);self.assertIs(w.volume,active)

    def test_comparison_union_and_partial_coverage_survive_primary_switch(self):
        with patch('workspace.get_plotlyjs',return_value=''),patch.object(ExplorerWorkspace,'figures',return_value={}):
            w=ExplorerWorkspace(self.path);w.send=Mock()
            w.handle_message(None,dict(event='comparison_add',payload=dict(intervals=[[1,2],[4,5]],frames=[1,2])),None)
            self.assertNotIn('error',w.send.call_args.args[0])
            curve=w.comparison_curves()[0][1]
            np.testing.assert_allclose(curve,[np.nan,.75,.875],equal_nan=True)
            self.assertEqual(w.comparisons[0]['recipe']['intervals'],[[1,2],[4,5]])
            w.roi=(1,1,0,0)
            np.testing.assert_allclose(w.comparison_curves()[0][1],[np.nan,.5,.75],equal_nan=True)
