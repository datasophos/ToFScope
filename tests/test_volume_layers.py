"""Multi-ion previews share a bounded acquisition-coordinate block grid."""
import unittest
from unittest.mock import patch
import numpy as np
from signals import SignalRecipe
from volume_layers import VolumeLayer,build_layer_previews,clear_preview_cache


class VolumeLayerTests(unittest.TestCase):
    def setUp(self):clear_preview_cache()
    def layer(self,frames,label='ion'):
        return VolumeLayer(label,SignalRecipe(intervals=((1,2),),frames=frames,label=label))
    def test_absolute_alignment_and_missing_coverage(self):
        a,b=self.layer((10,14),'a'),self.layer((12,14),'b')
        arrays={a.id:np.array([0,0,9,0,0.])[:,None,None]*np.ones((1,3,3)),b.id:np.array([9,0,0.])[:,None,None]*np.ones((1,3,3))}
        with patch('volume_layers.inspect_file',return_value=dict(shape=(20,3,3,1),fov_um=30)),patch('volume_layers.file_key',return_value=('fixture',1,1)),patch('volume_layers.read_signal',side_effect=lambda path,r:arrays[r.label]):
            results=build_layer_previews('fixture',[a,b],(1,2,1,2),(10,14),quality='Fast')
        np.testing.assert_array_equal(results[0].grid.z,[10,11,12,13,14]);np.testing.assert_array_equal(results[0].grid.x,[15,25])
        np.testing.assert_array_equal(results[0].values[2],results[1].values[2]);self.assertTrue(np.isnan(results[1].values[:2]).all())
        self.assertTrue((results[1].coverage[:2]==0).all())

    def test_budget_partial_means_and_style_cache(self):
        a=self.layer((0,4));data=np.arange(45.).reshape(5,3,3)
        with patch('volume_layers.inspect_file',return_value=dict(shape=(5,3,3,1),fov_um=None)),patch('volume_layers.file_key',return_value=('fixture',1,1)),patch('volume_layers.read_signal',return_value=data) as reader:
            result=build_layer_previews('fixture',[a],(0,2,0,2),(0,4),quality='Fast',voxel_budget=4)[0]
            self.assertLessEqual(result.values.size,4)
            # Weighted sum of all block means equals sum of source values.
            self.assertAlmostEqual(float((result.values*result.valid_counts).sum()),990)
            a.colorscale='Reds';a.opacity=.5
            again=build_layer_previews('fixture',[a],(0,2,0,2),(0,4),quality='Fast',voxel_budget=4)[0]
            self.assertEqual(reader.call_count,1);np.testing.assert_array_equal(result.values,again.values)

    def test_many_layers_total_budget_and_invisible_work(self):
        layers=[self.layer((0,9),str(i)) for i in range(7)];layers[-1].visible=False
        with patch('volume_layers.inspect_file',return_value=dict(shape=(10,8,8,1),fov_um=None)),patch('volume_layers.file_key',return_value=('fixture',1,1)),patch('volume_layers.read_signal',return_value=np.ones((10,8,8))) as reader:
            results=build_layer_previews('fixture',layers,(0,7,0,7),(0,9),quality='Fast',voxel_budget=100)
            self.assertLessEqual(sum(p.values.size for p in results),100);self.assertEqual(len(results),6)
            self.assertTrue(all(np.all(p.values==1) for p in results));self.assertEqual(reader.call_count,1)
