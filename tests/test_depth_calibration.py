"""Depth coordinates preserve acquisition frames and never extrapolate."""
import unittest
import numpy as np
from tofscope.science.depth_calibration import DepthAnchor,DepthCalibration,validate_anchors,convert_depth


class DepthCalibrationTests(unittest.TestCase):
    def test_piecewise_depth(self):
        c=DepthCalibration((DepthAnchor(300,250),DepthAnchor(0,0),DepthAnchor(100,50)),401)
        frames=np.array([0,50,100,200,300])
        expected=np.array([0,25,50,150,250])
        np.testing.assert_array_equal(c.frame_to_depth(frames),expected)
        np.testing.assert_array_equal(c.depth_to_frame(expected),frames)
        self.assertEqual(float(c.depth_to_frame(np.array(25.5))),51)
        self.assertTrue(np.isnan(c.frame_to_depth(np.array([-1,301]))).all())
        self.assertTrue(np.isnan(c.depth_to_frame(np.array([-1,251]))).all())

    def test_fixed_origin_and_invalid_anchors(self):
        self.assertEqual(validate_anchors([],401),(DepthAnchor(0,0.),))
        self.assertEqual(validate_anchors([DepthAnchor(100,50)],401),(DepthAnchor(0,0.),DepthAnchor(100,50)))
        for anchors in [[DepthAnchor(0,1)],[DepthAnchor(0,-1)], [DepthAnchor(100,-10)], [DepthAnchor(100,10),DepthAnchor(100,20)], [DepthAnchor(100,10),DepthAnchor(200,10)], [DepthAnchor(401,10)], [DepthAnchor(-1,10)], [DepthAnchor(1.5,10)], [DepthAnchor(True,10)], [DepthAnchor(1,float('nan'))]]:
            with self.subTest(anchors=anchors),self.assertRaises(ValueError):validate_anchors(anchors,401)
        with self.assertRaises(ValueError):DepthCalibration((),401)
        with self.assertRaises(ValueError):DepthCalibration((DepthAnchor(0,0),),0)

    def test_units_and_round_trip(self):
        for unit in ('µm','um'):
            self.assertEqual(convert_depth(1,unit,'nm'),1000)
        self.assertEqual(convert_depth(1,'mm','nm'),1e6)
        with self.assertRaises(ValueError):convert_depth(1,'m','nm')
        c=DepthCalibration((DepthAnchor(0,0),DepthAnchor(200,1500)),301)
        data=c.to_dict(unit='µm');restored=DepthCalibration.from_dict(data)
        self.assertEqual(restored,c);self.assertEqual(data['unit'],'µm')
        self.assertEqual(data['anchors'][1],dict(frame=200,depth_nm=1500))
        self.assertEqual(c.anchors[1].depth_nm,1500)
