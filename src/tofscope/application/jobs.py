"""Bounded round-robin user scheduling, with one active job per user."""

from collections import OrderedDict, deque
from dataclasses import dataclass, replace, field
from threading import Condition, Event, RLock, Thread
import json
import time
from uuid import uuid4
from tofscope.application.workspaces import CapacityError
from tofscope.application.commands import AllDepth
from tofscope.science.integration import canonical_intervals
from tofscope.science.signals import SignalRecipe

TERMINAL = {"succeeded", "failed", "cancelled", "obsolete"}


@dataclass(frozen=True)
class IntegrationSpec:
    intervals: tuple[tuple[float, float], ...]
    frames: tuple[int, int]
    target: str


@dataclass(frozen=True)
class JobSnapshot:
    id: str
    analysis_id: str
    status: str
    done: int = 0
    total: int = 0
    safe_error: str | None = None


@dataclass
class Job:
    snapshot: JobSnapshot
    owner: str
    source: object
    recipe: SignalRecipe
    target: str
    token: int
    cancelled: Event = field(default_factory=Event)


class JobService:
    def __init__(self, workspaces, explore, cache, settings):
        self.workspaces = workspaces
        self.explore = explore
        self.cache = cache
        self.settings = settings
        self.jobs = OrderedDict()
        self.pending = {}
        self.users = deque()
        self.running = set()
        self.condition = Condition(RLock())
        self.stopping = False
        self.threads = [
            Thread(target=self._worker, daemon=True, name=f"tofscope-job-{i}")
            for i in range(settings.workers)
        ]
        workspaces.on_close.append(self.close_analysis)
        for thread in self.threads:
            thread.start()

    def submit(self, owner, analysis_id, envelope, spec):
        e = self.workspaces.entry(owner, analysis_id)
        fingerprint = json.dumps(
            {"envelope": envelope.model_dump(mode="json"), "spec": spec.__dict__},
            sort_keys=True,
        )
        with e.lock:
            old = self.explore.validate_envelope(e, envelope, fingerprint)
            if old is not None:
                return old
            s = e.snapshot
            if (
                spec.target == "comparison"
                and len(s.comparisons) >= self.settings.comparisons_per_analysis
            ):
                raise CapacityError(
                    "Comparison quota reached; remove a comparison first."
                )
            windows = canonical_intervals(spec.intervals, s.mass_limits)
            if spec.target not in ("active", "comparison"):
                raise ValueError("Unknown integration target.")
            first, last = spec.frames
            if (
                type(first) is not int
                or type(last) is not int
                or not 0 <= first <= last < s.shape[0]
            ):
                raise ValueError("Integration frames outside stored domain.")
            with self.condition:
                active = [
                    j for j in self.jobs.values() if j.snapshot.status not in TERMINAL
                ]
                if (
                    len(active) >= self.settings.jobs_global
                    or sum(j.owner == owner for j in active)
                    >= self.settings.jobs_per_user
                    or sum(j.snapshot.analysis_id == analysis_id for j in active)
                    >= self.settings.jobs_per_analysis
                ):
                    raise CapacityError("Integration queue full; wait or cancel a job.")
                e.tokens[spec.target] += 1
                recipe = SignalRecipe(
                    intervals=windows,
                    frames=tuple(spec.frames),
                    label=" ∪ ".join(f"{lo:g}–{hi:g}" for lo, hi in windows) + " Th",
                )
                if spec.target == "comparison":
                    recipe = replace(
                        recipe,
                        label=recipe.label
                        + f" · frames {first}–{last} · #{len(s.comparisons) + 1}",
                    )
                snap = JobSnapshot(
                    str(uuid4()), analysis_id, "queued", total=last - first + 1
                )
                self.jobs[snap.id] = Job(
                    snap, owner, s.dataset, recipe, spec.target, e.tokens[spec.target]
                )
                self.pending.setdefault(owner, deque()).append(snap.id)
                if owner not in self.users:
                    self.users.append(owner)
                self.explore.receipt(e, envelope.request_id, fingerprint, snap)
                self.condition.notify_all()
                # Keep a bounded terminal receipt history; live jobs are never removed.
                terminal = [
                    id
                    for id, j in self.jobs.items()
                    if j.owner == owner and j.snapshot.status in TERMINAL
                ]
                for id in terminal[:-256]:
                    del self.jobs[id]
                return snap

    def get(self, owner, job_id):
        with self.condition:
            j = self.jobs.get(job_id)
            if j is None or j.owner != owner:
                raise KeyError("Job unavailable.")
            return j.snapshot

    def cancel(self, owner, job_id):
        with self.condition:
            snap = self.get(owner, job_id)
            j = self.jobs[job_id]
            if snap.status not in TERMINAL:
                j.cancelled.set()
                if snap.status == "queued":
                    j.snapshot = replace(snap, status="cancelled")
            self.condition.notify_all()
            return j.snapshot

    def close_analysis(self, analysis_id):
        with self.condition:
            for id, j in self.jobs.items():
                if (
                    j.snapshot.analysis_id == analysis_id
                    and j.snapshot.status not in TERMINAL
                ):
                    self.cancel(j.owner, id)

    def _next(self):
        for _ in range(len(self.users)):
            owner = self.users.popleft()
            q = self.pending[owner]
            while q and self.jobs[q[0]].snapshot.status in TERMINAL:
                q.popleft()
            if not q:
                continue
            self.users.append(owner)
            if owner in self.running:
                continue
            id = q.popleft()
            self.running.add(owner)
            j = self.jobs[id]
            j.snapshot = replace(j.snapshot, status="running")
            return j
        return None

    def _worker(self):
        while True:
            with self.condition:
                j = self._next()
                while j is None and not self.stopping:
                    self.condition.wait()
                    j = self._next()
                if self.stopping and j is None:
                    return
            lease = None
            scratch = None
            try:
                aid = j.snapshot.analysis_id
                e = self.workspaces.entry(j.owner, aid)

                def current():
                    return (
                        not e.closed
                        and e.snapshot.dataset == j.source
                        and e.tokens[j.target] == j.token
                    )

                def cancelled():
                    return j.cancelled.is_set() or not current()

                if cancelled():
                    raise InterruptedError()
                # Budget NumPy/event conversion workspace separately from retained output.
                scratch = self.cache.budget.reserve(
                    j.owner,
                    aid,
                    min(
                        64 * 1024**2,
                        max(1024, e.snapshot.shape[1] * e.snapshot.shape[2] * 4096),
                    ),
                )

                def progress(done, total):
                    with self.condition:
                        j.snapshot = replace(j.snapshot, done=done, total=total)

                lease = self.cache.load(
                    j.owner,
                    aid,
                    j.source,
                    j.recipe,
                    progress=progress,
                    cancel=cancelled,
                )
                with e.lock:
                    if cancelled():
                        raise InterruptedError()
                    self.cache.repository.assert_current(j.owner, j.source)
                    s = e.snapshot
                    if j.target == "active":
                        previous = e.leases.pop(s.active_recipe.id, None)
                        if previous:
                            previous.release()
                        result = replace(
                            s,
                            revision=s.revision + 1,
                            active_recipe=j.recipe,
                            loaded_frames=j.recipe.frames,
                            depth=AllDepth(),
                        )
                    else:
                        result = replace(
                            s,
                            revision=s.revision + 1,
                            comparisons=s.comparisons + (j.recipe,),
                        )
                    e.leases[j.recipe.id] = lease
                    lease = None
                    e.snapshot = result
                    with self.condition:
                        j.snapshot = replace(
                            j.snapshot, status="succeeded", done=j.snapshot.total
                        )
            except (InterruptedError, KeyError):
                with self.condition:
                    j.snapshot = replace(
                        j.snapshot,
                        status="cancelled" if j.cancelled.is_set() else "obsolete",
                    )
            except Exception as exc:
                with self.condition:
                    j.snapshot = replace(
                        j.snapshot,
                        status="obsolete"
                        if "changed" in str(exc).lower()
                        else "failed",
                        safe_error="Integration failed; check source/calibration or narrow the frame range."
                        if not isinstance(exc, CapacityError)
                        else str(exc),
                    )
            finally:
                if lease:
                    lease.release()
                if scratch:
                    scratch.release()
                with self.condition:
                    self.running.discard(j.owner)
                    self.condition.notify_all()

    def wait(self, owner, job_id, timeout=30):
        deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                s = self.get(owner, job_id)
                if s.status in TERMINAL:
                    return s
                left = deadline - time.monotonic()
                if left <= 0:
                    raise TimeoutError("Job did not complete.")
                self.condition.wait(left)

    def shutdown(self):
        with self.condition:
            self.stopping = True
            for j in self.jobs.values():
                if j.snapshot.status not in TERMINAL:
                    self.cancel(j.owner, j.snapshot.id)
            self.condition.notify_all()
        for thread in self.threads:
            thread.join(timeout=35)
        self.cache.clear()
