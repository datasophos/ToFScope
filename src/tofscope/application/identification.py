"""Owner-scoped atomic matching and explicit, bounded isotope measurements."""
from dataclasses import dataclass, replace, asdict
import hashlib
import json
import numpy as np
from tofscope.application.identification_models import (
    AtomicAssignment, CatalogProvenance, CandidateResult, MeasuredSignal, MeasurementResult,
)
from tofscope.application.signals import get_signal
from tofscope.application.analyses import CapacityError
from tofscope.science.isotopes import CATALOG_PATH, load_catalog, find_candidates, ion_mz, CandidateLimitExceeded
from tofscope.science.abundance import measure_isotopes


def catalog_provenance():
    meta = json.loads(CATALOG_PATH.read_text())['metadata']
    return CatalogProvenance(meta['records_sha256'], meta['retrieved'], json.dumps(meta['sources'], sort_keys=True))


def assignment(candidate_id, measured_mz=None):
    if candidate_id is None:
        return None
    for isotope in load_catalog():
        for charge in (-3, -2, -1, 1, 2, 3):
            if candidate_id == f'{isotope.symbol}-{isotope.mass_number}:{charge:+d}':
                predicted = ion_mz(isotope, charge)
                error = measured_mz - predicted if measured_mz is not None else None
                return AtomicAssignment(candidate_id, isotope, charge, predicted, catalog_provenance(),
                                        measured_mz, error, error / predicted * 1e6 if error is not None else None)
    raise ValueError('Atomic candidate unavailable.')


def requested_frames(snapshot):
    depth = snapshot.depth
    return ((depth.index, depth.index) if depth.mode == 'frame' else
            (depth.first, depth.last) if depth.mode == 'window' else (0, snapshot.shape[0] - 1))


def dependency_key(snapshot, ids):
    rows = []
    for sid in ids:
        signal = get_signal(snapshot, sid)
        rows.append((sid, signal.recipe_version, asdict(signal.recipe) if signal.recipe else None,
                     signal.materialization_id, asdict(signal.assignment) if signal.assignment else None))
    value = (snapshot.dataset.generation, snapshot.roi, requested_frames(snapshot), rows)
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def current_result(snapshot):
    result = snapshot.isotope_measurement
    if result is None:
        return None
    try:
        stale = snapshot.stale or result.dependency_key != dependency_key(snapshot, [r.signal_id for r in result.rows])
    except ValueError:
        stale = True
    return replace(result, out_of_date=stale)


@dataclass(frozen=True)
class MeasurementTask:
    snapshot: object
    signal_ids: tuple[str, ...]
    dependency_key: str


class IdentificationService:
    def __init__(self, analyses, explore, cache, jobs):
        self.analyses, self.explore, self.cache, self.jobs = analyses, explore, cache, jobs
        self.catalog = load_catalog()
        self.provenance = catalog_provenance()
        jobs.measurement_handler = self.run

    def candidates(self, owner, aid, mz, tolerance, unit, charges):
        s = self.analyses.get(owner, aid)
        self.cache.repository.assert_current(owner, s.dataset)
        limit = min(256, max(0, (self.jobs.settings.response_bytes - 4096) // 2048))
        try:
            candidates = find_candidates(mz, tolerance, unit, charges, self.catalog, max_results=limit)
        except CandidateLimitExceeded as exc:
            raise CapacityError(str(exc)) from None
        return CandidateResult(tuple(candidates), self.provenance)

    def measure(self, owner, aid, envelope, recipe_ids):
        ids = tuple(recipe_ids)
        fingerprint = json.dumps({'isotopes': ids, 'envelope': envelope.model_dump(mode='json')}, sort_keys=True)
        e = self.analyses.entry(owner, aid)
        with e.lock:
            old = self.explore.validate_envelope(e, envelope, fingerprint)
            if old is not None:
                return old
            s = e.snapshot
            if not ids or len(ids) > 128 or len(set(ids)) != len(ids):
                raise ValueError('Choose 1–128 distinct ready signals.')
            if any(get_signal(s, sid).recipe is None for sid in ids):
                raise ValueError('Finish signal calculations before measuring.')
            task = MeasurementTask(s, ids, dependency_key(s, ids))
            with self.jobs.condition:
                job = self.jobs.enqueue_task(owner, task, 'measurement', aid)
                self.jobs.jobs[job.id].referenced = True
                previous = self.jobs.jobs.get(s.isotope_job_id)
                if previous:
                    previous.referenced = False
                terminal = [jid for jid, item in self.jobs.jobs.items()
                            if item.owner == owner and not item.referenced and
                            item.snapshot.status in {'succeeded', 'failed', 'cancelled', 'obsolete'}]
                for jid in terminal[:-256]:
                    del self.jobs.jobs[jid]
            # A new explicit measurement supersedes an earlier pending result.
            e.snapshot = replace(s, revision=s.revision+1, isotope_job_id=job.id)
            self.explore.receipt(e, envelope.request_id, fingerprint, job)
            return job

    def result(self, owner, aid):
        s = self.analyses.get(owner, aid)
        self.cache.repository.assert_current(owner, s.dataset)
        return current_result(s)

    def run(self, job):
        task = job.task
        s = task.snapshot
        e = self.analyses.entry(job.owner, s.id)
        signals = tuple(get_signal(s, sid) for sid in task.signal_ids)

        def cancelled():
            return (job.cancelled.is_set() or e.closed or e.snapshot.dataset != s.dataset or
                    e.snapshot.isotope_job_id != job.snapshot.id)

        def check():
            if cancelled():
                raise InterruptedError()

        def read(path, recipe):
            with e.lock:
                check()
            signal = next(row for row in signals if row.recipe.id == recipe.id)
            return self.cache.load(job.owner, s.id, s.dataset, recipe,
                materialization_id=signal.materialization_id, cancel=cancelled)

        # The numerical routine owns one lease at a time; it never accumulates volumes.
        rows = measure_isotopes(None, [r.recipe for r in signals], s.roi, requested_frames(s), reader=read)
        if any(r.summed_intensity is not None and not np.isfinite(r.summed_intensity) for r in rows):
            raise ValueError('Non-finite measurement intensity.')
        result = MeasurementResult(job.snapshot.id, s.dataset.generation, s.roi, requested_frames(s),
            task.dependency_key, tuple(MeasuredSignal(row.id, row.name, row.assignment, row.recipe.intervals, value)
                                       for row, value in zip(signals, rows)), self.provenance)
        with e.lock:
            check()
            self.cache.repository.assert_current(job.owner, s.dataset)
            # Preserve captured results even if ROI/recipes changed while the job ran.
            updated = replace(e.snapshot, revision=e.snapshot.revision+1, isotope_measurement=result)
            e.snapshot = replace(updated, isotope_measurement=current_result(updated))
        return None
