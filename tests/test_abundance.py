"""Measured isotope-set fractions use common coverage and original counts."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from signals import SignalRecipe
from abundance import measure_isotopes


class AbundanceTests(unittest.TestCase):
    def recipe(self,interval,frames=(0,2)):
        return SignalRecipe(intervals=(interval,),frames=frames,label='isotope')

    def test_areas_ratios_roi_and_zero_total(self):
        a,b=self.recipe((1,2)),self.recipe((3,4))
        data={a.id:np.array([10.,20.,30.])[:,None,None],b.id:np.array([30.,40.,50.])[:,None,None]}
        with patch('abundance.read_signal',side_effect=lambda path,r:data[r.id]):
            rows=measure_isotopes('unused',[a,b],(0,0,0,0),(0,1))
            self.assertEqual([r.summed_intensity for r in rows],[30.,70.])
            self.assertEqual([r.observed_fraction for r in rows],[.3,.7])
        with patch('abundance.read_signal',return_value=np.zeros((3,2,2))):
            rows=measure_isotopes('unused',[a,b],(0,1,0,1),(0,2))
            self.assertTrue(all(r.observed_fraction is None for r in rows))

    def test_coverage_overlap_and_empty_common_span(self):
        a,b=self.recipe((1,2),(0,2)),self.recipe((3,4),(1,3))
        with patch('abundance.read_signal',side_effect=lambda path,r:np.array([1.,2.,3.])[:,None,None]):
            rows=measure_isotopes('unused',[a,b],(0,0,0,0),(0,3))
            self.assertEqual([r.actual_frames for r in rows],[(1,2),(1,2)])
            self.assertEqual([r.summed_intensity for r in rows],[5.,3.])
            self.assertEqual(rows[0].observed_fraction,5/8)
        overlapping=self.recipe((2,3))
        with patch('abundance.read_signal',return_value=np.ones((3,1,1))):
            rows=measure_isotopes('unused',[a,overlapping],(0,0,0,0),(0,2))
            self.assertTrue(all(r.ambiguous and r.observed_fraction is None for r in rows))
        b=self.recipe((3,4),(4,5))
        with patch('abundance.read_signal',side_effect=AssertionError('empty coverage should not read')):
            rows=measure_isotopes('unused',[a,b],(0,0,0,0),(0,5))
            self.assertTrue(all(r.actual_frames is None and r.observed_fraction is None for r in rows))

    def test_real_fixture_and_roi_are_original_counts(self):
        from test_signal_recipes import make_acquisition
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'a.h5';make_acquisition(path)
            rows=measure_isotopes(path,[self.recipe((1,2)),self.recipe((4,5))],(1,1,0,0),(0,2))
            self.assertEqual([r.summed_intensity for r in rows],[.75,.75])
            self.assertEqual([r.observed_fraction for r in rows],[.5,.5])
            with self.assertRaises(ValueError):measure_isotopes(path,[self.recipe((1,2))],(0,9,0,0),(0,2))
