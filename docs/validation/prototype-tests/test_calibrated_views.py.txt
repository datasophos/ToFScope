"""Physical depth changes geometry, never measured signal or frame selection."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
import numpy as np
from depth_calibration import DepthAnchor,DepthCalibration
from plots import cross_section,front_projection,volume_plot,overlay_volume_plot,tiled_volume_plot
from volume_layers import VolumeLayer,build_layer_previews
from signals import SignalRecipe
from workspace import ExplorerWorkspace
from test_signal_recipes import make_acquisition


class CalibratedViewTests(unittest.TestCase):
    def test_sections_and_front_keep_values_and_original_frames(self):
        values=np.arange(20,dtype=np.float32).reshape(5,2,2)
        c=DepthCalibration((DepthAnchor(0,0),DepthAnchor(100,50),DepthAnchor(102,150)),105)
        for function,args,expected in [
            (cross_section,('XZ',20,False,20),values[:3,0,:]),
            (cross_section,('YZ',20,False,20),values[:3,:,0]),
            (front_projection,(20,False),values[:3].sum(axis=1))]:
            with self.subTest(view=function.__name__,args=args):
                fig=function(values,(100,104),(0,1,0,1),*args,calibration=c,unit='µm')
                np.testing.assert_allclose(fig.data[0].y,[.05,.1,.15])
                np.testing.assert_array_equal(fig.data[0].z,expected)
                np.testing.assert_array_equal(fig.data[0].customdata,expected)
                np.testing.assert_array_equal(np.asarray(fig.data[0].text)[:,0],[100,101,102])
                self.assertEqual(fig.layout.yaxis.title.text,'Depth (µm)')
                self.assertEqual(fig.layout.meta['omitted_frames'],2)
        empty=cross_section(values,(103,107),(0,1,0,1),'XZ',20,False,20,calibration=c)
        self.assertFalse(empty.data);self.assertIn('No calibrated depth',empty.layout.annotations[0].text)

    def test_volume_pooling_averages_physical_coordinates_across_anchor_kinks(self):
        values=np.broadcast_to(np.arange(1,202,dtype=np.float32)[:,None,None],(201,2,2))
        c=DepthCalibration((DepthAnchor(0,0),DepthAnchor(1,10),DepthAnchor(200,209)),201)
        fig,shape=volume_plot(values,(0,200),(0,1,0,1),1,log=False,stretch=1,calibration=c)
        self.assertEqual(shape,(67,2,2));self.assertEqual(fig.data[0].z[0],7)
        self.assertEqual(fig.data[0].value[0],2)
        self.assertEqual(fig.layout.scene.zaxis.title.text,'Depth (nm)')
        self.assertAlmostEqual(fig.layout.scene.aspectratio.z,.209)
        self.assertEqual(fig.layout.meta['physical_aspect'],True)

    def test_volume_omits_unknown_frames_before_pooling(self):
        values=np.tile(np.array([[1,2],[3,4]],dtype=np.float32),(201,1,1));values[101:]=10000
        c=DepthCalibration((DepthAnchor(0,0),DepthAnchor(100,100)),201)
        fig,shape=volume_plot(values,(0,200),(0,1,0,1),20,log=False,calibration=c)
        self.assertEqual(shape[0],51);self.assertLessEqual(max(fig.data[0].value),4)
        self.assertEqual(fig.layout.meta['display_frames'],[0,100])
        self.assertEqual(fig.layout.meta['omitted_frames'],100)
        empty,shape=volume_plot(values[:10],(150,159),(0,1,0,1),20,calibration=c)
        self.assertEqual(shape,(0,0,0));self.assertFalse(empty.data)

    def test_single_calibrated_plane_does_not_claim_known_thickness(self):
        c=DepthCalibration((DepthAnchor(0,0),DepthAnchor(2,100)),3)
        fig,_=volume_plot(np.ones((1,2,2)),(1,1),(0,1,0,1),20,calibration=c)
        self.assertFalse(fig.layout.meta['physical_aspect'])
        self.assertEqual(set(fig.data[0].z),{50})
        self.assertTrue(any('thickness' in a.text for a in fig.layout.annotations))

    def test_layered_previews_clip_and_use_common_physical_depth(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'a.h5';make_acquisition(path)
            recipe=SignalRecipe(source='stored',stored_index=0,intervals=((1,3),),frames=(0,2),label='ion')
            styles=[VolumeLayer('a',recipe,percentile=0),VolumeLayer('b',recipe,percentile=0)]
            c=DepthCalibration((DepthAnchor(0,0),DepthAnchor(1,100)),3)
            previews=build_layer_previews(path,styles,(0,1,0,0),(0,2),quality='Fast',calibration=c)
            self.assertEqual(previews[0].values.shape,(2,1,2))
            for constructor in [overlay_volume_plot,tiled_volume_plot]:
                fig=constructor(previews,styles,calibration=c,unit='µm',stretch=1,log=False)
                self.assertEqual(set(fig.data[0].z),{0.,.1})
                self.assertEqual(fig.layout.scene.zaxis.title.text,'Depth (µm)')
                self.assertFalse(fig.layout.meta['physical_aspect']) # Fixture has no FOV.

    def test_controller_updates_all_views_and_physical_markers(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'a.h5';make_acquisition(path)
            with patch('workspace.get_plotlyjs',return_value=''):w=ExplorerWorkspace(path)
            w.send=Mock();original=w.volume
            def event(name,**payload):
                w.handle_message(None,dict(event=name,payload=payload),None)
                response=w.send.call_args.args[0];self.assertNotIn('error',response,response);return response
            event('depth_anchor_set',frame=1,depth=100,unit='nm')
            response=event('profile_axis',axis='depth')
            self.assertTrue({'front','xz','yz','volume','profile'}<=response['figures'].keys())
            self.assertEqual(w.state()['stretch'],1)
            self.assertIs(w.volume,original)
            event('depth_unit',unit='µm');response=event('frame',frame=1)
            for key in ['xz','yz','front']:
                patch_values=response['relayout'][key]
                self.assertIn(.1,patch_values.values())
            response=event('frame',frame=2)
            for key in ['xz','yz','front']:self.assertIn(False,response['relayout'][key].values())
            response=event('depth_anchor_remove',frame=1)
            self.assertEqual(response['figures']['xz']['layout']['yaxis']['title']['text'],'Depth frame')
