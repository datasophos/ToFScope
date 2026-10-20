import json
import unittest
from unittest.mock import patch
import h5py
import numpy as np
from service_fixture import setup_case
from tofscope.api.app import build_services
from tofscope.application.commands import CommandEnvelope
from tofscope.application.jobs import IntegrationSpec
from tofscope.application.resources import ResourceBudget
from tofscope.application.analyses import CapacityError


class ReviewRegressions(unittest.TestCase):
    def setUp(self):
        setup_case(self)
        self.s = build_services(self.settings)
        self.addCleanup(self.s.jobs.shutdown)
        self.addCleanup(self.s.analyses.close_all)

    def open(self):
        return self.s.analyses.create_analysis("a", self.s.repository.open("a", "a.h5"))

    def command(self, a, command):
        return self.s.explore.apply(
            "a",
            a.id,
            CommandEnvelope(str(a.revision), a.revision, a.dataset.generation, command),
        )

    def test_infinite_stored_samples_transport_as_missing(self):
        with h5py.File(self.settings.data_root / "a.h5", "r+") as f:
            f["PeakData/PeakData"][0, 0, 0, 1] = np.inf
        a = self.open()
        d = self.s.presenter.snapshot("a", a.id)
        json.dumps(d.to_dict(), allow_nan=False)
        self.assertIsNone(d.panels["ion"].values[0][0])
        self.assertFalse(d.panels["ion"].coverage[0][0])

    def test_se_scaling_independent_of_stored_channel(self):
        a = self.open()
        a = self.command(
            a, {"type": "set_display", "image": "se", "log": False, "relative": False}
        )
        before = self.s.presenter.snapshot("a", a.id, {"ion"}).panels["ion"]
        a = self.command(a, {"type": "add_stored_signal", "index": 0})
        self.command(a, {"type": "select_image_signal", "signal_id": a.signals[-1].id})
        after = self.s.presenter.snapshot("a", a.id, {"ion"}).panels["ion"]
        self.assertEqual(before.intensity_range, after.intensity_range)
        self.assertEqual(before.palette, "gray")

    def test_missing_source_stales_and_allows_replacement(self):
        a = self.open()
        (self.settings.data_root / "a.h5").rename(
            self.settings.data_root / "removed.h5"
        )
        stale = self.s.analyses.get("a", a.id)
        self.assertTrue(stale.stale)
        replacement = self.s.analyses.replace(
            "a", a.id, self.s.repository.open("a", "b.h5"), stale.revision
        )
        self.assertFalse(replacement.stale)

    def test_metadata_admitted_before_read_and_released(self):
        repo = self.s.repository
        budget = self.s.cache.budget
        with repo.metadata("a", self.s.repository.open("a", "a.h5")) as meta:
            self.assertGreaterEqual(
                budget.physical_bytes, meta.mass_axis.nbytes + meta.sum_spectrum.nbytes
            )
        self.assertEqual(budget.physical_bytes, 0)
        from dataclasses import replace

        repo.budget = ResourceBudget(
            replace(self.settings, global_bytes=16, user_bytes=16, analysis_bytes=16)
        )
        with patch(
            "tofscope.storage.acquisitions.inspect_file",
            side_effect=AssertionError("read before admission"),
        ):
            with self.assertRaises(CapacityError):
                repo.open("a", "a.h5")

    def test_raw_payload_cannot_bypass_scratch_budget(self):
        with h5py.File(self.settings.data_root / "a.h5", "r+") as f:
            f["FullSpectra/EventList"][0, 0, 0] = np.ones(10000, dtype="u4") * 64
        a = self.open()
        from dataclasses import replace

        tiny = replace(
            self.settings, global_bytes=9000, user_bytes=9000, analysis_bytes=9000
        )
        self.s.cache.budget.settings = tiny
        job = self.s.jobs.submit(
            "a",
            a.id,
            CommandEnvelope(
                "big",
                0,
                a.dataset.generation,
                {"type": "set_depth", "depth": {"mode": "all"}},
            ),
            IntegrationSpec(((1, 2),), (0, 0), "active"),
        )
        result = self.s.jobs.wait("a", job.id, 5)
        self.assertEqual(result.status, "failed")
        self.assertIn("Memory budget", result.safe_error)
        self.assertEqual(self.s.cache.budget.users["a"], 0)
