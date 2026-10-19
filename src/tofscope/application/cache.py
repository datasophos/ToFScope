from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Condition, RLock
import numpy as np
from tofscope.application.workspaces import CapacityError


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

    def key(self, dataset, recipe):
        return (
            dataset.key,
            dataset.generation,
            recipe.source,
            recipe.stored_index,
            recipe.saved_id,
            recipe.intervals,
            recipe.frames,
        )

    def _evict(self):
        for key, entry in list(self.entries.items()):
            if not entry.consumers:
                entry.physical.release()
                del self.entries[key]

    def clear(self):
        with self.condition:
            self._evict()

    def acquire(self, owner, analysis_id, dataset, recipe, loader, estimated_bytes):
        self.repository.assert_current(owner, dataset)
        key = self.key(dataset, recipe)
        consumer = (owner, analysis_id)
        with self.condition:
            while key in self.loading:
                self.condition.wait()
            if key in self.entries:
                return self._lease(owner, analysis_id, dataset, key, consumer)
            self._evict()
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

    def load(self, owner, aid, dataset, recipe, **kwargs):
        m = self.repository.metadata(owner, dataset)
        n = (recipe.frames[1] - recipe.frames[0] + 1) * m.shape[1] * m.shape[2] * 4
        return self.acquire(
            owner,
            aid,
            dataset,
            recipe,
            lambda: self.repository.read(owner, dataset, recipe, **kwargs),
            n,
        )

    def invalidate(self, dataset_key, generation):
        with self.condition:
            for key, entry in list(self.entries.items()):
                if key[:2] == (dataset_key, generation) and not entry.consumers:
                    entry.physical.release()
                    del self.entries[key]
