from contextlib import ExitStack
from dataclasses import asdict
import hashlib
import json
import numpy as np
from tofscope.presentation.data import Axis, Curve, Panel, ExploreData
from tofscope.application.workspaces import CapacityError
from tofscope.storage.explorer import _se_mean, file_key

PANELS = {"ion", "front", "spectrum", "profile"}


def finite(values):
    a = np.asarray(values, dtype=float)
    if a.ndim == 0:
        return float(a) if np.isfinite(a) else None
    if a.ndim == 1:
        return [float(v) if np.isfinite(v) else None for v in a]
    return [finite(row) for row in a]


def finite_max(values):
    a = np.asarray(values)
    return float(np.max(a, where=np.isfinite(a), initial=0)) or 1.0


def axis(name, unit, values, step=1):
    v = np.asarray(values, dtype=float)
    if len(v) > 1:
        bounds = np.r_[
            v[0] - (v[1] - v[0]) / 2, (v[1:] + v[:-1]) / 2, v[-1] + (v[-1] - v[-2]) / 2
        ]
    elif len(v):
        bounds = [v[0] - step / 2, v[0] + step / 2]
    else:
        bounds = []
    return Axis(name, unit, v.tolist(), list(map(float, bounds)))


def selected_frames(s):
    if s.depth.mode == "frame":
        return (s.depth.index, s.depth.index)
    if s.depth.mode == "window":
        return (s.depth.first, s.depth.last)
    return s.loaded_frames


class ExplorePresenter:
    def __init__(self, workspaces, repository, cache, settings):
        self.workspaces = workspaces
        self.repository = repository
        self.cache = cache
        self.settings = settings

    def curves(self, s, stack):
        x0, x1, y0, y1 = s.roi
        start, stop = s.loaded_frames
        result = []
        for r in (s.active_recipe, *s.comparisons):
            lease = stack.enter_context(self.cache.load(s.owner, s.id, s.dataset, r))
            a = lease.array
            v = np.full(stop - start + 1, np.nan)
            low = max(start, r.frames[0])
            high = min(stop, r.frames[1])
            if low <= high:
                v[low - start : high - start + 1] = a[
                    low - r.frames[0] : high - r.frames[0] + 1, y0 : y1 + 1, x0 : x1 + 1
                ].mean(axis=(1, 2), dtype=np.float64)
            result.append(Curve(r.id, r.label, finite(v), np.isfinite(v).tolist()))
        return result

    def snapshot(self, owner, analysis_id, panels=None):
        panels = set(PANELS if panels is None else panels)
        if not panels <= PANELS:
            raise ValueError("Unknown display panel.")
        self.workspaces.get(owner, analysis_id)
        e = self.workspaces.entry(owner, analysis_id)
        with e.lock, ExitStack() as metadata_stack:
            if e.closed:
                raise KeyError("Analysis unavailable.")
            s = e.snapshot
            meta = metadata_stack.enter_context(
                self.repository.metadata(owner, s.dataset, s.id)
            )
            nz, ny, nx, _ = s.shape
            first, last = s.loaded_frames
            # Bound all Python numeric/JSON intermediates before constructing lists.
            se_shape = (
                self.repository.se_shape(owner, s.dataset, *selected_frames(s))
                if "ion" in panels and s.display.image == "se"
                else (ny, nx)
            )
            count = (
                (se_shape[0] * se_shape[1] if "ion" in panels else 0)
                + ((last - first + 1) * nx if "front" in panels else 0)
                + (
                    (last - first + 1) * (1 + len(s.comparisons))
                    if "profile" in panels
                    else 0
                )
                + (len(meta.mass_axis) if "spectrum" in panels else 0)
            )
            estimate = int(count * 128 + 4096)
            if estimate > self.settings.response_bytes * 4:
                raise CapacityError("Display is too large; narrow loaded frames.")
            with (
                self.cache.budget.reserve(owner, analysis_id, estimate),
                ExitStack() as stack,
            ):
                result = {}
                xaxis = axis(
                    "x",
                    "µm" if s.fov_um else "pixel",
                    (np.arange(nx) + 0.5) * s.fov_um / nx
                    if s.fov_um
                    else np.arange(nx),
                )
                yaxis = axis(
                    "y",
                    "µm" if s.fov_um else "pixel",
                    (np.arange(ny) + 0.5) * s.fov_um / ny
                    if s.fov_um
                    else np.arange(ny),
                )
                if panels & {"ion", "front"}:
                    a = stack.enter_context(
                        self.cache.load(owner, s.id, s.dataset, s.active_recipe)
                    ).array
                    r = s.active_recipe
                    lo, hi = selected_frames(s)
                    low = max(lo, r.frames[0])
                    high = min(hi, r.frames[1])
                    frames = axis("frame", "frame", np.arange(first, last + 1))
                    x0, x1, y0, y1 = s.roi
                    if "ion" in panels:
                        if s.display.image == "se":
                            with self.repository.access(owner, s.dataset) as path:
                                image, _ = _se_mean.__wrapped__(
                                    file_key(path), meta.image_names, lo, hi
                                )
                            if image is None:
                                image = np.full((ny, nx), np.nan)
                            iy, ix = image.shape
                            axes = [
                                axis("x", "native pixel", np.arange(ix)),
                                axis("y", "native pixel", np.arange(iy)),
                            ]
                            aggregation = "unregistered SE mean / actual pixel coverage"
                        else:
                            image = (
                                a[low - r.frames[0] : high - r.frames[0] + 1].sum(
                                    axis=0, dtype=np.float64
                                )
                                if low <= high
                                else np.full((ny, nx), np.nan)
                            )
                            axes = [xaxis, yaxis]
                            aggregation = (
                                "sum over selected frames"
                                if lo != hi
                                else "single stored-domain frame"
                            )
                        if s.display.image == "se":
                            valid = image[np.isfinite(image)]
                            bounds = (
                                tuple(map(float, np.percentile(valid, [2, 98])))
                                if valid.size
                                else (0.0, 1.0)
                            )
                            if bounds[0] == bounds[1]:
                                bounds = (bounds[0], bounds[0] + 1)
                        else:
                            maximum = (
                                max(finite_max(frame) for frame in a)
                                if s.depth.mode == "frame"
                                else finite_max(a.sum(axis=0, dtype=np.float64))
                            )
                            bounds = (0.0, maximum)
                        result["ion"] = self.panel(
                            "image",
                            axes,
                            values=image,
                            aggregation=aggregation,
                            intensity_range=bounds,
                            palette="gray" if s.display.image == "se" else "ion",
                            log=s.display.log,
                        )
                    if "front" in panels:
                        front = np.full((last - first + 1, nx), np.nan)
                        l = max(first, r.frames[0])
                        h = min(last, r.frames[1])
                        if l <= h:
                            front[l - first : h - first + 1] = a[
                                l - r.frames[0] : h - r.frames[0] + 1, y0 : y1 + 1, :
                            ].sum(axis=1, dtype=np.float64)
                        fx = xaxis
                        result["front"] = self.panel(
                            "image",
                            [fx, frames],
                            values=front,
                            aggregation="exact sum along ROI y",
                            intensity_range=(
                                0,
                                finite_max(front),
                            ),
                            log=s.display.log,
                        )
                if "profile" in panels:
                    result["profile"] = self.panel(
                        "line",
                        [axis("frame", "frame", np.arange(first, last + 1))],
                        series=self.curves(s, stack),
                        aggregation="original-resolution ROI mean / pixel",
                        relative=s.display.relative,
                    )
                if "spectrum" in panels:
                    result["spectrum"] = self.panel(
                        "line",
                        [axis("m/z", "Th", meta.mass_axis)],
                        series=[
                            Curve(
                                "sum-spectrum",
                                "Sum spectrum",
                                finite(meta.sum_spectrum),
                                np.isfinite(meta.sum_spectrum).tolist(),
                            )
                        ],
                        aggregation="vendor summed spectrum",
                    )
                self.repository.assert_current(owner, s.dataset)
                payload = ExploreData(s.id, s.revision, s.dataset.generation, result)
                if (
                    len(json.dumps(payload.to_dict(), allow_nan=False).encode())
                    > self.settings.response_bytes
                ):
                    raise CapacityError(
                        "Display exceeds response limit; narrow loaded frames."
                    )
                return payload

    def panel(self, kind, axes, values=None, series=None, **kwargs):
        data = finite(values) if values is not None else []
        coverage = np.isfinite(values).tolist() if values is not None else []
        p = Panel(kind, "", axes, data, coverage, series or [], **kwargs)
        digest = hashlib.sha256(
            json.dumps(asdict(p), sort_keys=True, allow_nan=False).encode()
        ).hexdigest()[:20]
        return Panel(kind, digest, axes, data, coverage, series or [], **kwargs)
