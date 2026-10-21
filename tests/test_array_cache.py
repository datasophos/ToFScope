from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
import numpy as np
from service_fixture import setup_case
from tofscope.application.cache import ArrayCache
from tofscope.application.resources import ResourceBudget
from tofscope.application.analyses import CapacityError
from tofscope.science.signals import SignalRecipe


class CacheTests(unittest.TestCase):
    def setUp(self):
        setup_case(self, global_bytes=64, user_bytes=64, analysis_bytes=64)
        self.budget = ResourceBudget(self.settings)
        self.cache = ArrayCache(self.repo, self.budget)
        self.r = SignalRecipe(
            source="stored", stored_index=0, intervals=((1, 3),), frames=(0, 2)
        )

    def test_leases_single_flight_and_authorization(self):
        count = []

        def load():
            count.append(1)
            return np.ones((3, 1, 2), dtype="float32")

        with ThreadPoolExecutor(2) as pool:
            a, b = list(
                pool.map(
                    lambda owner: self.cache.acquire(
                        owner, owner, self.dataset, self.r, load, 24
                    ),
                    ["a", "b"],
                )
            )
        self.assertEqual(len(count), 1)
        self.assertFalse(a.array.flags.writeable)
        self.assertEqual(self.budget.physical_bytes, 24)
        a.release()
        np.testing.assert_array_equal(b.array, 1)
        self.assertEqual(self.budget.physical_bytes, 24)
        self.repo.authorize = lambda o, p: o != "denied"
        with self.assertRaises(PermissionError):
            self.cache.acquire("denied", "d", self.dataset, self.r, load, 24)
        b.release()
        self.cache.clear()
        self.assertEqual(self.budget.physical_bytes, 0)

    def test_reservations_precede_allocation_and_release_on_failure(self):
        reservation = self.budget.reserve("a", "a", 48)
        with self.assertRaises(CapacityError):
            self.budget.reserve("b", "b", 32)
        reservation.release()
        self.assertEqual(self.budget.physical_bytes, 0)

        def bad():
            raise ValueError("bad data")

        with self.assertRaises(ValueError):
            self.cache.acquire("a", "a", self.dataset, self.r, bad, 24)
        self.assertEqual(self.budget.physical_bytes, 0)
    def test_byte_lru_keeps_unleased_arrays_until_pressure(self):
        from dataclasses import replace
        recipes=[self.r,replace(self.r,stored_index=1),replace(self.r,frames=(1,2)),replace(self.r,frames=(0,0))]
        for r in recipes[:3]:
            self.cache.load('a','a',self.dataset,r).release()
        self.assertEqual(len(self.cache.entries),3);self.assertEqual(self.budget.physical_bytes,64)
        self.cache.load('a','a',self.dataset,recipes[3]).release()
        self.assertEqual(len(self.cache.entries),3);self.assertEqual(self.budget.physical_bytes,48)
