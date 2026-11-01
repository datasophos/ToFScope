import unittest

import h5py
import numpy as np
from service_fixture import setup_case
from tofscope.application.analyses import AnalysisService, strongest_spectral_peak
from tofscope.application.explore import ExploreService
from tofscope.application.commands import CommandEnvelope


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        setup_case(self)
        self.ws = AnalysisService(self.repo, self.settings)
        self.explore = ExploreService(self.ws, self.repo)

    def new(self, owner="a"):
        return self.ws.create_analysis(owner, self.repo.open(owner, "a.h5"))

    def command(self, s, command, request="one"):
        return self.explore.apply(
            s.owner,
            s.id,
            CommandEnvelope(request, s.revision, s.dataset.generation, command),
        )

    def test_default_prefers_eligible_peaks_even_when_lower_peak_is_stronger(self):
        peaks = [
            {"index": 0, "mass": 2., "low": 1.5, "high": 2.5},
            {"index": 1, "mass": 20., "low": 19.5, "high": 20.5},
            {"index": 2, "mass": 27., "low": 26.5, "high": 27.5},
        ]
        result = strongest_spectral_peak(peaks, np.array([2., 20., 27.]), np.array([1000., 5., 7.]))
        self.assertEqual(result["index"], 2)
        # The threshold is inclusive.
        result = strongest_spectral_peak(peaks, np.array([2., 20., 27.]), np.array([1000., 8., 7.]))
        self.assertEqual(result["index"], 1)

    def test_default_falls_back_when_no_peak_meets_threshold(self):
        peaks = [
            {"index": 0, "mass": 2., "low": 1.5, "high": 2.5},
            {"index": 1, "mass": 12., "low": 11.5, "high": 12.5},
        ]
        result = strongest_spectral_peak(peaks, np.array([2., 12.]), np.array([1., 8.]))
        self.assertEqual(result["index"], 1)

    def test_default_signal_has_greatest_integrated_spectrum(self):
        # The strongest individual spectral bin is in the second window, but
        # the first window has the greater total across all its bins.
        with h5py.File(self.settings.data_root / "a.h5", "r+") as handle:
            handle["FullSpectra/SumSpectrum"][:] = [0, 6, 6, 0, 9, 0]
        analysis = self.new()
        self.assertEqual(analysis.signals[0].recipe.stored_index, 0)
        self.assertEqual(analysis.image_signal_id, analysis.signals[0].id)
        self.assertEqual(analysis.signals[0].recipe.frames, (0, 2))

    def test_default_signal_ignores_nonfinite_spectrum_and_breaks_ties_by_order(self):
        with h5py.File(self.settings.data_root / "a.h5", "r+") as handle:
            handle["FullSpectra/SumSpectrum"][:] = [0, 4, np.nan, 0, 2, 2]
        analysis = self.new()
        self.assertEqual(analysis.signals[0].recipe.stored_index, 0)

    def test_default_signal_falls_back_to_first_when_spectrum_has_no_finite_values(self):
        with h5py.File(self.settings.data_root / "a.h5", "r+") as handle:
            handle["FullSpectra/SumSpectrum"][:] = np.nan
        analysis = self.new()
        self.assertEqual(analysis.signals[0].recipe.stored_index, 0)

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

    def test_open_and_replace_establish_clean_baselines_without_claiming_a_save(self):
        a = self.new()
        self.assertEqual(a.opened_revision, a.revision)
        self.assertIsNone(a.saved_revision)
        a = self.command(a, {"type": "set_roi", "roi": [1, 1, 0, 0]})
        self.assertLess(a.opened_revision, a.revision)
        a = self.ws.replace("a", a.id, self.repo.open("a", "a.h5"), a.revision)
        self.assertGreater(a.revision, 0)
        self.assertEqual(a.opened_revision, a.revision)
        self.assertIsNone(a.saved_revision)

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
