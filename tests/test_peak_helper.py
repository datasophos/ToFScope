"""Suggestions never relabel source peaks or trigger implicit reconstruction."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from workspace import ExplorerWorkspace
from test_signal_recipes import make_acquisition


class PeakHelperTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        path=Path(temp.name)/'a.h5';make_acquisition(path)
        with patch('workspace.get_plotlyjs',return_value=''),patch.object(ExplorerWorkspace,'figures',return_value={}):self.w=ExplorerWorkspace(path)
        self.w.send=Mock()

    def event(self,name,**payload):
        self.w.handle_message(None,dict(event=name,payload=payload),None)
        result=self.w.send.call_args.args[0];self.assertNotIn('error',result,result);return result

    def test_candidates_annotations_and_empty_matches(self):
        original=self.w.volume;label=self.w.label
        with patch('workspace.read_signal',side_effect=AssertionError('candidate search reconstructed raw')):
            result=self.event('peak_candidates',mz=26.981,tolerance=.01,unit='Th',charges=[1],request_id=1)
        candidates=result['peak_candidates']['rows']
        al=next(c for c in candidates if c['id']=='Al-27:+1')
        self.assertAlmostEqual(al['predicted_mz'],26.980989950090958)
        self.event('peak_assignment',recipe_id=self.w.active_recipe.id,candidate_id=al['id'])
        self.assertEqual(self.w.label,label);self.assertIs(self.w.volume,original)
        self.assertEqual(self.w.state()['assignments'][self.w.active_recipe.id]['candidate']['id'],'Al-27:+1')
        result=self.event('peak_candidates',mz=.0001,tolerance=0,unit='Th',charges=[1],request_id=2)
        self.assertEqual(result['peak_candidates']['rows'],[])

    def test_explicit_measurement_export_and_stale_annotation_rejection(self):
        self.event('abundance_measure',recipe_ids=[self.w.active_recipe.id],frames=[0,1],roi=[0,1,0,0])
        row=self.w.state()['abundance_rows'][0]
        self.assertEqual(row['summed_intensity'],6.)
        self.assertEqual(row['observed_fraction'],1.)
        self.assertEqual(self.w.state()['abundance_context']['frames'],[0,1])
        self.event('abundance_export')
        text=self.w.send.call_args.args[0]['download']['text']
        self.assertIn('observed_selected_set_fraction',text);self.assertIn('reference_abundance_low',text)
        self.w.handle_message(None,dict(event='peak_assignment',payload=dict(recipe_id='missing',candidate_id='Al-27:+1')),None)
        self.assertIn('error',self.w.send.call_args.args[0])
