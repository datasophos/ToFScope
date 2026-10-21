from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Condition, RLock
import numpy as np
from tofscope.application.analyses import CapacityError


@dataclass
class CachedArray:
    array: np.ndarray
    physical: object
    consumers: dict = field(default_factory=dict)


class ArrayLease:
    def __init__(self, cache, key, consumer, array):
        self.cache = cache
        self.key = key
        self.consumer = consumer
        self.array = array
        self.released = False

    def release(self):
        with self.cache.condition:
            if self.released:
                return
            self.released = True
            entry = self.cache.entries.get(self.key)
            if entry is None:
                return
            count, reservation = entry.consumers[self.consumer]
            if count == 1:
                reservation.release()
                del entry.consumers[self.consumer]
            else:
                entry.consumers[self.consumer] = (count - 1, reservation)
            self.cache.condition.notify_all()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.release()


class ArrayCache:
    def __init__(self, repository, budget):
        self.repository = repository
        self.budget = budget
        self.entries = OrderedDict()
        self.loading = set()
        self.condition = Condition(RLock())

    def key(self, dataset, recipe, materialization_id=None):
        return (
            dataset.key,
            dataset.generation,
            recipe.source,
            recipe.stored_index,
            recipe.saved_id,
            recipe.intervals,
            recipe.frames,
            materialization_id,
        )

    def _evict(self, needed=None):
        for key, entry in list(self.entries.items()):
            if (
                needed is not None
                and self.budget.physical_bytes + needed
                <= self.budget.settings.global_bytes
            ):
                break
            if not entry.consumers:
                entry.physical.release()
                del self.entries[key]

    def clear(self):
        with self.condition:
            self._evict()

    def acquire(self, owner, analysis_id, dataset, recipe, loader, estimated_bytes, materialization_id=None):
        self.repository.assert_current(owner, dataset)
        key = self.key(dataset, recipe, materialization_id)
        consumer = (owner, analysis_id)
        with self.condition:
            while key in self.loading:
                self.condition.wait()
            if key in self.entries:
                return self._lease(owner, analysis_id, dataset, key, consumer)
            try:
                physical = self.budget.reserve(None, None, estimated_bytes)
            except CapacityError:
                self._evict(estimated_bytes)
                physical = self.budget.reserve(None, None, estimated_bytes)
            try:
                logical = self.budget.reserve(
                    owner, analysis_id, estimated_bytes, physical=False
                )
            except BaseException:
                physical.release()
                raise
            self.loading.add(key)
        try:
            array = loader()
            if not isinstance(array, np.ndarray) or array.nbytes != estimated_bytes:
                raise CapacityError(
                    "Reader allocation did not match its preflight shape/dtype."
                )
            self.repository.assert_current(owner, dataset)
            array.setflags(write=False)
            with self.condition:
                self.entries[key] = CachedArray(
                    array, physical, {consumer: (1, logical)}
                )
                return ArrayLease(self, key, consumer, array)
        except BaseException:
            physical.release()
            logical.release()
            raise
        finally:
            with self.condition:
                self.loading.remove(key)
                self.condition.notify_all()

    def _lease(self, owner, aid, dataset, key, consumer):
        self.repository.assert_current(owner, dataset)
        entry = self.entries[key]
        if consumer in entry.consumers:
            n, res = entry.consumers[consumer]
            entry.consumers[consumer] = (n + 1, res)
        else:
            entry.consumers[consumer] = (
                1,
                self.budget.reserve(
                    owner, aid, int(entry.array.nbytes), physical=False
                ),
            )
        self.entries.move_to_end(key)
        return ArrayLease(self, key, consumer, entry.array)

    def load(self, owner, aid, dataset, recipe, materialization_id=None, **kwargs):
        with self.repository.access(owner, dataset) as path:
            import h5py

            with h5py.File(path, "r") as f:
                shape = f["PeakData/PeakData"].shape
        n = (recipe.frames[1] - recipe.frames[0] + 1) * shape[1] * shape[2] * 4
        if recipe.source == "custom":
            kwargs["reserve"] = lambda size: self.budget.reserve(owner, aid, size)
        return self.acquire(
            owner,
            aid,
            dataset,
            recipe,
            lambda: self.repository.read(owner, dataset, recipe, materialization_id=materialization_id, **kwargs),
            n,
            materialization_id=materialization_id,
        )

    def invalidate(self, dataset_key, generation):
        with self.condition:
            for key, entry in list(self.entries.items()):
                if key[:2] == (dataset_key, generation) and not entry.consumers:
                    entry.physical.release()
                    del self.entries[key]
