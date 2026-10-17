"""Namespaced full-resolution records retain exact recipe and frame coverage."""
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
import h5py
import numpy as np
from integration_store import IntegrationRecord,write_integration_group,list_saved_integrations,read_saved_integration
from signals import SignalRecipe,read_signal
from test_signal_recipes import make_acquisition


class IntegrationStoreTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'a.h5';make_acquisition(self.path)

    def record(self,intervals=((1,2),(4,5)),frames=(10,12)):
        recipe=SignalRecipe(intervals=intervals,frames=frames,label='Ti α')
        return IntegrationRecord(str(uuid4()),recipe.to_dict(),(1,2),dict(generation='source'),dict(normalization=4))

    def test_round_trip_partial_composite_and_vendor_unchanged(self):
        record=self.record();values=np.arange(6,dtype=np.float32).reshape(3,1,2)
        with h5py.File(self.path,'r+') as f:
            before=f['PeakData/PeakData'][:].copy();write_integration_group(f,record,iter(values))
            np.testing.assert_array_equal(f['PeakData/PeakData'][:],before)
        saved=list_saved_integrations(self.path);self.assertEqual(len(saved),1)
        self.assertEqual(saved[0]['derivation']['intervals'],[[1.,2.],[4.,5.]])
        self.assertEqual(saved[0]['derivation']['label'],'Ti α')
        np.testing.assert_array_equal(read_saved_integration(self.path,record.id),values)
        recipe=SignalRecipe(source='saved',saved_id=record.id,intervals=((1,2),(4,5)),frames=(11,12))
        np.testing.assert_array_equal(read_signal(self.path,recipe),values[1:])

    def test_invalid_and_incomplete_records(self):
        record=self.record(frames=(0,2));values=np.ones((3,1,2),dtype=np.float32)
        with h5py.File(self.path,'r+') as f:
            with self.assertRaises(ValueError):write_integration_group(f,record,values[:2])
        self.assertEqual(list_saved_integrations(self.path),[])
        for identifier in ['../bad','/absolute','abc']:
            with self.assertRaises(ValueError):read_saved_integration(self.path,identifier)
        record=self.record(frames=(0,2))
        with h5py.File(self.path,'r+') as f:
            write_integration_group(f,record,values)
            with self.assertRaises(ValueError):write_integration_group(f,record,values)
            f[f'ToFScope/Integrations/{record.id}'].attrs['schema_version']=99
        with self.assertRaises(ValueError):read_saved_integration(self.path,record.id)
