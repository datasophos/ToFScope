"""Admission for managed arrays and transport buffers; allocator RSS is separate."""

from collections import defaultdict
from threading import RLock
from tofscope.application.analyses import CapacityError


class Reservation:
    def __init__(self, budget, owner, analysis_id, n, physical):
        self.budget = budget
        self.owner = owner
        self.analysis_id = analysis_id
        self.n = n
        self.physical = physical
        self.released = False

    def release(self):
        with self.budget.lock:
            if self.released:
                return
            self.released = True
            if self.physical:
                self.budget.physical_bytes -= self.n
            if self.owner is not None:
                self.budget.users[self.owner] -= self.n
                self.budget.analyses[self.analysis_id] -= self.n

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.release()


class ResourceBudget:
    def __init__(self, settings):
        self.settings = settings
        self.lock = RLock()
        self.physical_bytes = 0
        self.users = defaultdict(int)
        self.analyses = defaultdict(int)

    def reserve(self, owner, analysis_id, bytes, physical=True):
        if type(bytes) is not int or bytes < 0:
            raise ValueError("An exact nonnegative allocation size is required.")
        with self.lock:
            s = self.settings
            if (physical and self.physical_bytes + bytes > s.global_bytes) or (
                owner is not None
                and (
                    self.users[owner] + bytes > s.user_bytes
                    or self.analyses[analysis_id] + bytes > s.analysis_bytes
                )
            ):
                raise CapacityError(
                    "Memory budget reached; hide profiles or close an analysis."
                )
            if physical:
                self.physical_bytes += bytes
            if owner is not None:
                self.users[owner] += bytes
                self.analyses[analysis_id] += bytes
            return Reservation(self, owner, analysis_id, bytes, physical)
