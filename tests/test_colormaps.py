import unittest
import json
from service_fixture import setup_case
from tofscope.api.app import build_services
from tofscope.application.commands import CommandEnvelope
from tofscope.storage.analysis_document import encode_document,restore_snapshot,SavedAnalysisDocument

class ColormapTests(unittest.TestCase):
    def setUp(self):
        setup_case(self)
        self.s=build_services(self.settings)
        self.addCleanup(self.s.jobs.shutdown)
        self.addCleanup(self.s.analyses.close_all)
        self.a=self.s.analyses.create_analysis('a',self.s.repository.open('a','a.h5'))

    def change(self,**patch):
        a=self.s.analyses.get('a',self.a.id)
        return self.s.explore.apply('a',a.id,CommandEnvelope(str(a.revision),a.revision,a.dataset.generation,dict(type='set_display',log=True,relative=True,image='sims') | patch))

    def test_palette_changes_only_colors_and_is_analysis_local(self):
        other=self.s.analyses.create_analysis('a',self.a.dataset)
        before=self.s.presenter.snapshot('a',self.a.id)
        csv=self.s.exports.render('a',self.a.id,'csv').content
        for palette in ['viridis','magma','cividis','gray']:
            a=self.change(colormap=palette)
            after=self.s.presenter.snapshot('a',a.id)
            for name in ['ion','front']:
                self.assertEqual(after.panels[name].palette,palette)
                self.assertEqual(after.panels[name].values,before.panels[name].values)
                self.assertEqual(after.panels[name].axes,before.panels[name].axes)
            self.assertEqual(after.panels['profile'],before.panels['profile'])
            self.assertEqual(self.s.exports.render('a',a.id,'csv').content,csv)
            self.assertEqual(other.display.colormap,'viridis')
        self.change(colormap='magma')
        self.change(image='se')
        se=self.s.presenter.snapshot('a',self.a.id,{'ion','front'})
        self.assertEqual(se.panels['ion'].palette,'gray')
        self.assertEqual(se.panels['front'].palette,'magma')
        with self.assertRaises(ValueError): self.change(colormap='invalid')

    def test_persistence_and_legacy_default(self):
        a=self.change(colormap='magma')
        # Older display commands must preserve the current palette.
        a=self.change()
        self.assertEqual(a.display.colormap,'magma')
        doc=encode_document(a)
        restored=restore_snapshot(SavedAnalysisDocument.model_validate_json(doc.model_dump_json()),self.a)
        self.assertEqual(restored.display.colormap,'magma')
        old=doc.model_dump()
        del old['display']['colormap']
        self.assertEqual(restore_snapshot(SavedAnalysisDocument.model_validate(old),self.a).display.colormap,'viridis')
        self.assertEqual(json.loads(self.s.exports.render('a',a.id,'json').content)['display']['colormap'],'magma')

    def test_legacy_ion_palette_migrates_to_viridis(self):
        doc=encode_document(self.a).model_dump()
        doc['display']['colormap']='ion'
        restored=restore_snapshot(SavedAnalysisDocument.model_validate(doc),self.a)
        self.assertEqual(restored.display.colormap,'viridis')
