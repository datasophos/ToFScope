"""Explicit generation-bound raw preparations on the shared owner work queue."""
from dataclasses import dataclass, replace
from uuid import uuid4
import os

from tofscope.storage.raw_preparation import inspect_source, prepare_copy
from tofscope.storage.saved_files import filename


@dataclass(frozen=True)
class PreparationTask:
    id: str
    source: object
    name: str
    required_bytes: int


class PreparationService:
    def __init__(self, repository, jobs, files):
        self.repository, self.jobs, self.files = repository, jobs, files
        jobs.preparation_handler = self.run

    def inspect(self, owner, path, location='acquisition'):
        return inspect_source(self.repository, owner, path, location)[1]

    def submit(self, owner, path, location, generation, name, *, accept_assumptions=False):
        name = filename(name)
        source, preview = inspect_source(self.repository, owner, path, location)
        if preview.generation != generation:
            raise ValueError('Acquisition changed; inspect it again before preparation.')
        if not preview.requires_preparation:
            raise ValueError('This file already contains integrated peak data.')
        if preview.assumptions and not accept_assumptions:
            raise ValueError('Missing acquisition metadata requires explicit acceptance of the reconstruction assumptions.')
        if os.path.lexists(self.files.owner_root(owner) / name):
            raise FileExistsError('Output already exists; choose a new name.')
        task = PreparationTask(str(uuid4()), source, name, preview.required_bytes)
        return self.jobs.enqueue_task(owner, task, 'preparation', task.id)

    def run(self, job):
        def progress(stage, done, total):
            with self.jobs.condition:
                job.snapshot = replace(job.snapshot, stage=stage, done=done, total=total)
        task = job.task
        return prepare_copy(self.repository, self.files, job.owner, task.source, task.name,
                            task.required_bytes, job.cancelled, progress, task.id)
