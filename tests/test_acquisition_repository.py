import tempfile
import unittest
from pathlib import Path
import numpy as np
from fixtures.acquisition import make_acquisition
from tofscope.config import Settings
from tofscope.storage.acquisitions import AcquisitionRepository
from tofscope.science.signals import SignalRecipe


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        make_acquisition(self.root / "a.h5")
        self.repo = AcquisitionRepository(
            Settings(self.root, runtime_dir=self.root / "runtime")
        )

    def test_alias_authorization_and_readonly_source(self):
        p = self.root / "a.h5"
        before = p.read_bytes()
        p.chmod(0o444)
        (self.root / "alias.h5").symlink_to(p)
        a = self.repo.open("a", "a.h5")
        b = self.repo.open("b", "alias.h5")
        self.assertEqual(a.key, b.key)
        self.assertEqual(a.generation, b.generation)
        with self.repo.metadata("a", a) as m:
            self.assertEqual(m.shape, (3, 1, 2, 2))
        self.assertNotIn(str(self.root), repr(a))
        r = SignalRecipe(source="custom", intervals=((1, 2), (4, 5)), frames=(0, 2))
        v = self.repo.read("a", a, r)
        np.testing.assert_array_equal(v[:, 0, :], [[1, 0.25], [1, 0.5], [1, 0.75]])
        self.assertEqual(before, p.read_bytes())
        self.assertFalse(list(self.root.glob(".*.lock")))
        self.repo.authorize = lambda owner, path: owner != "denied"
        with self.assertRaises(PermissionError):
            with self.repo.metadata("denied", a):
                pass

    def test_escape_malformed_and_stale(self):
        for path in ["../a.h5", "/etc/passwd", "missing.h5"]:
            with self.assertRaises(ValueError):
                self.repo.open("a", path)
        (self.root / "bad.h5").write_text("bad")
        with self.assertRaisesRegex(ValueError, "Acquisition"):
            self.repo.open("a", "bad.h5")
        a = self.repo.open("a", "a.h5")
        (self.root / "a.h5").touch()
        with self.assertRaisesRegex(ValueError, "changed"):
            self.repo.assert_current("a", a)

    def test_hdf5_external_links_do_not_escape_root(self):
        import h5py

        root = self.root
        outside = root / "outside"
        outside.mkdir()
        make_acquisition(outside / "external.h5")
        make_acquisition(root / "linked.h5")
        with h5py.File(root / "linked.h5", "r+") as f:
            del f["PeakData/PeakData"]
            f["PeakData/PeakData"] = h5py.ExternalLink(
                str(outside / "external.h5"), "/PeakData/PeakData"
            )
        with self.assertRaisesRegex(ValueError, "external"):
            self.repo.open("a", "linked.h5")
