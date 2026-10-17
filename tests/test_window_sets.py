"""Scientific semantics and serialization of composite mass-window signals."""
import json
from dataclasses import replace, FrozenInstanceError
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

import numpy as np

from integration import canonical_intervals, integrate_event_windows
from signals import SignalRecipe


class WindowSetTests(unittest.TestCase):
    def setUp(self):
        self.axis=np.arange(6.)
        self.events=np.empty((1,1),dtype=object)
        self.events[0,0]=np.array([1,2,2,3,4],dtype=np.uint32)*64

    def test_union_counts_overlap_once(self):
        result=integrate_event_windows(self.events,self.axis,64,2,[(1,2),(2,4)])
        np.testing.assert_array_equal(result,[[2.5]])

    def test_gaps_stay_excluded(self):
        np.testing.assert_array_equal(integrate_event_windows(self.events,self.axis,64,2,[(1,2),(4,5)]),[[2.]])

    def test_valid_interval_between_bins_yields_zero(self):
        np.testing.assert_array_equal(integrate_event_windows(self.events,self.axis,64,2,[(2.1,2.9)]),[[0.]])

    def test_float32_axis_does_not_round_user_bounds_onto_a_bin(self):
        axis=np.array([0.,1.,2.],dtype=np.float32)
        events=np.empty((1,1),dtype=object);events[0,0]=np.array([1],dtype=np.uint32)
        for bounds in [[1.00000001,2.],[0.,.99999999]]:
            with self.subTest(bounds=bounds):
                np.testing.assert_array_equal(integrate_event_windows(events,axis,1,1,[bounds]),[[0.]])
        np.testing.assert_array_equal(integrate_event_windows(events,axis,1,1,[(1.,1.5)]),[[1.]])

    def test_canonical_order_merging_and_invalid_bounds(self):
        self.assertEqual(canonical_intervals([(4,5),(1,2),(2,3),(1.5,2.5)],(0,5)),((1.,3.),(4.,5.)))
        for windows in [[],[(2,1)],[(2,2)],[(0,float('nan'))],[(-1,1)],[(1,6)],[(1,2,3)]]:
            with self.subTest(windows=windows),self.assertRaises(ValueError):
                canonical_intervals(windows,(0,5))

    def test_invalid_timestamps_empty_pixels_and_one_interval_compatibility(self):
        events=np.empty((1,3),dtype=object)
        events[0,0]=np.array([-64,0,64,320,999999],dtype=np.int64)
        events[0,1]=np.array([],dtype=np.uint32)
        events[0,2]=np.array([128,256],dtype=np.uint32)
        np.testing.assert_array_equal(integrate_event_windows(events,self.axis,64,2,[(0,.5),(4,5)]),[[1.,0.,.5]])
        from explorer import integrate_events
        np.testing.assert_array_equal(integrate_events(self.events,self.axis,64,2,1,4),[[2.5]])

    def test_recipe_canonical_immutable_and_round_trips_json(self):
        recipe=SignalRecipe(id=str(uuid4()),label='Al + Ti',source='custom',intervals=((4,5),(1,2)),frames=(10,12))
        self.assertEqual(recipe.intervals,((1.,2.),(4.,5.)))
        self.assertEqual(recipe,SignalRecipe.from_dict(json.loads(json.dumps(recipe.to_dict()))))
        self.assertEqual(recipe.to_dict()['schema_version'],3)
        with self.assertRaises(FrozenInstanceError):recipe.label='Changed'

    def test_legacy_raw_recipe_migrates_one_interval(self):
        recipe=SignalRecipe.from_dict(dict(schema_version=2,source='raw_reconstruction',signal='custom',lower_Th=1,upper_Th=2,frames_inclusive=[10,12]))
        self.assertEqual(recipe.intervals,((1.,2.),))
        self.assertEqual(recipe.frames,(10,12))
        self.assertEqual(recipe.source,'custom')

    def test_recipe_validates_references_frames_and_unknown_schema(self):
        valid=dict(source='custom',intervals=((1,2),),frames=(0,3))
        for patch in [dict(frames=(3,1)),dict(frames=(.5,2)),dict(frames=(-1,2)),dict(id='not-a-uuid'),dict(source='unknown'),dict(source='stored'),dict(stored_index=3),dict(intervals=())]:
            with self.subTest(patch=patch),self.assertRaises(ValueError):SignalRecipe(**(valid|patch))
        with self.assertRaises(ValueError):SignalRecipe.from_dict(dict(schema_version=99))

    def test_computation_key_ignores_display_identity(self):
        recipe=SignalRecipe(label='one',source='custom',intervals=((1,2),),frames=(10,12))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source.h5';path.touch()
            changed=replace(recipe,id=str(uuid4()),label='two')
            self.assertEqual(recipe.computation_key(path),changed.computation_key(path))
            self.assertNotEqual(recipe.computation_key(path),replace(recipe,intervals=((1,3),)).computation_key(path))
            before=recipe.computation_key(path)
            path.write_text('new source')
            self.assertNotEqual(before,recipe.computation_key(path))
