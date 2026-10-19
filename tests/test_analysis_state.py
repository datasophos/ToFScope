import unittest
from service_fixture import setup_case
from tofscope.application.workspaces import WorkspaceService
from tofscope.application.explore import ExploreService
from tofscope.application.commands import CommandEnvelope


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        setup_case(self)
        self.ws = WorkspaceService(self.repo, self.settings)
        self.explore = ExploreService(self.ws, self.repo)

    def new(self, owner="a"):
        return self.ws.create_analysis(
            owner, self.ws.create(owner).id, self.repo.open(owner, "a.h5")
        )

    def command(self, s, command, request="one"):
        return self.explore.apply(
            s.owner,
            s.id,
            CommandEnvelope(request, s.revision, s.dataset.generation, command),
        )

    def test_display_defaults_and_independent_overrides(self):
        a = self.new()
        self.assertTrue(a.display.log)
        self.assertTrue(a.display.relative)
        a = self.command(
            a, {"type": "set_display", "log": False, "relative": False, "image": "sims"}
        )
        self.assertFalse(a.display.log)
        self.assertFalse(a.display.relative)
        b = self.new()
        self.assertTrue(b.display.log)
        self.assertTrue(b.display.relative)
        self.assertEqual(self.ws.get("a", a.id).display, a.display)

    def test_same_file_analyses_have_independent_selections(self):
        a = self.new()
        b = self.new("b")
        c = self.new()
        old = b
        a = self.command(a, {"type": "set_roi", "roi": [1, 1, 0, 0]})
        a = self.command(
            a, {"type": "set_depth", "depth": {"mode": "frame", "index": 2}}, "two"
        )
        self.assertEqual(self.ws.get("b", b.id), old)
        self.assertEqual(self.ws.get("a", c.id).depth.mode, "all")
        with self.assertRaises(KeyError):
            self.ws.get("b", a.id)
        with self.assertRaises(ValueError):
            self.ws.replace(
                "a", a.id, type(a.dataset)(a.dataset.key, "stale", "a.h5"), a.revision
            )
        self.assertEqual(self.ws.get("a", a.id), a)

    def test_command_retry_is_idempotent_and_conflicts_are_atomic(self):
        a = self.new()
        cmd = {"type": "set_roi", "roi": [1, 1, 0, 0]}
        result = self.command(a, cmd)
        self.assertEqual(self.command(a, cmd), result)
        with self.assertRaises(ValueError):
            self.command(a, {"type": "set_roi", "roi": [0, 1, 0, 0]})
        with self.assertRaises(ValueError):
            self.command(a, cmd, "new")
        self.assertEqual(self.ws.get("a", a.id), result)

    def test_strict_indices_and_exclusive_depth_modes(self):
        for depth in [
            {"mode": "frame", "index": True},
            {"mode": "frame", "index": 0.5},
            {"mode": "window", "first": 2, "last": 0},
            {"mode": "all", "index": 1},
        ]:
            a = self.new()
            with self.assertRaises(ValueError):
                self.command(a, {"type": "set_depth", "depth": depth})
