import unittest
from service_fixture import setup_case
from tofscope.application.workspaces import WorkspaceService
from tofscope.application.lifecycle import LifecycleService


class FakeJobs:
    def __init__(self):
        self.cancelled = []

    def close_analysis(self, id):
        self.cancelled.append(id)


class LifecycleTests(unittest.TestCase):
    def test_grace_live_second_view_and_expiry(self):
        setup_case(self)
        ws = WorkspaceService(self.repo, self.settings)
        a = ws.create_analysis("a", ws.create("a").id, self.dataset)
        jobs = FakeJobs()
        clock = [0.0]
        life = LifecycleService(ws, jobs, self.settings, lambda: clock[0])
        v = life.attach("a", a.id)
        clock[0] = 30
        second = life.attach("a", a.id)
        life.detach("a", v.id)
        clock[0] = 60
        life.heartbeat("a", second.id)
        life.sweep()
        self.assertFalse(jobs.cancelled)
        clock[0] = 200
        life.sweep()
        self.assertTrue(jobs.cancelled)
        clock[0] = 1000
        life.sweep()
        with self.assertRaises(KeyError):
            ws.get("a", a.id)
        with self.assertRaises(KeyError):
            life.heartbeat("a", second.id)
