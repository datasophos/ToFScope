import json
import unittest
import numpy as np
from service_fixture import setup_case
from tofscope.api.app import build_services
from tofscope.application.commands import CommandEnvelope
from tofscope.presentation.explore import ExplorePresenter
from tofscope.presentation.exports import ExportService


class PresentationTests(unittest.TestCase):
    def setUp(self):
        setup_case(self)
        self.s = build_services(self.settings)
        self.addCleanup(self.s.jobs.shutdown)
        self.addCleanup(self.s.workspaces.close_all)
        self.a = self.s.workspaces.create_analysis(
            "a", self.s.workspaces.create("a").id, self.s.repository.open("a", "a.h5")
        )
        self.presenter = ExplorePresenter(
            self.s.workspaces, self.s.repository, self.s.cache, self.settings
        )
        self.exports = ExportService(self.presenter)

    def command(self, command):
        a = self.s.workspaces.get("a", self.a.id)
        return self.s.explore.apply(
            "a",
            a.id,
            CommandEnvelope(str(a.revision), a.revision, a.dataset.generation, command),
        )

    def test_original_values_and_coverage(self):
        self.command({"type": "select_stored", "index": 0})
        d = self.presenter.snapshot(
            "a", self.a.id, {"ion", "front", "profile", "spectrum"}
        )
        np.testing.assert_array_equal(d.panels["ion"].values, [[6.0, 9.0]])
        np.testing.assert_array_equal(
            d.panels["front"].values, [[0.0, 1.0], [2.0, 3.0], [4.0, 5.0]]
        )
        self.assertEqual(d.panels["profile"].series[0].values, [0.5, 2.5, 4.5])
        json.dumps(d.to_dict(), allow_nan=False)
        self.command({"type": "set_roi", "roi": [1, 1, 0, 0]})
        np.testing.assert_array_equal(
            self.presenter.snapshot("a", self.a.id, {"front"}).panels["front"].values,
            [[0.0, 1.0], [2.0, 3.0], [4.0, 5.0]],
        )
        csv = self.exports.render("a", self.a.id, "csv").content
        self.command(
            {"type": "set_display", "log": True, "relative": True, "image": "sims"}
        )
        self.assertEqual(self.exports.render("a", self.a.id, "csv").content, csv)
        self.command({"type": "set_depth", "depth": {"mode": "frame", "index": 1}})
        self.assertEqual(self.exports.render("a", self.a.id, "csv").content, csv)
        np.testing.assert_array_equal(
            self.presenter.snapshot("a", self.a.id, {"ion"}).panels["ion"].values,
            [[2.0, 3.0]],
        )

    def test_se_and_json_exact_scope(self):
        self.command(
            {"type": "set_display", "log": False, "relative": False, "image": "se"}
        )
        d = self.presenter.snapshot("a", self.a.id, {"ion"})
        np.testing.assert_array_equal(d.panels["ion"].values, [[4.0, 6.0], [8.0, 10.0]])
        recipe = json.loads(self.exports.render("a", self.a.id, "json").content)
        self.assertEqual(recipe["schema_version"], 3)
        self.assertEqual(recipe["loaded_frames"], [0, 2])
        self.assertNotIn(str(self.settings.data_root), str(recipe))

    def test_missing_se_pixels_are_null_not_zero(self):
        import h5py

        with h5py.File(self.settings.data_root / "b.h5", "r+") as f:
            f["FIBImages/Image0000/Data"][0, 0] = np.nan
            f["FIBImages/Image0001/Data"][0, 0] = np.nan
        current = self.s.workspaces.get("a", self.a.id)
        self.s.workspaces.replace(
            "a", self.a.id, self.s.repository.open("a", "b.h5"), current.revision
        )
        self.command(
            {"type": "set_display", "log": False, "relative": False, "image": "se"}
        )
        d = self.presenter.snapshot("a", self.a.id, {"ion"})
        self.assertIsNone(d.panels["ion"].values[0][0])
        self.assertFalse(d.panels["ion"].coverage[0][0])
    def test_partial_comparison_alignment_roi_and_exports(self):
        from tofscope.application.jobs import IntegrationSpec
        from tofscope.application.commands import CommandEnvelope
        a=self.s.workspaces.get('a',self.a.id)
        job=self.s.jobs.submit('a',a.id,CommandEnvelope('comparison',a.revision,a.dataset.generation,{'type':'set_depth','depth':{'mode':'all'}}),IntegrationSpec(((1,2),(4,5)),(1,2),'comparison'))
        self.assertEqual(self.s.jobs.wait('a',job.id,3).status,'succeeded')
        self.command({'type':'select_stored','index':0})
        panel=self.presenter.snapshot('a',a.id,{'profile'}).panels['profile'];self.assertEqual(panel.series[1].values,[None,.75,.875])
        self.command({'type':'set_roi','roi':[1,1,0,0]})
        self.assertEqual(self.presenter.snapshot('a',a.id,{'profile'}).panels['profile'].series[1].values,[None,.5,.75])
        self.assertIn(b'0,1.0,',self.exports.render('a',a.id,'csv').content)
