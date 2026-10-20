"""Create verified PeakData in a new copy; never write to a raw acquisition."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import logging
import os
from pathlib import Path
from uuid import uuid4

import h5py
import numpy as np

from tofscope.science.raw_peaks import integrate_peak_table
from tofscope.storage.acquisitions import DatasetRef
from tofscope.storage.bounded_events import admitted_events
from tofscope.storage.explorer import integration_parameters, scalar
from tofscope.storage.saved_files import COPY_BYTES, SavedFile, file_id, filename, reserve_disk


@dataclass(frozen=True)
class PreparationPreview:
    requires_preparation: bool
    generation: str
    shape: tuple[int, int, int, int]
    suggested_filename: str
    required_bytes: int


@contextmanager
def raw_metadata(repository, owner, source, task_id):
    """Preflight decoded metadata and frame scratch before allocation."""
    with repository.access(owner, source) as path, h5py.File(path, 'r') as f:
        repository.validate_layout(f)
        required = ('PeakData/PeakTable', 'FullSpectra/MassAxis', 'FullSpectra/SumSpectrum', 'FullSpectra/EventList')
        if any(name not in f for name in required):
            raise ValueError('Raw preparation requires a peak table, calibrated mass axis, summed spectrum and event list.')
        table, axis, spectrum, raw = (f[name] for name in required)
        event_type = h5py.check_dtype(vlen=raw.dtype)
        if (table.ndim != 1 or not len(table) or table.dtype.hasobject or axis.ndim != 1
                or not len(axis) or axis.dtype.kind not in 'iuf' or spectrum.shape != axis.shape
                or spectrum.dtype.kind not in 'iuf' or raw.ndim != 3
                or event_type is None or np.dtype(event_type).kind not in 'iu'):
            raise ValueError('Unsupported raw acquisition layout.')
        if 'NbrWrites' not in f.attrs or 'NbrSegments' not in f.attrs:
            raise ValueError('Raw preparation requires completed-frame and raster metadata.')
        write_count = float(scalar(f.attrs['NbrWrites']))
        if not np.isfinite(write_count) or not write_count.is_integer():
            raise ValueError('Completed frame count must be a finite integer.')
        writes = int(write_count)
        if not 0 < writes <= raw.shape[0] or any(n <= 0 for n in raw.shape[1:]):
            raise ValueError('Completed frame count exceeds the raw event data.')
        if int(scalar(f.attrs['NbrSegments'])) != raw.shape[1]:
            raise ValueError('Raw raster metadata does not match the event list.')
        estimate = table.size * (table.dtype.itemsize * 4 + 1024) + axis.size * 32 + 4096
        with repository.budget.reserve(owner, task_id, int(estimate)):
            records, masses = table[:], axis[:]
            try:
                windows = np.column_stack((records['lower integration limit'], records['upper integration limit'])).astype('float64')
                finite = np.isfinite(records['mass']).all()
                valid_labels = records['label'].dtype.kind == 'S'
            except (ValueError, KeyError, TypeError):
                raise ValueError('Invalid raw peak table.') from None
            if (not finite or not valid_labels or not np.isfinite(windows).all()
                    or np.any(windows[:, 0] >= windows[:, 1]) or not np.isfinite(masses).all()):
                raise ValueError('Raw peak windows and mass calibration must be finite.')
            ratio, normalization = integration_parameters(f)
            yield f, records, masses, windows, (writes, *raw.shape[1:], len(records)), ratio, normalization


def inspect_source(repository, owner, relative_path, location='acquisition'):
    provisional = DatasetRef('', '', relative_path, location)
    path = repository.path(owner, provisional)
    source = DatasetRef(hashlib.sha256((repository.salt + str(path)).encode()).hexdigest(),
                        repository.identity(path), relative_path, location, path.name)
    with repository.access(owner, source), h5py.File(path, 'r') as handle:
        repository.validate_layout(handle)
        if 'PeakData/PeakData' in handle:
            shape = handle['PeakData/PeakData'].shape
            if len(shape) != 4:
                raise ValueError('Invalid integrated acquisition layout.')
            return source, PreparationPreview(False, source.generation, shape, '', 0)
    with raw_metadata(repository, owner, source, source.key) as (_, _, _, _, shape, _, _):
        # Admit a source copy and a worst-case frame, then check as compressed
        # output grows instead of reserving an entire uncompressed cube.
        needed = path.stat().st_size + int(np.prod(shape[1:])) * 8 + 64 * 1024**2
        return source, PreparationPreview(True, source.generation, shape, path.stem + '_prepared.h5', needed)


def prepare_copy(repository, files, owner, source, name, required_bytes, cancelled, progress, task_id):
    name = filename(name)
    directory = files.owner_root(owner)
    destination = directory / name
    if os.path.lexists(destination):
        raise FileExistsError('Output already exists; choose a new name.')
    temporary = directory / f'.tmp-{uuid4()}.h5'
    def check():
        if cancelled.is_set():
            raise InterruptedError('Preparation cancelled.')
        repository.assert_current(owner, source)
    try:
        with repository.access(owner, source) as path, reserve_disk(directory, required_bytes):
            check()
            with repository.budget.reserve(owner, task_id, COPY_BYTES):
                with path.open('rb') as src, temporary.open('xb') as out:
                    os.chmod(temporary, 0o600)
                    buffer = bytearray(COPY_BYTES)
                    copied, total = 0, path.stat().st_size
                    while True:
                        check()
                        count = src.readinto(buffer)
                        if not count:
                            break
                        out.write(memoryview(buffer)[:count])
                        copied += count
                        progress('Copying raw acquisition', copied, total)
                    out.flush()
                    os.fsync(out.fileno())
            with raw_metadata(repository, owner, source, task_id) as (f, table, axis, windows, shape, ratio, normalization):
                scratch = int(np.prod(shape[1:])) * 24 + 4096
                digest = hashlib.sha256()
                with repository.budget.reserve(owner, task_id, scratch), h5py.File(temporary, 'r+') as output:
                    data = output['PeakData'].create_dataset('PeakData', shape=shape, dtype='float32',
                        chunks=(1, min(32, shape[1]), min(32, shape[2]), min(32, shape[3])),
                        compression='lzf', shuffle=True)
                    for z in range(shape[0]):
                        check()
                        with reserve_disk(directory, int(np.prod(shape[1:])) * 8 + 64 * 1024**2):
                            with admitted_events(f['FullSpectra/EventList'], z, lambda n: repository.budget.reserve(owner, task_id, n)) as events:
                                with repository.budget.reserve(owner, task_id, events.samples.size * 48):
                                    values = integrate_peak_table(events, axis, ratio, normalization, windows)
                                    data[z] = values
                                    digest.update(values.tobytes())
                                    del values
                        progress('Integrating peak channels', z + 1, shape[0])
                    output.attrs['NbrPeaks'] = shape[-1]
                    group = output.require_group('ToFScope/Preparation')
                    group.attrs.update(schema_version=1, algorithm='inclusive-window-counts-v1',
                        source_name=source.name, source_generation=source.generation,
                        completed_frames=shape[0], clock_ratio=ratio, normalization=normalization,
                        sha256=digest.hexdigest())
                    output.flush()
                # Verify the written frame values, not merely the dataset dimensions.
                with repository.budget.reserve(owner, task_id, scratch), h5py.File(temporary, 'r') as output:
                    verified = hashlib.sha256()
                    for z in range(shape[0]):
                        check()
                        verified.update(output['PeakData/PeakData'][z].tobytes())
                        progress('Verifying integrated data', z + 1, shape[0])
                    if verified.hexdigest() != digest.hexdigest() or not np.array_equal(output['PeakData/PeakTable'][:], table):
                        raise ValueError('Prepared peak data verification failed.')
            with temporary.open('rb') as stream:
                os.fsync(stream.fileno())
            check()
            result = SavedFile(file_id(name), name, temporary.stat().st_size)
        # All source-generation contexts must exit before publication: a
        # post-publication recheck must not label a complete copy as failed.
        if cancelled.is_set():
            raise InterruptedError('Preparation cancelled.')
        os.link(temporary, destination)
        return result
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            logging.getLogger(__name__).warning('Could not remove a preparation temporary file.')
