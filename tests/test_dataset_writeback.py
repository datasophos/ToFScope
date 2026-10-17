"""Copy-and-replace saves never publish partial or stale scientific data."""
import tempfile
import unittest
from pathlib import Path
from dataclasses import asdict,replace
from unittest.mock import patch
from uuid import uuid4
import subprocess
import sys
import h5py
import numpy as np
from filelock import Timeout
from dataset_io import file_identity,dataset_lock,save_to_acquisition
from server_config import ServerSettings
from integration_store import IntegrationRecord,read_saved_integration
from signals import SignalRecipe,read_signal
from test_signal_recipes import make_acquisition


class DatasetWritebackTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name).resolve();self.path=self.root/'a.h5';make_acquisition(self.path)
        self.settings=ServerSettings(self.root,allow_writes=True,allow_unverified_native=True)
        self.expected=file_identity(self.path)
        self.recipe=SignalRecipe(intervals=((1,2),),frames=(0,2),label='saved_test')
        self.values=read_signal(self.path,self.recipe)
        self.record=IntegrationRecord(str(uuid4()),self.recipe.to_dict(),(1,2),asdict(self.expected),dict(normalization=4))

    def save(self):return save_to_acquisition(self.settings,'a.h5',self.record,lambda:iter(self.values),self.expected)

    def test_success_preserves_vendor_and_retains_backup(self):
        before=self.path.read_bytes();result=self.save()
        self.assertTrue(result.backup.exists());self.assertEqual(result.backup.read_bytes(),before)
        np.testing.assert_array_equal(read_saved_integration(self.path,self.record.id),self.values)
        with h5py.File(self.path,'r') as f:
            self.assertEqual(f['PeakData/PeakData'].shape,(3,1,2,2));self.assertEqual(f.attrs['ToFScopeGeneration'],result.generation)
        self.assertNotEqual(file_identity(self.path),self.expected)
        with self.assertRaises(ValueError):self.save()

    def test_prepublication_failures_preserve_original_bytes(self):
        before=self.path.read_bytes()
        for target in ['dataset_io.shutil.copy2','dataset_io.export_native_copy','dataset_io.write_integration_group','dataset_io.verify_saved_copy','dataset_io.os.replace']:
            with self.subTest(stage=target),patch(target,side_effect=OSError('injected failure')):
                with self.assertRaises(OSError):self.save()
            self.assertEqual(self.path.read_bytes(),before)
        with patch('dataset_io.file_identity',side_effect=[self.expected,replace(self.expected,mtime_ns=self.expected.mtime_ns+1)]):
            with self.assertRaises(ValueError):self.save()
        self.assertEqual(self.path.read_bytes(),before)

    def test_policy_space_stale_and_postreplace_warning(self):
        for settings in [ServerSettings(self.root),ServerSettings(self.root,allow_writes=True)]:
            with self.assertRaises(ValueError):save_to_acquisition(settings,'a.h5',self.record,lambda:iter(self.values),self.expected)
        with patch('dataset_io.shutil.disk_usage') as disk:
            disk.return_value.free=0
            with self.assertRaises(ValueError):self.save()
        with self.assertRaises(ValueError):save_to_acquisition(self.settings,'../escape.h5',self.record,lambda:iter(self.values),self.expected)
        with patch('dataset_io.clear_dataset_caches',side_effect=OSError('cache failure after commit')):
            result=self.save()
        self.assertTrue(result.reload_required);self.assertTrue(result.warning)
        np.testing.assert_array_equal(read_saved_integration(self.path,self.record.id),self.values)

    def test_lock_reentrant_and_excludes_other_process(self):
        self.assertIs(dataset_lock(self.path),dataset_lock(self.path))
        with dataset_lock(self.path):self.assertEqual(file_identity(self.path),self.expected)
        script="from dataset_io import dataset_lock;import sys,time\nwith dataset_lock(sys.argv[1]):\n print('locked',flush=True)\n time.sleep(.6)"
        process=subprocess.Popen([sys.executable,'-c',script,str(self.path)],stdout=subprocess.PIPE,text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(),'locked')
            with self.assertRaises(Timeout):
                with dataset_lock(self.path).acquire(timeout=.05):pass
        finally:process.wait(timeout=3);process.stdout.close()
