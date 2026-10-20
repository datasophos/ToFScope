from dataclasses import replace
import unittest
from service_fixture import setup_case
from tofscope.api.app import build_services


class InvalidationTests(unittest.TestCase):
    def test_filesystem_metadata_updates_do_not_invalidate_unchanged_data(self):
        import os
        setup_case(self)
        source = self.settings.data_root / 'a.h5'
        before = source.stat()
        os.chmod(source, before.st_mode)
        after = source.stat()
        self.assertEqual(before.st_mtime_ns, after.st_mtime_ns)
        self.assertEqual(before.st_size, after.st_size)
        self.assertNotEqual(before.st_ctime_ns, after.st_ctime_ns)
        self.repo.assert_current('a', self.dataset)

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
