"""Multi-ion previews share a bounded acquisition-coordinate block grid."""
import unittest
from unittest.mock import patch
import numpy as np
from tofscope.science.signals import SignalRecipe
from tofscope.science.volume_layers import VolumeLayer,build_layer_previews,clear_preview_cache


class VolumeLayerTests(unittest.TestCase):
    def setUp(self):clear_preview_cache()
    def layer(self,frames,label='ion'):
        return VolumeLayer(label,SignalRecipe(intervals=((1,2),),frames=frames,label=label))
    def test_absolute_alignment_and_missing_coverage(self):
        a,b=self.layer((10,14),'a'),self.layer((12,14),'b')
        arrays={a.id:np.array([0,0,9,0,0.])[:,None,None]*np.ones((1,3,3)),b.id:np.array([9,0,0.])[:,None,None]*np.ones((1,3,3))}
        with patch('tofscope.science.volume_layers.inspect_file',return_value=dict(shape=(20,3,3,1),fov_um=30)),patch('tofscope.science.volume_layers.file_key',return_value=('fixture',1,1)),patch('tofscope.science.volume_layers.read_signal',side_effect=lambda path,r:arrays[r.label]):
            results=build_layer_previews('fixture',[a,b],(1,2,1,2),(10,14),quality='Fast')
        np.testing.assert_array_equal(results[0].grid.z,[10,11,12,13,14]);np.testing.assert_array_equal(results[0].grid.x,[15,25])
        np.testing.assert_array_equal(results[0].values[2],results[1].values[2]);self.assertTrue(np.isnan(results[1].values[:2]).all())
        self.assertTrue((results[1].coverage[:2]==0).all())

    def test_budget_partial_means_and_style_cache(self):
        a=self.layer((0,4));data=np.arange(45.).reshape(5,3,3)
        with patch('tofscope.science.volume_layers.inspect_file',return_value=dict(shape=(5,3,3,1),fov_um=None)),patch('tofscope.science.volume_layers.file_key',return_value=('fixture',1,1)),patch('tofscope.science.volume_layers.read_signal',return_value=data) as reader:
            result=build_layer_previews('fixture',[a],(0,2,0,2),(0,4),quality='Fast',voxel_budget=4)[0]
            self.assertLessEqual(result.values.size,4)
            # Weighted sum of all block means equals sum of source values.
            self.assertAlmostEqual(float((result.values*result.valid_counts).sum()),990)
            a.colorscale='Reds';a.opacity=.5
            again=build_layer_previews('fixture',[a],(0,2,0,2),(0,4),quality='Fast',voxel_budget=4)[0]
            self.assertEqual(reader.call_count,1);np.testing.assert_array_equal(result.values,again.values)

    def test_many_layers_total_budget_and_invisible_work(self):
        layers=[self.layer((0,9),str(i)) for i in range(7)];layers[-1].visible=False
        with patch('tofscope.science.volume_layers.inspect_file',return_value=dict(shape=(10,8,8,1),fov_um=None)),patch('tofscope.science.volume_layers.file_key',return_value=('fixture',1,1)),patch('tofscope.science.volume_layers.read_signal',return_value=np.ones((10,8,8))) as reader:
            results=build_layer_previews('fixture',layers,(0,7,0,7),(0,9),quality='Fast',voxel_budget=100)
            self.assertLessEqual(sum(p.values.size for p in results),100);self.assertEqual(len(results),6)
            self.assertTrue(all(np.all(p.values==1) for p in results));self.assertEqual(reader.call_count,1)

    def test_calibrated_block_means_and_clipping_before_pooling(self):
        from tofscope.science.depth_calibration import DepthCalibration, DepthAnchor
        a = self.layer((0,5))
        data = np.arange(6., dtype=np.float32)[:,None,None]
        calibration = DepthCalibration((DepthAnchor(0,0),DepthAnchor(2,20),DepthAnchor(4,60)),6)
        with patch('tofscope.science.volume_layers.inspect_file',return_value=dict(shape=(6,1,1,1),fov_um=None)),patch('tofscope.science.volume_layers.file_key',return_value=('calibration',1,1)):
            p=build_layer_previews('fixture',[a],(0,0,0,0),(0,5),quality='Fast',voxel_budget=3,reader=lambda *args:data,calibration=calibration)[0]
        np.testing.assert_array_equal(p.grid.z,[5,30,60])
        np.testing.assert_array_equal(p.values[:,0,0],[.5,2.5,4])
        # An anchor lies inside this block: depth(mean frame) is 20, but
        # the mean of calibrated samples is 26. Geometry must use the latter.
        with patch('tofscope.science.volume_layers.inspect_file',return_value=dict(shape=(6,1,1,1),fov_um=None)),patch('tofscope.science.volume_layers.file_key',return_value=('calibration',1,1)):
            pooled=build_layer_previews('fixture',[a],(0,0,0,0),(0,5),quality='Fast',voxel_budget=1,reader=lambda *args:data,calibration=calibration)[0]
        np.testing.assert_array_equal(pooled.grid.z,[26])


    def test_quality_limits(self):
        a=self.layer((0,199))
        with patch('tofscope.science.volume_layers.inspect_file',return_value=dict(shape=(200,49,49,1),fov_um=None)),patch('tofscope.science.volume_layers.file_key',return_value=('limits',1,1)):
            for quality,limits in [('Fast',(96,32,32)),('Detailed',(160,48,48))]:
                p=build_layer_previews('fixture',[a],(0,48,0,48),(0,199),quality=quality,reader=lambda *args:np.ones((200,49,49)))[0]
                self.assertTrue(all(n<=limit for n,limit in zip(p.values.shape,limits)))

    def test_nonfinite_samples_are_excluded_from_partial_block_mean(self):
        a=self.layer((0,2))
        with patch('tofscope.science.volume_layers.inspect_file',return_value=dict(shape=(3,1,1,1),fov_um=None)),patch('tofscope.science.volume_layers.file_key',return_value=('missing',1,1)):
            p=build_layer_previews('fixture',[a],(0,0,0,0),(0,2),quality='Fast',voxel_budget=1,reader=lambda *args:np.array([2,np.nan,8])[:,None,None])[0]
        self.assertEqual(float(p.values[0,0,0]),5.)
        self.assertEqual(int(p.valid_counts[0,0,0]),2)
        self.assertAlmostEqual(float(p.coverage[0,0,0]),2/3,places=6)
