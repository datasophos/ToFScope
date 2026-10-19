import tempfile
import unittest
import weakref
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

import h5py
import numpy as np

from tofscope.application.resources import ResourceBudget
from tofscope.application.workspaces import CapacityError
from tofscope.config import Settings
from tofscope.science.integration import integrate_event_windows
from tofscope.storage.bounded_events import admitted_events


class BoundedEventTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = Settings(self.root, runtime_dir=self.root / "runtime")
        self.budget = ResourceBudget(self.settings)
        self.path = self.root / "raw.h5"
        with h5py.File(self.path, "w") as f:
            raw = f.create_dataset("events", (1, 8, 8), dtype=h5py.vlen_dtype(np.dtype("i4")))
            for y in range(8):
                for x in range(8):
                    size = (0, 1, 20, 2000)[(x + y) % 4]
                    raw[0, y, x] = np.arange(size, dtype="i4") - 1

    def reserve(self, size):
        return self.budget.reserve("a", "analysis", size)

    def test_admission_batches_allocations_and_preserves_exact_cell_counts(self):
        requests = []
        def reserve(size):
            requests.append(size)
            return self.reserve(size)
        with h5py.File(self.path, "r") as f:
            expected = integrate_event_windows(f["events"][0], np.arange(10.), 2, 4, [(1, 2), (4, 5)])
            with admitted_events(f["events"], 0, reserve) as events:
                self.assertGreater(self.budget.physical_bytes, 0)
                actual = integrate_event_windows(events, np.arange(10.), 2, 4, [(1, 2), (4, 5)])
                np.testing.assert_array_equal(actual, expected)
        self.assertEqual(self.budget.physical_bytes, 0)
        self.assertLessEqual(len(requests), 16, "Reserve scratch in batches, not for every pixel")

    def test_oversized_cell_is_refused_before_payload_allocation_and_releases_budget(self):
        with h5py.File(self.path, "w") as f:
            f.create_dataset("events", (1, 1, 1), dtype=h5py.vlen_dtype(np.dtype("u4")))[0, 0, 0] = np.ones(100000, dtype="u4")
        self.budget.settings = replace(self.settings, global_bytes=100000, user_bytes=100000, analysis_bytes=100000)
        with h5py.File(self.path, "r") as f, patch("tofscope.storage.bounded_events.np.empty", side_effect=AssertionError("payload allocated before admission")):
            with self.assertRaises(CapacityError):
                with admitted_events(f["events"], 0, self.reserve):
                    self.fail("Unadmitted events were exposed")
        self.assertEqual(self.budget.physical_bytes, 0)
        self.assertEqual(self.budget.users["a"], 0)

    def test_caller_failure_releases_all_scratch(self):
        with h5py.File(self.path, "r") as f:
            with self.assertRaisesRegex(RuntimeError, "caller"):
                with admitted_events(f["events"], 0, self.reserve):
                    raise RuntimeError("caller")
        self.assertEqual(self.budget.physical_bytes, 0)

    def test_arena_memory_does_not_outlive_the_read_context(self):
        references = []
        empty = np.empty
        def allocate(*args, **kwargs):
            array = empty(*args, **kwargs)
            references.append(weakref.ref(array))
            return array
        with h5py.File(self.path, "r") as f, patch("tofscope.storage.bounded_events.np.empty", side_effect=allocate):
            with admitted_events(f["events"], 0, self.reserve) as events:
                self.assertTrue(any(ref() is not None for ref in references))
            # The packed numerical values may remain borrowed by the caller;
            # HDF5's arena buffers must already have been freed.
            self.assertTrue(references)
            self.assertTrue(all(ref() is None for ref in references))
        self.assertEqual(self.budget.physical_bytes, 0)

    def test_budget_failure_after_partial_read_releases_all_arenas(self):
        self.budget.settings = replace(self.settings, global_bytes=200000, user_bytes=200000, analysis_bytes=200000)
        with h5py.File(self.path, "r") as f, patch("tofscope.storage.bounded_events.np.empty", wraps=np.empty) as allocate:
            with self.assertRaises(CapacityError):
                with admitted_events(f["events"], 0, self.reserve):
                    self.fail("Partial read escaped admission")
            self.assertGreater(allocate.call_count, 0)
        self.assertEqual(self.budget.physical_bytes, 0)
        self.assertEqual(self.budget.users["a"], 0)

    def test_independent_concurrent_reads_do_not_share_arenas_or_reservations(self):
        def run(owner):
            with h5py.File(self.path, "r") as f:
                with admitted_events(f["events"], 0, lambda size: self.budget.reserve(owner, owner, size)) as events:
                    return integrate_event_windows(events, np.arange(10.), 2, 4, [(1, 2), (4, 5)])
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(run, ("a", "b")))
        np.testing.assert_array_equal(*results)
        self.assertEqual(self.budget.physical_bytes, 0)
        self.assertEqual(dict(self.budget.users), {"a": 0, "b": 0})

    def test_empty_cells_and_integer_byte_orders_preserve_stored_samples(self):
        for dtype in ("u2", ">u4", "i8", "u8"):
            with self.subTest(dtype=dtype):
                with h5py.File(self.path, "w") as f:
                    raw = f.create_dataset("events", (1, 1, 2), dtype=h5py.vlen_dtype(np.dtype(dtype)))
                    raw[0, 0, 0] = np.array([], dtype=dtype)
                    raw[0, 0, 1] = np.array([0, 1, 2, 4, 8], dtype=dtype)
                with h5py.File(self.path, "r") as f:
                    # Exact stored timestamps 2 and 4 select two samples / normalization 4.
                    # h5py's high-level VLEN path does not preserve nonnative byte order.
                    expected = np.array([[0, 0.5]], dtype="f4")
                    with admitted_events(f["events"], 0, self.reserve) as events:
                        np.testing.assert_array_equal(integrate_event_windows(events, np.arange(10.), 2, 4, [(1, 2)]), expected)
                self.assertEqual(self.budget.physical_bytes, 0)


if __name__ == "__main__":
    unittest.main()
