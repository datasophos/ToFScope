"""Bounded round-robin user scheduling, with one active job per user."""

from collections import OrderedDict, deque
from dataclasses import dataclass, replace, field
from threading import Condition, Event, RLock, Thread
import json
import time
from uuid import uuid4
from typing import Literal
from tofscope.storage.saved_files import SavedFile
from tofscope.application.analyses import CapacityError
from tofscope.application.models import SignalSnapshot
from tofscope.application.signals import get_signal, normalize_view, valid_name
from tofscope.science.integration import canonical_intervals
from tofscope.science.signals import SignalRecipe

TERMINAL = {"succeeded", "failed", "cancelled", "obsolete"}


@dataclass(frozen=True)
class IntegrationSpec:
    intervals: tuple[tuple[float, float], ...]
    frames: tuple[int, int]
    name: str
    signal_id: str | None = None
    expected_recipe_version: int | None = None
    candidate_id: str | None = None
    measured_mz: float | None = None


@dataclass(frozen=True)
class JobSnapshot:
    id: str
    analysis_id: str
    status: str
    signal_id: str = ""
    recipe_version: int = 0
    done: int = 0
    total: int = 0
    safe_error: str | None = None
    kind: Literal["integration", "save", "preparation", "measurement"] = "integration"
    stage: str = ""
    saved_file: SavedFile | None = None
    saved_revision: int | None = None


@dataclass
class Job:
    snapshot: JobSnapshot
    owner: str
    source: object
    recipe: SignalRecipe
    signal_id: str
    token: int
    name_revision: int
    referenced: bool = True
    cancelled: Event = field(default_factory=Event)
    task: object = None


class JobService:
    def __init__(self, workspaces, explore, cache, settings):
        self.analyses = workspaces
        self.explore = explore
        self.cache = cache
        self.settings = settings
        self.jobs = OrderedDict()
        self.pending = {}
        self.users = deque()
        self.running = set()
        self.condition = Condition(RLock())
        self.stopping = False
        self.save_handler = None
        self.preparation_handler = None
        self.measurement_handler = None
        self.threads = [
            Thread(target=self._worker, daemon=True, name=f"tofscope-job-{i}")
            for i in range(settings.workers)
        ]
        workspaces.on_close.append(self.close_analysis)
        workspaces.on_remove.append(self.remove_signal)
        for thread in self.threads:
            thread.start()

    def submit(self, owner, analysis_id, envelope, spec):
        e = self.analyses.entry(owner, analysis_id)
        fingerprint = json.dumps(
            {"envelope": envelope.model_dump(mode="json"), "spec": spec.__dict__},
            sort_keys=True,
        )
        with self.analyses.signal_lock, e.lock:
            old = self.explore.validate_envelope(e, envelope, fingerprint)
            if old is not None:
                return old
            s = e.snapshot
            name = valid_name(spec.name)
            windows = canonical_intervals(spec.intervals, s.mass_limits)
            from tofscope.application.identification import assignment
            atomic_assignment = assignment(spec.candidate_id, spec.measured_mz) if spec.candidate_id else None
            if spec.signal_id is not None:
                signal = get_signal(s, spec.signal_id)
                if signal.recipe is not None and signal.recipe.source != 'custom':
                    raise ValueError('Stored channels require a custom copy before raw integration.')
                if spec.expected_recipe_version != signal.recipe_version:
                    raise ValueError('Signal recipe changed; refresh before calculating.')
            else:
                self.analyses.admit_signal(owner, len(s.signals))
                signal = SignalSnapshot(str(uuid4()), name, s.next_style_index, None, 0)
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
                token = e.tokens.get(signal.id, 0) + 1
                e.tokens[signal.id] = token
                recipe = SignalRecipe(id=signal.id, intervals=windows, frames=tuple(spec.frames), label=name)
                snap = JobSnapshot(str(uuid4()), analysis_id, 'queued', signal.id,
                                   signal.recipe_version+1, total=last-first+1)
                self.jobs[snap.id] = Job(snap, owner, s.dataset, recipe, signal.id, token, signal.name_revision)
                if signal.job_id in self.jobs:
                    self.jobs[signal.job_id].referenced = False
                updated = replace(signal, job_id=snap.id, assignment=atomic_assignment if spec.candidate_id else signal.assignment)
                signals = tuple(updated if r.id == signal.id else r for r in s.signals)
                if spec.signal_id is None:
                    signals = (*signals, updated)
                e.snapshot = replace(s, signals=signals, revision=s.revision+1,
                                     next_style_index=s.next_style_index+(spec.signal_id is None))
                self.pending.setdefault(owner, deque()).append(snap.id)
                if owner not in self.users:
                    self.users.append(owner)
                self.explore.receipt(e, envelope.request_id, fingerprint, snap)
                self.condition.notify_all()
                # Keep a bounded terminal receipt history; live jobs are never removed.
                terminal = [
                    id
                    for id, j in self.jobs.items()
                    if j.owner == owner and j.snapshot.status in TERMINAL and not j.referenced
                ]
                for id in terminal[:-256]:
                    del self.jobs[id]
                return snap

    def enqueue_save(self, owner, task):
        return self.enqueue_task(owner, task, 'save', task.snapshot.id, task.snapshot.revision)

    def enqueue_task(self, owner, task, kind, aid, saved_revision=None):
        with self.condition:
            active = [j for j in self.jobs.values() if j.snapshot.status not in TERMINAL]
            if (len(active) >= self.settings.jobs_global or
                    sum(j.owner == owner for j in active) >= self.settings.jobs_per_user or
                    sum(j.snapshot.analysis_id == aid for j in active) >= self.settings.jobs_per_analysis):
                raise CapacityError('Work queue full; wait or cancel a job.')
            snap = JobSnapshot(str(uuid4()), aid, 'queued', kind=kind, saved_revision=saved_revision)
            source = task.snapshot.dataset if kind in {'save', 'measurement'} else task.source
            self.jobs[snap.id] = Job(snap, owner, source, None, '', 0, 0, referenced=False, task=task)
            self.pending.setdefault(owner, deque()).append(snap.id)
            if owner not in self.users:
                self.users.append(owner)
            terminal = [id for id, j in self.jobs.items() if j.owner == owner and j.snapshot.status in TERMINAL and not j.referenced]
            for id in terminal[:-256]:
                del self.jobs[id]
            self.condition.notify_all()
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

    def remove_signal(self, analysis_id, signal_id):
        with self.condition:
            for jid, job in self.jobs.items():
                if job.snapshot.analysis_id == analysis_id and job.signal_id == signal_id:
                    job.referenced = False
                    self.cancel(job.owner, jid)

    def close_analysis(self, analysis_id):
        with self.condition:
            for jid, job in self.jobs.items():
                if job.snapshot.analysis_id == analysis_id:
                    job.referenced = False
                    self.cancel(job.owner, jid)

    def _next(self):
        for _ in range(len(self.users)):
            owner = self.users.popleft()
            q = self.pending[owner]
            while q and (q[0] not in self.jobs or self.jobs[q[0]].snapshot.status in TERMINAL):
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
            try:
                if j.snapshot.kind in {'save', 'preparation', 'measurement'}:
                    if j.cancelled.is_set():
                        raise InterruptedError()
                    handler = {'save': self.save_handler, 'preparation': self.preparation_handler, 'measurement': self.measurement_handler}[j.snapshot.kind]
                    result = handler(j)
                    with self.condition:
                        j.snapshot = replace(j.snapshot, status='succeeded', saved_file=result, done=j.snapshot.total)
                    continue
                aid = j.snapshot.analysis_id
                e = self.analyses.entry(j.owner, aid)

                def current():
                    return (
                        not e.closed
                        and e.snapshot.dataset == j.source
                        and e.tokens.get(j.signal_id) == j.token
                        and any(r.id == j.signal_id for r in e.snapshot.signals)
                    )

                def cancelled():
                    return j.cancelled.is_set() or not current()

                if cancelled():
                    raise InterruptedError()

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
                    old = get_signal(s, j.signal_id)
                    name = old.name if old.name_revision != j.name_revision else j.recipe.label
                    updated = replace(old, name=name, recipe=j.recipe, recipe_version=j.snapshot.recipe_version, materialization_id=None)
                    result = normalize_view(replace(s, revision=s.revision+1,
                        signals=tuple(updated if r.id == old.id else r for r in s.signals),
                        profile_signal_ids=tuple(dict.fromkeys((*s.profile_signal_ids, old.id))) if old.recipe is None else s.profile_signal_ids))
                    if result.isotope_measurement:
                        from tofscope.application.identification import current_result
                        result = replace(result, isotope_measurement=current_result(result))
                    previous = e.leases.pop(old.id, None)
                    if previous:
                        previous.release()
                    if old.id in result.profile_signal_ids or old.id == result.image_signal_id:
                        e.leases[old.id] = lease
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
                        status="cancelled" if j.cancelled.is_set() else "obsolete"
                        if "changed" in str(exc).lower()
                        else "failed",
                        safe_error=("Isotope measurement failed; check source, coverage and memory limits." if j.snapshot.kind == "measurement" else "Preparing raw data failed; check free space, source/calibration and output name." if j.snapshot.kind == "preparation" else "Saving failed; check free space, output name and current analysis revision." if j.snapshot.kind == "save" else "Integration failed; check source/calibration or narrow the frame range.")
                        if not isinstance(exc, CapacityError)
                        else str(exc),
                    )
            finally:
                if lease:
                    lease.release()
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
