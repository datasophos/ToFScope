"""Owner-scoped, revision-bound raw subvolume spectrum jobs."""

import json
from dataclasses import dataclass, replace

from tofscope.application.identification import requested_frames
from tofscope.science.spectrum import subvolume_spectrum


@dataclass(frozen=True)
class SpectrumResult:
    job_id: str
    dataset_generation: str
    roi: tuple[int, int, int, int]
    frames: tuple[int, int]
    values: list[float]


@dataclass(frozen=True)
class SpectrumTask:
    snapshot: object
    frames: tuple[int, int]


class SpectrumService:
    def __init__(self, analyses, explore, cache, jobs):
        self.analyses, self.explore, self.cache, self.jobs = (
            analyses,
            explore,
            cache,
            jobs,
        )
        jobs.spectrum_handler = self.run

    def submit(self, owner, aid, envelope):
        entry = self.analyses.entry(owner, aid)
        fingerprint = json.dumps(
            {"spectrum": envelope.model_dump(mode="json")}, sort_keys=True
        )
        with entry.lock:
            old = self.explore.validate_envelope(entry, envelope, fingerprint)
            if old is not None:
                return old
            snapshot = entry.snapshot
            with self.cache.repository.metadata(owner, snapshot.dataset, aid) as meta:
                if meta.raw_shape is None:
                    raise ValueError(
                        "This file does not retain raw events; the acquisition-wide spectrum remains available."
                    )
            task = SpectrumTask(snapshot, requested_frames(snapshot))
            with self.jobs.condition:
                job = self.jobs.enqueue_task(owner, task, "spectrum", aid)
                entry.spectrum_job_id = job.id
            self.explore.receipt(entry, envelope.request_id, fingerprint, job)
            return job

    def result(self, owner, aid):
        entry = self.analyses.entry(owner, aid)
        with entry.lock:
            self.cache.repository.assert_current(owner, entry.snapshot.dataset)
            if entry.spectrum is None:
                return None
            job_id, source, roi, frames, values = entry.spectrum
            if source != entry.snapshot.dataset:
                return None
            return SpectrumResult(
                job_id, source.generation, roi, frames, values.tolist()
            )

    def run(self, job):
        task = job.task
        snapshot = task.snapshot
        entry = self.analyses.entry(job.owner, snapshot.id)

        def cancelled():
            return (
                job.cancelled.is_set()
                or entry.closed
                or entry.snapshot.dataset != snapshot.dataset
                or entry.spectrum_job_id != job.snapshot.id
            )

        def progress(done, total):
            with self.jobs.condition:
                job.snapshot = replace(
                    job.snapshot,
                    done=done,
                    total=total,
                    stage="Reading selected frames",
                )

        budget = self.cache.budget
        with self.cache.repository.metadata(
            job.owner, snapshot.dataset, snapshot.id
        ) as meta:
            lease = budget.reserve(job.owner, snapshot.id, int(meta.mass_axis.size * 8))
        try:
            with self.cache.repository.access(job.owner, snapshot.dataset) as path:
                values = subvolume_spectrum(
                    path,
                    snapshot.roi,
                    task.frames,
                    reserve=lambda n: budget.reserve(job.owner, snapshot.id, n),
                    progress=progress,
                    cancel=cancelled,
                )
            with entry.lock:
                if cancelled():
                    raise InterruptedError()
                self.cache.repository.assert_current(job.owner, snapshot.dataset)
                old = entry.leases.pop("_spectrum", None)
                if old:
                    old.release()
                entry.spectrum = (
                    job.snapshot.id,
                    snapshot.dataset,
                    snapshot.roi,
                    task.frames,
                    values,
                )
                entry.leases["_spectrum"] = lease
                lease = None
        finally:
            if lease:
                lease.release()
