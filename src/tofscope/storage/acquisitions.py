"""Authorized storage boundary. No open handles or renderer objects escape."""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
from threading import RLock
import secrets
import h5py
import numpy as np
from filelock import Timeout
from tofscope.config import resolve_data_path
from tofscope.storage.dataset_io import LOCK_DIR, dataset_lock
from tofscope.storage.explorer import inspect_file
from tofscope.science.integration import custom_peak_windows


class SourceChanged(ValueError):
    pass


class DatasetBusy(ValueError):
    pass


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
    def __init__(self, settings, authorize=None):
        self.settings = settings
        self.authorize = authorize or (lambda owner, path: bool(owner))
        self.salt = secrets.token_hex(32)
        self._metadata = {}
        self._mutex = RLock()

    def path(self, owner, dataset):
        p = resolve_data_path(self.settings, dataset.relative_path, require_file=True)
        if not self.authorize(owner, p):
            raise PermissionError("Acquisition access denied.")
        return p

    def identity(self, p):
        s = p.stat()
        return hashlib.sha256(
            f"{self.salt}|{p}|{s.st_dev}|{s.st_ino}|{s.st_size}|{s.st_mtime_ns}|{s.st_ctime_ns}".encode()
        ).hexdigest()

    @contextmanager
    def access(self, owner, dataset):
        p = self.path(owner, dataset)
        token = LOCK_DIR.set(self.settings.lock_dir)
        try:
            with dataset_lock(p):
                self.assert_current(owner, dataset)
                yield p
                self.assert_current(owner, dataset)
        except Timeout:
            raise DatasetBusy("Acquisition busy; retry in a moment.") from None
        finally:
            LOCK_DIR.reset(token)

    def open(self, owner, relative_path):
        provisional = DatasetRef("", "", relative_path)
        p = self.path(owner, provisional)
        token = LOCK_DIR.set(self.settings.lock_dir)
        try:
            with dataset_lock(p):
                generation = self.identity(p)
                with h5py.File(p, "r") as handle:
                    self.validate_layout(handle)
                with h5py.File(p, "r") as handle:
                    if handle["PeakData/PeakData"].dtype.kind not in "iuf":
                        raise ValueError("Unsupported stored intensity dtype.")
                m = inspect_file(p)
                if any(
                    not np.isfinite([peak["mass"], peak["low"], peak["high"]]).all()
                    or peak["low"] >= peak["high"]
                    for peak in m["peaks"]
                ):
                    raise ValueError("Invalid stored integration metadata.")
                with h5py.File(p, "r") as handle:
                    for name in m["image_names"]:
                        group = handle[f"FIBImages/{name}"]
                        if (
                            "Data" not in group
                            or group["Data"].ndim != 2
                            or any(n <= 0 for n in group["Data"].shape)
                        ):
                            raise ValueError("Invalid SE image layout.")
                if (
                    any(n <= 0 for n in m["shape"])
                    or not len(m["masses"])
                    or len(m["masses"]) != len(m["spectrum"])
                ):
                    raise ValueError("Invalid acquisition shape.")
                if (
                    m["masses"].ndim != 1
                    or m["spectrum"].ndim != 1
                    or not np.isfinite(m["masses"]).all()
                ):
                    raise ValueError("Invalid mass calibration.")
                if generation != self.identity(p):
                    raise SourceChanged("Acquisition changed; reopen it.")
                key = hashlib.sha256((self.salt + str(p)).encode()).hexdigest()
                d = DatasetRef(key, generation, relative_path)
                for a in (m["masses"], m["spectrum"]):
                    a.setflags(write=False)
                meta = AcquisitionMetadata(
                    tuple(m["shape"]),
                    tuple(m["peaks"]),
                    m["masses"],
                    m["spectrum"],
                    m["fov_um"],
                    m["raw_shape"],
                    tuple(m["image_names"]),
                )
                with self._mutex:
                    self._metadata[(key, generation)] = meta
                return d
        except Timeout:
            raise DatasetBusy("Acquisition busy; retry in a moment.") from None
        except (OSError, KeyError, IndexError, TypeError):
            raise ValueError(
                "Acquisition is unreadable or has an unsupported layout."
            ) from None
        finally:
            LOCK_DIR.reset(token)

    @staticmethod
    def validate_layout(handle):
        seen = set()

        def visit(group):
            address = h5py.h5o.get_info(group.id).addr
            if address in seen:
                return
            seen.add(address)
            for name in group:
                link = group.get(name, getlink=True)
                if isinstance(link, h5py.ExternalLink):
                    raise ValueError("HDF5 external links are unsupported.")
                item = group[name]
                if isinstance(item, h5py.Group):
                    visit(item)
                elif item.is_virtual or item.external:
                    raise ValueError("HDF5 external or virtual storage is unsupported.")

        visit(handle)

    def assert_current(self, owner, dataset):
        p = self.path(owner, dataset)
        if self.identity(p) != dataset.generation:
            raise SourceChanged("Acquisition changed; explicitly reopen it.")

    def metadata(self, owner, dataset):
        self.assert_current(owner, dataset)
        with self._mutex:
            return self._metadata[(dataset.key, dataset.generation)]

    def se_shape(self, owner, dataset, first, last):
        m = self.metadata(owner, dataset)
        with self.access(owner, dataset) as p, h5py.File(p, "r") as f:
            shapes = [
                f[f"FIBImages/{name}/Data"].shape
                for name in m.image_names[max(0, first) : last + 1]
            ]
            if any(len(shape) != 2 for shape in shapes):
                raise ValueError("Invalid SE image dimensions.")
            return (
                tuple(max(shape[i] for shape in shapes) for i in range(2))
                if shapes
                else m.shape[1:3]
            )

    def read(self, owner, dataset, recipe, progress=None, cancel=None):
        with self.access(owner, dataset) as p:
            if recipe.source == "custom":
                return custom_peak_windows(
                    p, recipe.intervals, *recipe.frames, progress, cancel
                )
            if recipe.source != "stored":
                raise ValueError("Unsupported signal source in Explore pilot.")
            with h5py.File(p, "r") as f:
                data = f["PeakData/PeakData"]
                first, last = recipe.frames
                if (
                    not 0 <= first <= last < data.shape[0]
                    or not 0 <= recipe.stored_index < data.shape[-1]
                ):
                    raise ValueError("Signal bounds outside acquisition.")
                return np.asarray(
                    data[first : last + 1, :, :, recipe.stored_index], dtype=np.float32
                )
