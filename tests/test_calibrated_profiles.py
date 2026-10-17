"""Calibration changes coordinates and exports without resampling counts."""
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
import numpy as np
from depth_calibration import DepthAnchor,DepthCalibration
from plots import profile_plot
from workspace import ExplorerWorkspace
from test_signal_recipes import make_acquisition


class CalibratedProfileTests(unittest.TestCase):
    def test_profile_preserves_intensities_and_absolute_frames(self):
        data=np.arange(201.,dtype=float)[:,None,None]
        comparison=np.full(201,np.nan);comparison[10:20]=7
        c=DepthCalibration((DepthAnchor(0,0),DepthAnchor(100,50),DepthAnchor(200,150)),301)
        frame,values=profile_plot(data,(100,300),(0,0,0,0),150,'ion',[('other',comparison,'red')])
        depth,calibrated=profile_plot(data,(100,300),(0,0,0,0),150,'ion',[('other',comparison,'red')],calibration=c,unit='nm')
        np.testing.assert_array_equal(values,calibrated)
        for a,b in zip(frame.data,depth.data):np.testing.assert_array_equal(a.y,b.y)
        np.testing.assert_array_equal(depth.data[0].customdata,np.arange(100,301))
        np.testing.assert_allclose(np.asarray(depth.data[0].x)[:3],[50,51,52])
        self.assertTrue(np.isnan(np.asarray(depth.data[0].x)[101:]).all())
        self.assertEqual(depth.layout.meta['axis_kind'],'depth');self.assertEqual(depth.layout.shapes[0].x0,100)

    def test_one_calibrated_sample_is_visible(self):
        c=DepthCalibration((DepthAnchor(0,0),DepthAnchor(100,50)),301)
        fig,_=profile_plot(np.ones((201,1,1)),(100,300),(0,0,0,0),100,'ion',calibration=c)
        self.assertIn('markers',fig.data[0].mode)

    def test_controller_export_partial_depth_and_anchor_validation(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        path=Path(temp.name)/'a.h5';make_acquisition(path)
        with patch('workspace.get_plotlyjs',return_value=''),patch.object(ExplorerWorkspace,'figures',return_value={}):w=ExplorerWorkspace(path)
        w.send=Mock();original=w.volume
        def event(name,**payload):
            w.handle_message(None,dict(event=name,payload=payload),None)
            result=w.send.call_args.args[0];self.assertNotIn('error',result,result);return result
        response=event('depth_anchor_set',frame=1,depth=.1,unit='µm',request_id=17)
        self.assertEqual(response['depth_request_id'],17)
        event('profile_axis',axis='depth')
        event('depth_unit',unit='µm')
        self.assertIs(w.volume,original);self.assertEqual(w.state()['depth_calibration']['anchors'][1]['depth_nm'],100)
        event('export',format='csv');rows=list(csv.DictReader(io.StringIO(w.send.call_args.args[0]['download']['text'])))
        self.assertEqual([r['depth_nm'] for r in rows],['0','100',''])
        self.assertEqual([r['roi_mean_intensity'] for r in rows],['0.5','2.5','4.5'])
        event('export',format='json');recipe=json.loads(w.send.call_args.args[0]['download']['text'])
        self.assertEqual(recipe['depth_calibration']['unit'],'µm');self.assertFalse(recipe['depth_calibration']['extrapolation'])
        before=w.calibration
        for payload in [dict(frame=0,depth=4,unit='nm'),dict(frame=2,depth=99,unit='nm')]:
            w.handle_message(None,dict(event='depth_anchor_set',payload=payload),None)
            self.assertIn('error',w.send.call_args.args[0]);self.assertIs(w.calibration,before)
        event('depth_anchor_remove',frame=1)
        self.assertIsNone(w.calibration);self.assertEqual(w.state()['profile_axis'],'frame')
        w.handle_message(None,dict(event='depth_anchor_remove',payload=dict(frame=0)),None)
        self.assertIn('error',w.send.call_args.args[0]);self.assertEqual(len(w.depth_anchors),1)
