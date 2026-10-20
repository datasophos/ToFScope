"""Authorized storage boundary. No open handles or renderer objects escape."""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
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
    location: str = "acquisition"
    name: str = ""


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
    def __init__(self, settings, authorize=None, budget=None):
        self.settings = settings
        self.authorize = authorize or (lambda owner, path: bool(owner))
        self.salt = secrets.token_hex(32)
        self.budget = budget

    def path(self, owner, dataset):
        try:
            if dataset.location == 'saved':
                from tofscope.storage.saved_files import SavedFileStore
                try:
                    p = SavedFileStore(self.settings).path(owner, dataset.relative_path)
                except FileNotFoundError:
                    raise ValueError('Saved file unavailable.') from None
            elif dataset.location == 'acquisition':
                p = resolve_data_path(self.settings, dataset.relative_path, require_file=True)
                if p.is_relative_to(self.settings.output_root):
                    raise PermissionError('Open saved files through the owner-scoped saved file list.')
            else:
                raise ValueError('Unknown file location.')
        except ValueError:
            if dataset.generation:
                raise SourceChanged(
                    "Acquisition changed or unavailable; explicitly replace it."
                ) from None
            raise
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

    def open(self, owner, relative_path, location="acquisition"):
        provisional = DatasetRef("", "", relative_path, location)
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
                key = hashlib.sha256((self.salt + str(p)).encode()).hexdigest()
                d = DatasetRef(key, generation, relative_path, location, p.name)
                with self._inspect(owner, d, p):
                    pass
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

    @contextmanager
    def _inspect(self, owner, dataset, path, analysis_id=None):
        # Preflight all numerical metadata and conservative decoded record overhead.
        # No metadata arrays survive their consumer's context or enter a hidden cache.
        from contextlib import nullcontext

        with h5py.File(path, "r") as f:
            arrays = [
                f[name]
                for name in (
                    "FullSpectra/MassAxis",
                    "FullSpectra/SumSpectrum",
                    "PeakData/PeakTable",
                )
            ]
            if any(a.dtype.hasobject for a in arrays):
                raise ValueError("Variable-length acquisition metadata is unsupported.")
            estimate = sum(a.size * a.dtype.itemsize * 4 for a in arrays)
            estimate += f["PeakData/PeakData"].shape[-1] * 1024
            estimate += len(f.get("FIBImages", {})) * 512 + 4096
        reservation = (
            self.budget.reserve(owner, analysis_id or dataset.key, int(estimate))
            if self.budget
            else nullcontext()
        )
        with reservation:
            m = inspect_file(path)
            if (
                any(n <= 0 for n in m["shape"])
                or not len(m["masses"])
                or m["masses"].ndim != 1
                or m["spectrum"].ndim != 1
                or len(m["masses"]) != len(m["spectrum"])
                or not np.isfinite(m["masses"]).all()
            ):
                raise ValueError("Invalid acquisition shape or mass calibration.")
            if any(
                not np.isfinite([p["mass"], p["low"], p["high"]]).all()
                or p["low"] >= p["high"]
                for p in m["peaks"]
            ):
                raise ValueError("Invalid stored integration metadata.")
            with h5py.File(path, "r") as f:
                for name in m["image_names"]:
                    group = f[f"FIBImages/{name}"]
                    if (
                        "Data" not in group
                        or group["Data"].ndim != 2
                        or any(n <= 0 for n in group["Data"].shape)
                    ):
                        raise ValueError("Invalid SE image layout.")
            self.assert_current(owner, dataset)
            for a in (m["masses"], m["spectrum"]):
                a.setflags(write=False)
            yield AcquisitionMetadata(
                tuple(m["shape"]),
                tuple(m["peaks"]),
                m["masses"],
                m["spectrum"],
                m["fov_um"],
                m["raw_shape"],
                tuple(m["image_names"]),
            )

    @contextmanager
    def metadata(self, owner, dataset, analysis_id=None):
        with self.access(owner, dataset) as path:
            with self._inspect(owner, dataset, path, analysis_id) as metadata:
                yield metadata

    def se_shape(self, owner, dataset, first, last):
        with (
            self.metadata(owner, dataset) as m,
            self.access(owner, dataset) as p,
            h5py.File(p, "r") as f,
        ):
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

    def read(self, owner, dataset, recipe, progress=None, cancel=None, reserve=None, materialization_id=None):
        with self.access(owner, dataset) as p:
            if materialization_id is not None:
                from contextlib import nullcontext
                from tofscope.storage.integration_store import saved_result_info, metadata_size, ROOT
                with h5py.File(p, 'r') as handle:
                    size = metadata_size(handle[f'{ROOT}/{materialization_id}'])
                with reserve(size * 16) if reserve else nullcontext():
                    info = saved_result_info(p, materialization_id)
                    derivation = info['derivation']
                    if (recipe.source != 'custom' or tuple(derivation['frames']) != recipe.frames or
                            tuple(tuple(x) for x in derivation['intervals']) != recipe.intervals):
                        raise ValueError('Saved data does not match the signal derivation.')
                    if cancel and cancel():
                        raise InterruptedError()
                    with h5py.File(p, 'r') as h:
                        data = h[f'{ROOT}/{materialization_id}/data']
                        result = np.empty(data.shape, dtype='float32')
                        data.read_direct(result)
                    with reserve(result.size) if reserve else nullcontext():
                        if not np.isfinite(result).all():
                            raise ValueError('Saved result contains invalid numerical values.')
                    if cancel and cancel():
                        raise InterruptedError()
                    return result
            if recipe.source == "custom":
                return custom_peak_windows(
                    p, recipe.intervals, *recipe.frames, progress, cancel, reserve
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
