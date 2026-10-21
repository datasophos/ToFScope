import tempfile
import unittest
from pathlib import Path
import h5py
import numpy as np
from fixtures.acquisition import make_acquisition
from tofscope.science.integration import custom_peak_windows

class ReferenceFixtureTests(unittest.TestCase):
    def test_exact_union_and_stored_domain(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'fixture.h5';make_acquisition(p)
            before=p.read_bytes()
            np.testing.assert_array_equal(custom_peak_windows(p,[(1,2),(4,5)],0,2)[:,0,:],[[1,.25],[1,.5],[1,.75]])
            with h5py.File(p) as f:
                self.assertEqual(f['PeakData/PeakData'].shape,(3,1,2,2))
                self.assertEqual(f['FullSpectra/EventList'].shape,(4,1,2))
            self.assertEqual(p.read_bytes(),before)
