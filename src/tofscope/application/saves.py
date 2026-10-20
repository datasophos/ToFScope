"""Revision-bound saved copies run through the shared fair job scheduler."""
from contextlib import contextmanager
from dataclasses import dataclass, replace
import json

from tofscope.application.workspaces import Conflict
from tofscope.storage.analysis_document import encode_document
from tofscope.storage.saved_files import SavedFileStore, COPY_BYTES, filename


@dataclass(frozen=True)
class SaveTask:
    snapshot: object
    document: object
    name: str


class SaveService:
    def __init__(self, workspaces, jobs, cache, repository, settings):
        self.workspaces, self.jobs, self.cache, self.repository = workspaces, jobs, cache, repository
        self.files = SavedFileStore(settings)
        jobs.save_handler = self.run

    def submit(self, owner, analysis_id, envelope, name):
        name = filename(name)
        e = self.workspaces.entry(owner, analysis_id)
        fingerprint = json.dumps({'kind': 'save', 'envelope': envelope.model_dump(mode='json'), 'filename': name}, sort_keys=True)
        with e.lock:
            old = self.jobs.explore.validate_envelope(e, envelope, fingerprint)
            if old is not None:
                return old
            with self.jobs.condition:
                if any(j.snapshot.analysis_id == analysis_id and j.snapshot.kind == 'integration' and j.snapshot.status not in {'succeeded', 'failed', 'cancelled', 'obsolete'} for j in self.jobs.jobs.values()):
                    raise ValueError('Finish or cancel calculations before saving.')
                task = SaveTask(e.snapshot, encode_document(e.snapshot), name)
                result = self.jobs.enqueue_save(owner, task)
                self.jobs.explore.receipt(e, envelope.request_id, fingerprint, result)
                return result

    def run(self, job):
        task = job.task
        snapshot = task.snapshot
        entry = self.workspaces.entry(job.owner, snapshot.id)
        def progress(stage, done, total):
            from dataclasses import replace
            with self.jobs.condition:
                job.snapshot = replace(job.snapshot, stage=stage, done=done, total=total)
        def frames(signal_id):
            row = next(x for x in snapshot.signals if x.id == signal_id)
            with self.cache.load(job.owner, snapshot.id, snapshot.dataset, row.recipe, materialization_id=row.materialization_id, cancel=job.cancelled.is_set) as lease:
                yield from lease.array
        @contextmanager
        def publish_guard():
            with entry.lock:
                if entry.closed or job.cancelled.is_set():
                    raise InterruptedError()
                if entry.snapshot.revision != snapshot.revision or entry.snapshot.dataset != snapshot.dataset:
                    raise Conflict('Analysis changed during save; save the current revision again.')
                self.repository.assert_current(job.owner, snapshot.dataset)
                yield
                entry.snapshot = replace(entry.snapshot, saved_revision=snapshot.revision)
        self.repository.assert_current(job.owner, snapshot.dataset)
        path = self.repository.path(job.owner, snapshot.dataset)
        scratch = COPY_BYTES + snapshot.shape[1] * snapshot.shape[2] * 12
        with self.cache.budget.reserve(job.owner, snapshot.id, scratch):
            return self.files.publish_copy(job.owner, path, task.document, frames, task.name,
                                           job.cancelled, progress, publish_guard)
