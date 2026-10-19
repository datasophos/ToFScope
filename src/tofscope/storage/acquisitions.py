"""Authorized storage boundary. No open handles or renderer objects escape."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
from pathlib import Path
from threading import RLock
import secrets
import h5py
import numpy as np
from filelock import Timeout
from tofscope.config import resolve_data_path
from tofscope.storage.dataset_io import LOCK_DIR, dataset_lock
from tofscope.storage.explorer import inspect_file
from tofscope.science.integration import custom_peak_windows

class SourceChanged(ValueError):pass
class DatasetBusy(ValueError):pass

@dataclass(frozen=True)
class DatasetRef:
    key: str
    generation: str
    relative_path: str

@dataclass(frozen=True)
class AcquisitionMetadata:
    shape: tuple
    peaks: tuple
    mass_axis: np.ndarray
    sum_spectrum: np.ndarray
    fov_um: float | None
    raw_shape: tuple | None
    image_names: tuple

class AcquisitionRepository:
    def __init__(self,settings,authorize=None):
        self.settings=settings;self.authorize=authorize or (lambda owner,path:bool(owner));self.salt=secrets.token_hex(32);self._metadata={};self._mutex=RLock()
    def path(self,owner,dataset):
        p=resolve_data_path(self.settings,dataset.relative_path,require_file=True)
        if not self.authorize(owner,p):raise PermissionError('Acquisition access denied.')
        return p
    def identity(self,p):
        s=p.stat();return hashlib.sha256(f'{self.salt}|{p}|{s.st_dev}|{s.st_ino}|{s.st_size}|{s.st_mtime_ns}|{s.st_ctime_ns}'.encode()).hexdigest()
    @contextmanager
    def access(self,owner,dataset):
        p=self.path(owner,dataset);token=LOCK_DIR.set(self.settings.lock_dir)
        try:
            with dataset_lock(p):
                self.assert_current(owner,dataset)
                yield p
                self.assert_current(owner,dataset)
        except Timeout:raise DatasetBusy('Acquisition busy; retry in a moment.') from None
        finally:LOCK_DIR.reset(token)
    def open(self,owner,relative_path):
        provisional=DatasetRef('','',relative_path);p=self.path(owner,provisional);token=LOCK_DIR.set(self.settings.lock_dir)
        try:
            with dataset_lock(p):
                generation=self.identity(p)
                m=inspect_file(p)
                if any(n<=0 for n in m['shape']) or not len(m['masses']) or len(m['masses'])!=len(m['spectrum']):raise ValueError('Invalid acquisition shape.')
                if not np.isfinite(m['masses']).all():raise ValueError('Invalid mass calibration.')
                if generation!=self.identity(p):raise SourceChanged('Acquisition changed; reopen it.')
                key=hashlib.sha256((self.salt+str(p)).encode()).hexdigest()
                d=DatasetRef(key,generation,relative_path)
                for a in (m['masses'],m['spectrum']):a.setflags(write=False)
                meta=AcquisitionMetadata(tuple(m['shape']),tuple(m['peaks']),m['masses'],m['spectrum'],m['fov_um'],m['raw_shape'],tuple(m['image_names']))
                with self._mutex:self._metadata[(key,generation)]=meta
                return d
        except Timeout:raise DatasetBusy('Acquisition busy; retry in a moment.') from None
        except (OSError,KeyError,IndexError,TypeError):raise ValueError('Acquisition is unreadable or has an unsupported layout.') from None
        finally:LOCK_DIR.reset(token)
    def assert_current(self,owner,dataset):
        p=self.path(owner,dataset)
        if self.identity(p)!=dataset.generation:raise SourceChanged('Acquisition changed; explicitly reopen it.')
    def metadata(self,owner,dataset):
        self.assert_current(owner,dataset)
        with self._mutex:return self._metadata[(dataset.key,dataset.generation)]
    def read(self,owner,dataset,recipe,progress=None,cancel=None):
        with self.access(owner,dataset) as p:
            if recipe.source=='custom':return custom_peak_windows(p,recipe.intervals,*recipe.frames,progress,cancel)
            if recipe.source!='stored':raise ValueError('Unsupported signal source in Explore pilot.')
            with h5py.File(p,'r') as f:
                data=f['PeakData/PeakData'];first,last=recipe.frames
                if not 0<=first<=last<data.shape[0] or not 0<=recipe.stored_index<data.shape[-1]:raise ValueError('Signal bounds outside acquisition.')
                return np.asarray(data[first:last+1,:,:,recipe.stored_index],dtype=np.float32)
