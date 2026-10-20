"""Private, self-contained saved copies with bounded copying and exclusive publication."""
import base64
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import logging
import os
from pathlib import Path
import shutil
from threading import RLock
from uuid import uuid4

import h5py
import numpy as np

from tofscope import __version__
from tofscope.storage.acquisitions import AcquisitionRepository
from tofscope.storage.analysis_document import ROOT, MAX_DOCUMENT_BYTES, read_document
from tofscope.storage.integration_store import IntegrationRecord, write_integration_group, _read_info

COPY_BYTES = 8 * 1024**2
_disk_lock = RLock()
_disk_reservations = {}


@dataclass(frozen=True)
class SavedFile:
    id: str
    name: str
    size: int


def filename(value):
    if not isinstance(value, str) or not value or value.startswith('.') or any(x in value for x in ('/', '\\', '\x00')) or not value.endswith('.h5') or len(value.encode('utf-8')) > 240 or any(ord(c) < 32 for c in value):
        raise ValueError('Choose a plain .h5 filename without directory components.')
    return value


def file_id(name):
    return base64.urlsafe_b64encode(name.encode()).decode().rstrip('=')


@contextmanager
def reserve_disk(path, size):
    key = path.stat().st_dev
    with _disk_lock:
        held = _disk_reservations.get(key, 0)
        if shutil.disk_usage(path).free - held < size:
            raise OSError('Not enough free space for a complete saved copy.')
        _disk_reservations[key] = held + size
    try:
        yield
    finally:
        with _disk_lock:
            _disk_reservations[key] -= size


class SavedFileStore:
    def __init__(self, settings):
        self.settings = settings
        self.root = settings.output_root

    def owner_path(self, owner):
        if not isinstance(owner, str) or not owner:
            raise PermissionError('An authenticated owner is required.')
        # Local mode authenticates one operating-system user. Its visible save
        # folder is the physical destination; hosted identities remain isolated.
        if self.settings.mode == 'local' and owner == 'local':
            return self.root
        return self.root / hashlib.sha256(owner.encode()).hexdigest()

    def owner_root(self, owner):
        path = self.owner_path(owner)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink():
            raise ValueError('Saved-file directory cannot be a symbolic link.')
        path.mkdir(exist_ok=True, mode=0o700)
        return path

    def path(self, owner, identifier):
        try:
            name = base64.urlsafe_b64decode(identifier + '=' * (-len(identifier) % 4)).decode()
            if file_id(filename(name)) != identifier:
                raise ValueError('Invalid saved file ID.')
        except (ValueError, UnicodeError, TypeError) as exc:
            raise ValueError('Invalid saved file ID.') from exc
        target = self.owner_root(owner) / name
        if target.is_symlink() or not target.is_file():
            raise FileNotFoundError('Saved file unavailable.')
        return target

    def list(self, owner):
        return [SavedFile(file_id(p.name), p.name, p.stat().st_size)
                for p in sorted(self.owner_root(owner).iterdir())
                if not p.name.startswith('.') and p.suffix == '.h5' and p.is_file() and not p.is_symlink()]

    def publish_copy(self, owner, source, document, frames, name, cancel, progress, before_publish):
        name = filename(name)
        directory = self.owner_root(owner)
        destination = directory / name
        if os.path.lexists(destination):
            raise FileExistsError('Output already exists; choose a new name.')
        source = Path(source)
        initial = source.stat()
        source_identity = (initial.st_dev, initial.st_ino, initial.st_size, initial.st_mtime_ns, initial.st_ctime_ns)
        def check():
            if cancel.is_set():
                raise ValueError('Save cancelled.')
            now = source.stat()
            if (now.st_dev, now.st_ino, now.st_size, now.st_mtime_ns, now.st_ctime_ns) != source_identity:
                raise ValueError('Source changed while saving.')
        check()
        with h5py.File(source, 'r') as handle:
            AcquisitionRepository.validate_layout(handle)
        previous = read_document(source, self.settings)
        encoded = document.model_dump_json().encode()
        if len(encoded) > MAX_DOCUMENT_BYTES:
            raise ValueError('Analysis metadata exceeds save limits.')
        custom_bytes = sum((s.recipe.frames[1] - s.recipe.frames[0] + 1) * document.shape[1] * document.shape[2] * 4 for s in document.signals if s.materialization_id)
        needed = initial.st_size + custom_bytes + max(64 * 1024**2, custom_bytes // 10) + len(encoded) * 2
        temporary = directory / f'.tmp-{uuid4()}.h5'
        checksums = {}
        with reserve_disk(directory, needed):
            try:
                copied = 0
                with source.open('rb') as src, temporary.open('xb') as out:
                    os.chmod(temporary, 0o600)
                    buffer = bytearray(COPY_BYTES)
                    while True:
                        check()
                        count = src.readinto(buffer)
                        if not count:
                            break
                        out.write(memoryview(buffer)[:count])
                        copied += count
                        progress('Copying acquisition', copied, initial.st_size)
                    out.flush()
                    os.fsync(out.fileno())
                check()
                with h5py.File(temporary, 'r+') as handle:
                    if previous:
                        for row in previous.signals:
                            key = f'ToFScope/Integrations/{row.materialization_id}'
                            if row.materialization_id and key in handle:
                                del handle[key]
                    if ROOT in handle:
                        del handle[ROOT]
                    group = handle.require_group(ROOT)
                    group.attrs.update(schema_version=1, complete=False)
                    group.create_dataset('state_json', data=np.frombuffer(encoded, dtype='uint8'))
                    for row in document.signals:
                        if row.materialization_id is None:
                            continue
                        check()
                        digest = hashlib.sha256()
                        def checked_frames():
                            for i, values in enumerate(frames(row.id)):
                                check()
                                values = np.asarray(values)
                                digest.update(values.tobytes(order='C'))
                                progress('Saving ' + row.name, i + 1, row.recipe.frames[1] - row.recipe.frames[0] + 1)
                                yield values
                        record = IntegrationRecord(row.materialization_id, row.recipe.model_dump(mode='json'), document.shape[1:3], {}, {'kind': 'original_values'}, app_version=__version__)
                        write_integration_group(handle, record, checked_frames())
                        checksums[row.materialization_id] = digest.hexdigest()
                        handle[f'ToFScope/Integrations/{row.materialization_id}'].attrs['sha256'] = digest.hexdigest()
                    group.attrs['complete'] = True
                    handle.flush()
                self._verify(temporary, document, checksums, check)
                with temporary.open('rb') as stream:
                    os.fsync(stream.fileno())
                check()
                # The caller holds its revision lock across validation and publication.
                # A callback may return a context manager to make that interval explicit.
                from contextlib import nullcontext
                result = SavedFile(file_id(name), name, temporary.stat().st_size)
                guard = before_publish()
                with guard if guard is not None else nullcontext():
                    check()
                    os.link(temporary, destination)
                # Publication is committed; cleanup cannot turn a completed copy into failure.
                return result
            finally:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    logging.getLogger(__name__).warning('Could not remove a private save temporary file.')

    def _verify(self, path, document, checksums, check):
        if read_document(path, self.settings) != document:
            raise ValueError('Saved analysis verification failed.')
        with h5py.File(path, 'r') as handle:
            for row in document.signals:
                if not row.materialization_id:
                    continue
                group = handle[f'ToFScope/Integrations/{row.materialization_id}']
                _read_info(group)
                digest = hashlib.sha256()
                for values in group['data']:
                    check()
                    if not np.isfinite(values).all():
                        raise ValueError('Saved results contain invalid values.')
                    digest.update(values.tobytes(order='C'))
                if digest.hexdigest() != checksums[row.materialization_id]:
                    raise ValueError('Saved result checksum verification failed.')
