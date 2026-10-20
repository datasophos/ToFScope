from dataclasses import replace
import unittest
from service_fixture import setup_case
from tofscope.api.app import build_services


class InvalidationTests(unittest.TestCase):
    def test_aliases_stale_together_and_explicit_reload(self):
        setup_case(self)
        (self.settings.data_root / "alias.h5").symlink_to(
            self.settings.data_root / "a.h5"
        )
        s = build_services(self.settings)
        self.addCleanup(s.jobs.shutdown)
        self.addCleanup(s.analyses.close_all)

        def new(owner, path):
            return s.analyses.create_analysis(owner, s.repository.open(owner, path))

        a = new("a", "a.h5")
        b = new("b", "alias.h5")
        other = new("b", "b.h5")
        s.presenter.snapshot("a", a.id)
        (self.settings.data_root / "a.h5").touch()
        self.assertTrue(s.analyses.get("a", a.id).stale)
        self.assertTrue(s.analyses.get("b", b.id).stale)
        self.assertFalse(s.analyses.get("b", other.id).stale)
        with self.assertRaises(ValueError):
            s.exports.render("a", a.id, "csv")
        current = s.analyses.get("a", a.id)
        fresh = s.analyses.replace(
            "a", a.id, s.repository.open("a", "a.h5"), current.revision
        )
        self.assertFalse(fresh.stale)
        s.presenter.snapshot("a", a.id)
