import threading
import time
import unittest
from service_fixture import setup_case
from tofscope.application.workspaces import WorkspaceService
from tofscope.application.explore import ExploreService
from tofscope.application.resources import ResourceBudget
from tofscope.application.cache import ArrayCache
from tofscope.application.jobs import JobService, IntegrationSpec
from tofscope.application.commands import CommandEnvelope


class JobTests(unittest.TestCase):
    def setUp(self):
        setup_case(self)
        self.ws = WorkspaceService(self.repo, self.settings)
        self.explore = ExploreService(self.ws, self.repo)
        self.cache = ArrayCache(self.repo, ResourceBudget(self.settings))
        self.jobs = JobService(self.ws, self.explore, self.cache, self.settings)
        self.addCleanup(self.jobs.shutdown)
        self.a = self.ws.create_analysis("a", self.ws.create("a").id, self.dataset)

    def env(self, s, id="job"):
        return CommandEnvelope(
            id,
            s.revision,
            s.dataset.generation,
            {"type": "set_depth", "depth": {"mode": "all"}},
        )

    def wait(self, id):
        return self.jobs.wait("a", id, 5)

    def test_integration_retry_progress_and_independent_state(self):
        spec = IntegrationSpec(((1, 2), (4, 5)), (0, 2), "active")
        e = self.env(self.a)
        j = self.jobs.submit("a", self.a.id, e, spec)
        self.assertEqual(self.jobs.submit("a", self.a.id, e, spec).id, j.id)
        done = self.wait(j.id)
        self.assertEqual(done.status, "succeeded")
        self.assertEqual(done.done, 3)
        s = self.ws.get("a", self.a.id)
        self.assertEqual(s.active_recipe.intervals, spec.intervals)
        with self.assertRaises(KeyError):
            self.jobs.get("b", j.id)

    def test_new_apply_and_close_suppress_late_results(self):
        entered = threading.Event()
        release = threading.Event()
        original = self.repo.read

        def blocked(*args, **kwargs):
            entered.set()
            release.wait(3)
            return original(*args, **kwargs)

        self.repo.read = blocked
        first = self.jobs.submit(
            "a",
            self.a.id,
            self.env(self.a),
            IntegrationSpec(((1, 2),), (0, 2), "active"),
        )
        self.assertTrue(entered.wait(2))
        second = self.jobs.submit(
            "a",
            self.a.id,
            self.env(self.a, "second"),
            IntegrationSpec(((4, 5),), (0, 2), "active"),
        )
        release.set()
        self.assertEqual(self.wait(first.id).status, "obsolete")
        self.assertEqual(self.wait(second.id).status, "succeeded")
        s = self.ws.get("a", self.a.id)
        self.assertEqual(s.active_recipe.intervals, ((4.0, 5.0),))
        self.ws.close("a", s.id)
        self.assertEqual(self.cache.budget.users["a"], 0)

    def test_roi_revision_does_not_obsolete_computation(self):
        entered = threading.Event()
        release = threading.Event()
        original = self.repo.read

        def blocked(*a, **kw):
            entered.set()
            release.wait(3)
            return original(*a, **kw)

        self.repo.read = blocked
        j = self.jobs.submit(
            "a",
            self.a.id,
            self.env(self.a),
            IntegrationSpec(((1, 2),), (0, 2), "active"),
        )
        self.assertTrue(entered.wait(2))
        self.explore.apply(
            "a",
            self.a.id,
            CommandEnvelope(
                "roi",
                0,
                self.dataset.generation,
                {"type": "set_roi", "roi": [1, 1, 0, 0]},
            ),
        )
        release.set()
        self.assertEqual(self.wait(j.id).status, "succeeded")
        self.assertEqual(self.ws.get("a", self.a.id).roi, (1, 1, 0, 0))

    def test_second_user_runs_before_first_users_backlog(self):
        entered = threading.Event()
        release = threading.Event()
        order = []
        original = self.repo.read

        def blocked(owner, *args, **kwargs):
            order.append(owner)
            if owner == "a" and not entered.is_set():
                entered.set()
                release.wait(3)
            return original(owner, *args, **kwargs)

        self.repo.read = blocked
        first = self.jobs.submit(
            "a",
            self.a.id,
            self.env(self.a, "first"),
            IntegrationSpec(((1, 2),), (0, 2), "active"),
        )
        self.assertTrue(entered.wait(2))
        self.jobs.submit(
            "a",
            self.a.id,
            self.env(self.a, "backlog"),
            IntegrationSpec(((3, 4),), (0, 2), "active"),
        )
        b = self.ws.create_analysis(
            "b", self.ws.create("b").id, self.repo.open("b", "b.h5")
        )
        second = self.jobs.submit(
            "b",
            b.id,
            self.env(b, "second"),
            IntegrationSpec(((4, 5),), (0, 2), "active"),
        )
        self.assertEqual(self.jobs.wait("b", second.id, 2).status, "succeeded")
        self.assertEqual(order[:2], ["a", "b"])
        release.set()
        self.wait(first.id)
