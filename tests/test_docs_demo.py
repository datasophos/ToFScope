"""The synthetic documentation fixture must be reproducible and consistent."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import h5py
import numpy as np

from scripts.docs_capture import generate_demo


class DocumentationDemoTests(unittest.TestCase):
    def test_generated_counts_match_raw_events_and_are_deterministic(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(generate_demo, "SIZE", 8),
        ):
            first = generate_demo.generate(Path(directory) / "first.h5")
            second = generate_demo.generate(Path(directory) / "second.h5")
            with h5py.File(first) as a, h5py.File(second) as b:
                self.assertEqual(a["PeakData/PeakData"].shape, (8, 8, 8, 4))
                np.testing.assert_array_equal(
                    a["PeakData/PeakData"][:], b["PeakData/PeakData"][:]
                )
                np.testing.assert_array_equal(
                    a["FullSpectra/SumSpectrum"][:], b["FullSpectra/SumSpectrum"][:]
                )
                axis = a["FullSpectra/MassAxis"][:]
                table = a["PeakData/PeakTable"][:]
                for z, y, x in [(0, 0, 0), (4, 3, 2), (7, 7, 7)]:
                    events = a["FullSpectra/EventList"][z, y, x]
                    np.testing.assert_array_equal(
                        events, b["FullSpectra/EventList"][z, y, x]
                    )
                    masses = axis[events]
                    actual = [
                        np.count_nonzero(
                            (masses >= row["lower integration limit"])
                            & (masses <= row["upper integration limit"])
                        )
                        for row in table
                    ]
                    np.testing.assert_array_equal(
                        actual, a["PeakData/PeakData"][z, y, x]
                    )


if __name__ == "__main__":
    unittest.main()
