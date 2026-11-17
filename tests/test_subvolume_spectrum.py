import tempfile
import threading
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import h5py
import numpy as np
from service_fixture import setup_case

from tofscope.science.spectrum import subvolume_spectrum


class SubvolumeSpectrumTests(unittest.TestCase):
    def test_selected_events_use_original_bins_and_normalization(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.h5"
            with h5py.File(path, "w") as f:
                f.attrs["NbrWaveforms"] = 2
                f.attrs["Configuration File Contents"] = "Ch1Record=1"
                group = f.create_group("FullSpectra")
                group.attrs["SampleInterval"] = 2
                group.attrs["ClockPeriod"] = 1
                group.create_dataset("MassAxis", data=np.arange(4.0))
                raw = group.create_dataset(
                    "EventList", (2, 2, 2), dtype=h5py.vlen_dtype(np.dtype("i4"))
                )
                raw[0, 0, 1] = [-1, 0, 1, 2, 7, 8]
                raw[1, 0, 1] = [2, 3, 4]
                raw[0, 1, 0] = [4, 4, 4, 4]
                f.create_dataset("PeakData/PeakData", shape=(2, 2, 2, 1), dtype="f4")
            progress = []
            result = subvolume_spectrum(
                path,
                (1, 1, 0, 0),
                (0, 1),
                reserve=lambda _: nullcontext(),
                progress=lambda done, total: progress.append((done, total)),
            )
            np.testing.assert_array_equal(result, [1, 1.5, 0.5, 0.5])
            self.assertEqual(progress, [(1, 2), (2, 2)])

    def test_raw_spatial_grid_must_match_displayed_peak_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mismatch.h5"
            with h5py.File(path, "w") as f:
                f.create_dataset("PeakData/PeakData", shape=(1, 2, 2, 1), dtype="f4")
                group = f.create_group("FullSpectra")
                group.create_dataset("MassAxis", data=np.arange(4.0))
                group.create_dataset(
                    "EventList", (1, 1, 2), dtype=h5py.vlen_dtype(np.dtype("i4"))
                )
            with self.assertRaisesRegex(ValueError, "spatial shape"):
                subvolume_spectrum(
                    path, (0, 1, 0, 0), (0, 0), reserve=lambda _: nullcontext()
                )

    def test_job_returns_captured_selection_and_releases_memory_on_close(self):
        from tofscope.api.app import build_services
        from tofscope.api.schemas import RevisionEnvelope

        setup_case(self)
        services = build_services(self.settings)
        self.addCleanup(services.jobs.shutdown)
        dataset = services.repository.open("a", "a.h5")
        analysis = services.analyses.create_analysis("a", dataset)
        env = RevisionEnvelope(
            request_id="spectrum",
            expected_revision=analysis.revision,
            dataset_generation=analysis.dataset.generation,
        )
        job = services.spectra.submit("a", analysis.id, env)
        self.assertEqual(services.jobs.wait("a", job.id, 5).status, "succeeded")
        result = services.spectra.result("a", analysis.id)
        self.assertEqual(result.roi, (0, 1, 0, 0))
        self.assertEqual(result.frames, (0, 2))
        np.testing.assert_allclose(result.values, [0, 1.5, 1.5, 1.5, 0.75, 0.75])
        services.analyses.close("a", analysis.id)
        self.assertEqual(services.cache.budget.users["a"], 0)

    def test_missing_raw_events_preserve_existing_spectrum(self):
        from tofscope.api.app import build_services
        from tofscope.api.schemas import RevisionEnvelope

        setup_case(self)
        with h5py.File(self.settings.data_root / "a.h5", "r+") as f:
            del f["FullSpectra/EventList"]
        services = build_services(self.settings)
        self.addCleanup(services.jobs.shutdown)
        dataset = services.repository.open("a", "a.h5")
        analysis = services.analyses.create_analysis("a", dataset)
        env = RevisionEnvelope(
            request_id="spectrum",
            expected_revision=analysis.revision,
            dataset_generation=analysis.dataset.generation,
        )
        with self.assertRaisesRegex(ValueError, "does not retain raw events"):
            services.spectra.submit("a", analysis.id, env)
        self.assertIsNone(services.spectra.result("a", analysis.id))

    def test_selection_change_during_job_keeps_submitted_provenance(self):
        from tofscope.api.app import build_services
        from tofscope.api.schemas import RevisionEnvelope
        from tofscope.application.commands import CommandEnvelope

        setup_case(self)
        services = build_services(self.settings)
        self.addCleanup(services.jobs.shutdown)
        dataset = services.repository.open("a", "a.h5")
        analysis = services.analyses.create_analysis("a", dataset)
        entered, release = threading.Event(), threading.Event()

        def blocked(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("timed out")
            return subvolume_spectrum(*args, **kwargs)

        with patch(
            "tofscope.application.spectra.subvolume_spectrum", side_effect=blocked
        ):
            envelope = RevisionEnvelope(
                request_id="spectrum",
                expected_revision=analysis.revision,
                dataset_generation=dataset.generation,
            )
            job = services.spectra.submit("a", analysis.id, envelope)
            self.assertTrue(entered.wait(5))
            try:
                services.explore.apply(
                    "a",
                    analysis.id,
                    CommandEnvelope(
                        "roi-change",
                        analysis.revision,
                        dataset.generation,
                        {"type": "set_roi", "roi": [1, 1, 0, 0]},
                    ),
                )
            finally:
                release.set()
            self.assertEqual(services.jobs.wait("a", job.id, 5).status, "succeeded")
            self.assertEqual(
                services.spectra.result("a", analysis.id).roi, (0, 1, 0, 0)
            )
            self.assertEqual(services.analyses.get("a", analysis.id).roi, (1, 1, 0, 0))

    def test_cancellation_prevents_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.h5"
            with h5py.File(path, "w") as f:
                f.attrs["NbrWaveforms"] = 1
                f.attrs["Configuration File Contents"] = "Ch1Record=1"
                group = f.create_group("FullSpectra")
                group.attrs["SampleInterval"] = group.attrs["ClockPeriod"] = 1
                group.create_dataset("MassAxis", data=np.arange(4.0))
                group.create_dataset(
                    "EventList", (1, 1, 1), dtype=h5py.vlen_dtype(np.dtype("i4"))
                )
                f.create_dataset("PeakData/PeakData", shape=(1, 1, 1, 1), dtype="f4")
            with self.assertRaises(InterruptedError):
                subvolume_spectrum(
                    path,
                    (0, 0, 0, 0),
                    (0, 0),
                    reserve=lambda _: nullcontext(),
                    cancel=lambda: True,
                )


if __name__ == "__main__":
    unittest.main()
