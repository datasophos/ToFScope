"""Cooperative POSIX locks and verified, backed-up acquisition replacement.

Locks coordinate ToFScope processes, not an independently running acquisition
program. Admins must verify locking and atomic replacement on their NFS mount.
"""
from dataclasses import dataclass,asdict
from functools import wraps
from pathlib import Path
from threading import Lock
from uuid import uuid4
import os
import shutil
import stat

import h5py
import numpy as np
from filelock import FileLock

from vendor_export import export_native_copy,validate_native_recipe,validate_native_layout

_LOCKS={}
_REGISTRY_LOCK=Lock()


def write_integration_group(*args,**kwargs):
    from integration_store import write_integration_group as write
    return write(*args,**kwargs)


def dataset_lock(path,timeout=0):
    canonical=Path(path).expanduser().resolve()
    with _REGISTRY_LOCK:
        if canonical not in _LOCKS:
            _LOCKS[canonical]=FileLock(canonical.with_name('.'+canonical.name+'.tofscope.lock'),timeout=timeout)
        return _LOCKS[canonical]


def locked_read(function):
    @wraps(function)
    def read(path,*args,**kwargs):
        with dataset_lock(path):return function(path,*args,**kwargs)
    return read


@dataclass(frozen=True)
class FileIdentity:
    path: str
    device: int
    inode: int
    size: int
    mtime_ns: int
    generation: str


@locked_read
def file_identity(path):
    path=Path(path).resolve();before=path.stat()
    with h5py.File(path,'r') as h5:generation=str(h5.attrs.get('ToFScopeGeneration',''))
    after=path.stat()
    if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
        raise ValueError('Acquisition changed during reading. Reload acquisition.')
    return FileIdentity(str(path),after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,generation)


@dataclass(frozen=True)
class SaveResult:
    target: Path
    backup: Path
    generation: str
    saved_id: str
    native_index: int
    reload_required: bool = True
    warning: str | None = None


def required_space(identity,record):
    first,last=record.derivation['frames']
    # Extension and native channel both retain the full-resolution data.
    return 2*identity.size+2*(last-first+1)*np.prod(record.spatial_shape).item()*4+64*1024**2


def verify_saved_copy(source,prepared,record,frame_data_factory):
    """Verify original peak values plus both representations of the addition."""
    from integration_store import ROOT
    with h5py.File(source,'r') as old,h5py.File(prepared,'r') as new:
        a=old['PeakData/PeakData'];b=new['PeakData/PeakData'];index=a.shape[-1]
        if b.shape!=(*a.shape[:-1],index+1):raise ValueError('Native shape verification failed.')
        if not np.array_equal(old['PeakData/PeakTable'][:],new['PeakData/PeakTable'][:index]):raise ValueError('Original peak table changed.')
        if int(new.attrs['NbrPeaks'])!=index+1:raise ValueError('Native count verification failed.')
        # Raw compressed bytes can be compared when channel chunks are separate.
        if a.chunks and a.chunks[-1]==1:
            for selection in a.iter_chunks():
                offset=tuple(s.start for s in selection)
                if a.id.get_chunk_info_by_coord(offset).size:
                    if a.id.read_direct_chunk(offset)!=b.id.read_direct_chunk(offset):raise ValueError('Original compressed peak data changed.')
        else:
            for z in range(a.shape[0]):
                if not np.array_equal(a[z],b[z,:,:,:index],equal_nan=True):raise ValueError('Original peak data changed.')
        saved=new[f'{ROOT}/{record.id}/data'];count=0
        for z,frame in enumerate(frame_data_factory()):
            if z>=saved.shape[0] or not np.array_equal(frame,saved[z]) or not np.array_equal(frame,b[z,:,:,index]):raise ValueError('Saved integration verification failed.')
            count+=1
        if count!=saved.shape[0]:raise ValueError('Saved frame count verification failed.')


def clear_dataset_caches():
    from explorer import _stored_peak,_se_mean
    from volume_layers import clear_preview_cache
    _stored_peak.cache_clear();_se_mean.cache_clear();clear_preview_cache()


def save_to_acquisition(settings,relative_path,record,frame_data_factory,expected_identity):
    from server_config import resolve_data_path
    from signals import SignalRecipe
    if not settings.allow_writes:raise ValueError('Acquisition writes are disabled by the server.')
    if not settings.allow_unverified_native:raise ValueError('Commercial compatibility is unverified. Experimental native writes are disabled by the server.')
    target=resolve_data_path(settings,relative_path,require_file=True)
    if asdict(expected_identity)!=record.source_identity:raise ValueError('Prepared integration identity does not match its source.')
    with dataset_lock(target):
        if file_identity(target)!=expected_identity:raise ValueError('Acquisition changed since preparation. Reload acquisition before saving.')
        info=target.stat()
        if info.st_nlink!=1:raise ValueError('Hard-linked acquisition files cannot be replaced safely.')
        if not info.st_mode & stat.S_IWUSR or not os.access(target,os.W_OK) or not os.access(target.parent,os.W_OK):raise PermissionError('Acquisition and its parent directory must be writable.')
        recipe=SignalRecipe.from_dict(record.derivation)
        with h5py.File(target,'r') as h5:
            validate_native_layout(h5);validate_native_recipe(h5,recipe)
            shape=h5['PeakData/PeakData'].shape;native_index=shape[-1]
            if tuple(shape[1:3])!=record.spatial_shape:raise ValueError('Integration must cover the complete spatial field.')
        if shutil.disk_usage(target.parent).free<required_space(expected_identity,record):raise ValueError('Insufficient free space for backup and verified replacement.')
        suffix=str(uuid4());backup=target.with_name(f'.{target.name}.{suffix}.bak')
        temporary=target.with_name(f'.{target.name}.{suffix}.tmp.h5')
        generation=str(uuid4())
        # Both files are retained on failure for recovery. The original path is
        # untouched until every verification and final identity check succeeds.
        try:
            shutil.copy2(target,backup)
            values=np.stack(tuple(frame_data_factory()))
            export_native_copy(target,temporary,[recipe],volumes=[values])
            with h5py.File(temporary,'r+') as h5:
                write_integration_group(h5,record,iter(values));h5.attrs['ToFScopeGeneration']=generation
            verify_saved_copy(target,temporary,record,frame_data_factory)
            os.chmod(temporary,stat.S_IMODE(info.st_mode))
            with temporary.open('rb') as stream:os.fsync(stream.fileno())
            if resolve_data_path(settings,relative_path,require_file=True)!=target or file_identity(target)!=expected_identity:
                raise ValueError('Acquisition changed before publication. Reload acquisition.')
            os.replace(temporary,target)
        except Exception as exc:
            exc.add_note(f'Recovery backup: {backup}; prepared copy: {temporary}')
            raise
        warning=None
        try:
            descriptor=os.open(target.parent,os.O_RDONLY)
            try:os.fsync(descriptor)
            finally:os.close(descriptor)
            clear_dataset_caches()
        except Exception as exc:
            warning=f'Saved successfully; reload required. Post-save housekeeping: {exc}'
        return SaveResult(target,backup,generation,record.id,native_index,warning=warning)
