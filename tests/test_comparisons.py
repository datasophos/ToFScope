"""Comparison curves must stay independent and align to acquisition frames."""
import unittest
import csv
import io
from unittest.mock import patch, Mock
import numpy as np
from plots import profile_plot, front_projection
from workspace import ExplorerWorkspace


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.meta = dict(path='example.h5', name='example.h5', bytes=1, shape=(5,2,2,6),
            fov_um=None, raw_shape=(5,2,2), image_names=[], masses=np.arange(10.), spectrum=np.ones(10),
            peaks=[dict(index=i, mass=float(i+1), low=i+.5, high=i+1.5, label=f'ion{i}') for i in range(6)])
        self.patches = [patch('workspace.inspect_file',return_value=self.meta),
            patch('workspace.stored_peak',side_effect=lambda path,index:np.full((5,2,2),index+1.,dtype=np.float32)),
            patch('workspace.get_plotlyjs',return_value=''),patch.object(ExplorerWorkspace,'figures',return_value={})]
        for p in self.patches: p.start(); self.addCleanup(p.stop)
        self.w = ExplorerWorkspace('example.h5'); self.w.send=Mock()

    def event(self, name, **payload):
        self.w.handle_message(None,dict(event=name,payload=payload),None)
        result=self.w.send.call_args.args[0]
        self.assertNotIn('error',result,result)
        return result

    def test_add_many_remove_individually_and_preserve_primary(self):
        original=self.w.volume
        for index in range(5): self.event('comparison_add',index=index)
        self.assertEqual(len(self.w.comparisons),5)
        self.assertEqual(len(set(c['color'] for c in self.w.comparisons)),5)
        removed=self.w.comparisons[2]['id']
        self.event('comparison_remove',id=removed)
        self.assertEqual([c['index'] for c in self.w.comparisons],[0,1,3,4])
        self.assertIs(self.w.volume,original)
        self.event('comparison_add',index=0)
        self.assertEqual(len(self.w.comparisons),4)  # no accidental duplicates
        self.event('comparison_clear')
        self.assertEqual(self.w.comparisons,[])

    def test_custom_partial_frames_align_and_recompute_for_roi(self):
        custom=np.arange(8.,dtype=np.float32).reshape(2,2,2)
        with patch('workspace.custom_peak',return_value=custom):
            self.event('comparison_add',bounds=[2.2,2.7],frames=[1,2])
        descriptor=self.w.comparisons[0]
        self.assertEqual(descriptor['frames'],[1,2])
        curve=self.w.comparison_curves()[0]
        np.testing.assert_allclose(curve[1],[np.nan,1.5,5.5,np.nan,np.nan],equal_nan=True)
        self.w.roi=(1,1,0,0)
        np.testing.assert_allclose(self.w.comparison_curves()[0][1],[np.nan,1,5,np.nan,np.nan],equal_nan=True)
        self.event('comparison_remove',id=descriptor['id'])
        self.assertFalse(self.w.comparison_volumes)

    def test_profiles_normalize_independently_without_changing_arrays(self):
        volume=np.array([1.,2.,4.])[:,None,None]
        curves=[('one',np.array([2.,4.,8.]),'#ffaa00'),('two',np.array([np.nan,3.,6.]),'#dd00dd')]
        fig,_=profile_plot(volume,(10,12),(0,0,0,0),11,'primary',curves,True)
        self.assertEqual(len(fig.data),3)
        np.testing.assert_allclose(fig.data[0].y,[.25,.5,1])
        np.testing.assert_allclose(fig.data[1].y,[.25,.5,1])
        np.testing.assert_allclose(fig.data[2].y,[np.nan,.5,1],equal_nan=True)
        np.testing.assert_array_equal(curves[0][1],[2,4,8])

    def test_same_mass_different_frame_ranges_have_unique_names_and_csv_columns(self):
        with patch('workspace.custom_peak',return_value=np.ones((1,2,2),dtype=np.float32)):
            self.event('comparison_add',bounds=[2.2,2.7],frames=[1,1])
            self.event('comparison_add',bounds=[2.2,2.7],frames=[2,2])
        self.assertNotEqual(self.w.comparisons[0]['label'],self.w.comparisons[1]['label'])
        self.w.export('csv')
        text=self.w.send.call_args.args[0]['download']['text']
        reader=csv.DictReader(io.StringIO(text))
        self.assertEqual(len(set(reader.fieldnames)),4)
        rows=list(reader)
        self.assertEqual(list(rows[1].values())[2:],['1',''])
        self.assertEqual(list(rows[2].values())[2:],['','1'])

    def test_one_frame_comparison_has_a_visible_point(self):
        fig,_=profile_plot(np.ones((3,1,1)),(0,2),(0,0,0,0),0,'primary',
                           [('single',np.array([np.nan,2.,np.nan]),'#ffaa00')])
        self.assertIn('markers',fig.data[1].mode)

    def test_front_projection_sums_all_selected_y_rows_and_preserves_depth(self):
        volume=np.arange(24.,dtype=np.float32).reshape(3,2,4)
        fig=front_projection(volume,(10,12),(1,2,1,1),20,False)
        np.testing.assert_array_equal(fig.data[0].customdata,volume[:,1,:])
        fig=front_projection(volume,(10,12),(1,2,0,1),20,False)
        np.testing.assert_array_equal(fig.data[0].customdata,volume.sum(axis=1))
        np.testing.assert_array_equal(fig.data[0].y,[10,11,12])



if __name__=='__main__': unittest.main()
