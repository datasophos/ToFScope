"""Explicit saves retain scientific data; old sessions cannot overwrite them."""
from dataclasses import asdict,replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
import h5py
import numpy as np
from workspace import ExplorerWorkspace
from server_config import ServerSettings
from test_signal_recipes import make_acquisition
from integration_store import write_integration_group


class WorkspaceWritebackTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.path=self.root/'a.h5';make_acquisition(self.path)
        self.figures=patch.object(ExplorerWorkspace,'figures',return_value={});self.figures.start();self.addCleanup(self.figures.stop)
        self.bundle=patch('workspace.get_plotlyjs',return_value='');self.bundle.start();self.addCleanup(self.bundle.stop)
        self.settings=ServerSettings(self.root,allow_writes=True,allow_unverified_native=True)
        self.w=ExplorerWorkspace(self.path,settings=self.settings);self.w.send=Mock()

    def event(self,w,event,**payload):
        w.handle_message(None,dict(event=event,payload=payload),None)
        return w.send.call_args.args[0]

    def test_preview_is_readonly_save_reopens_and_stale_session_rejected(self):
        old=ExplorerWorkspace(self.path,settings=self.settings);old.send=Mock()
        self.event(self.w,'integrate',intervals=[[1,2]],frames=[0,2]);expected=self.w.volume.copy()
        self.event(self.w,'depth_anchor_set',frame=2,depth=100,unit='nm')
        before=self.path.read_bytes()
        preview=self.event(self.w,'save_preview',recipe_id=self.w.active_recipe.id)['save_preview']
        self.assertEqual(self.path.read_bytes(),before);self.assertEqual(preview['target'],'a.h5')
        self.assertEqual(preview['frames'],[0,2]);self.assertEqual(preview['spatial_shape'],[1,2]);self.assertEqual(preview['commercial_status'],'unverified')
        self.assertEqual(preview['expected_identity']['mtime_ns'],str(self.w.loaded_identity.mtime_ns))
        response=self.event(self.w,'save_integration',recipe_id=self.w.active_recipe.id,label='Al_test',expected_identity=preview['expected_identity'])
        self.assertNotIn('error',response);self.assertIn('saved',response)
        self.assertIsNone(response['saved']['warning']);self.assertEqual(self.w.calibration.frame_to_depth(1),50)
        self.assertEqual(self.w.active_recipe.source,'saved');self.assertEqual(len(self.w.state()['saved_integrations']),1)
        self.assertEqual(self.w.volume_layers[0].recipe,self.w.active_recipe)
        np.testing.assert_array_equal(self.w.volume,expected)
        with h5py.File(self.path,'r') as h5:self.assertEqual(len(h5['PeakData/PeakTable']),2)
        stale=self.event(old,'integrate',intervals=[[1,2]],frames=[0,2])
        self.assertIn('Reload',stale['error']);self.assertTrue(old.state()['stale'])
        self.assertEqual(old.active_recipe.source,'stored')
        self.event(old,'reload_acquisition');self.assertFalse(old.state()['stale'])
        saved_id=self.w.active_recipe.saved_id
        self.event(old,'saved_signal',saved_id=saved_id);np.testing.assert_array_equal(old.volume,expected)

    def test_readonly_partial_disjoint_and_forged_identity(self):
        w=ExplorerWorkspace(self.path,settings=ServerSettings(self.root));w.send=Mock()
        self.event(w,'integrate',intervals=[[1,2]],frames=[0,2])
        preview=self.event(w,'save_preview',recipe_id=w.active_recipe.id)['save_preview']
        self.assertFalse(preview['can_save'])
        self.assertIn('error',self.event(w,'save_integration',recipe_id=w.active_recipe.id,label='test',expected_identity=preview['expected_identity']))
        for intervals,frames in [([[1,2],[4,5]],[0,2]),([[1,2]],[1,2])]:
            self.event(self.w,'integrate',intervals=intervals,frames=frames)
            preview=self.event(self.w,'save_preview',recipe_id=self.w.active_recipe.id)['save_preview']
            self.assertFalse(preview['can_save']);self.assertIn('contiguous',preview['reason'])
        self.event(self.w,'integrate',intervals=[[1,2]],frames=[0,2])
        identity=asdict(self.w.loaded_identity);identity['mtime_ns']+=1
        before=self.path.read_bytes()
        self.assertIn('error',self.event(self.w,'save_integration',recipe_id=self.w.active_recipe.id,label='test',expected_identity=identity))
        self.assertEqual(before,self.path.read_bytes())

    def test_bad_saved_calibration_preserves_active_data_and_recipe(self):
        self.event(self.w,'integrate',intervals=[[1,2]],frames=[0,2])
        record=self.w.save_record('broken')
        record=replace(record,calibration=dict(anchors=[dict(frame=0,depth_nm=0),dict(frame=20,depth_nm=100)],unit='nm'))
        with h5py.File(self.path,'r+') as f:write_integration_group(f,record,iter(self.w.volume))
        self.w.load_file(self.path);before=self.w.volume;recipe=self.w.active_recipe
        result=self.event(self.w,'saved_signal',saved_id=record.id)
        self.assertIn('error',result);self.assertIs(self.w.volume,before);self.assertEqual(self.w.active_recipe,recipe)
