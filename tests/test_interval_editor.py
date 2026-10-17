"""Draft interval editing is independent of the currently applied signal."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock

from test_signal_recipes import make_acquisition
from workspace import ExplorerWorkspace


class IntervalEditorTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.path=Path(directory.name)/'example.h5';make_acquisition(self.path)
        self.figure_patch=patch.object(ExplorerWorkspace,'figures',return_value={});self.figure_patch.start();self.addCleanup(self.figure_patch.stop)
        with patch('workspace.get_plotlyjs',return_value=''):
            self.w=ExplorerWorkspace(self.path)
        self.w.send=Mock()

    def event(self,name,**payload):
        self.w.handle_message(None,dict(event=name,payload=payload),None)
        result=self.w.send.call_args.args[0]
        self.assertNotIn('error',result,result)
        return result['state']

    def test_add_select_edit_remove_only_changes_the_target_draft(self):
        primary=self.w.volume
        first=self.w.state()['draft_windows'][0]['id']
        state=self.event('interval_add',bounds=[4,5]);second=state['selected_interval_id']
        self.assertNotEqual(first,second)
        self.event('interval_select',id=first)
        state=self.event('interval_update',id=first,bounds=[1,2])
        self.assertEqual(state['draft_intervals'],((1.,2.),(4.,5.)))
        self.assertIs(self.w.volume,primary)
        self.event('interval_remove',id=second)
        state=self.event('interval_remove',id=first)
        self.assertEqual(state['draft_windows'],[])
        self.assertIsNone(state['selected_interval_id']);self.assertIsNone(state['draft'])
        self.assertIs(self.w.volume,primary)
        state=self.event('interval_add',bounds=[2,3])
        self.assertEqual(state['draft_intervals'],((2.,3.),))

    def test_rejected_edits_preserve_rows_and_active_signal(self):
        identifier=self.w.state()['draft_windows'][0]['id']
        before=self.w.state()['draft_windows'];primary=self.w.volume
        for event,payload in [('interval_update',dict(id=identifier,bounds=[3,1])),('interval_add',dict(bounds=[4,9])),('interval_remove',dict(id=999)),('interval_select',dict(id=999))]:
            self.w.handle_message(None,dict(event=event,payload=payload),None)
            self.assertIn('error',self.w.send.call_args.args[0])
            self.assertEqual(self.w.state()['draft_windows'],before)
            self.assertIs(self.w.volume,primary)

    def test_apply_uses_all_rows_and_merges_overlap_only_when_applied(self):
        first=self.w.state()['draft_windows'][0]['id']
        self.event('interval_update',id=first,bounds=[1,3])
        self.event('interval_add',bounds=[2,4])
        self.assertEqual(len(self.w.state()['draft_windows']),2)
        state=self.event('integrate',frames=[0,2])
        self.assertEqual(state['intervals'],((1.,4.),))
        self.assertEqual(len(state['draft_windows']),1)
