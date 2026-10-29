"""Admitted renderer-neutral volume previews in exact acquisition coordinates."""

from contextlib import contextmanager, ExitStack
from dataclasses import dataclass, asdict
import json
import math
import numpy as np
from tofscope.application.analyses import CapacityError
from tofscope.application.signals import get_signal
from tofscope.presentation.coordinates import calibration
from tofscope.presentation.explore import finite
from tofscope.science.depth_calibration import calibrated_window
from tofscope.science.volume_layers import VolumeLayer, build_layer_previews


@dataclass(frozen=True)
class LayerData:
    signal_id: str
    label: str
    frames: tuple[int, int]
    values: list[float | None]
    coverage: list[float]
    valid_counts: list[int]


@dataclass(frozen=True)
class VolumeData:
    analysis_id: str
    revision: int
    dataset_generation: str
    x: list[float]
    y: list[float]
    z: list[float]
    frame_centers: list[float]
    block_edges: list[list[int]]
    shape: tuple[int, int, int]
    xy_unit: str
    z_unit: str
    extent: tuple[float, float, float]
    physical_aspect: bool
    omitted_frames: int
    total_voxels: int
    layers: list[LayerData]

    def to_dict(self):
        return asdict(self)


class VolumePresenter:
    def __init__(self, analyses, repository, cache, settings):
        self.analyses, self.repository, self.cache, self.settings = (
            analyses,
            repository,
            cache,
            settings,
        )

    def preparation_bytes(self, s, count, frames, quality):
        # Python lists, boxed values, validity/counts and JSON plus reduction scratch.
        limits = (96, 32, 32) if quality == "Fast" else (160, 48, 48)
        sizes = (
            frames[1] - frames[0] + 1,
            s.roi[3] - s.roi[2] + 1,
            s.roi[1] - s.roi[0] + 1,
        )
        steps = [max(1, math.ceil(n / limit)) for n, limit in zip(sizes, limits)]
        counts = lambda: [math.ceil(n / step) for n, step in zip(sizes, steps)]
        while math.prod(counts()) * count > 500_000:
            i = max(range(3), key=lambda i: counts()[i])
            steps[i] += 1
        voxels = math.prod(counts()) * count
        scratch = min(steps[0], sizes[0]) * sizes[1] * sizes[2] * 24
        return int(
            voxels * 256 + scratch + (sum(sizes) + len(s.depth_anchors)) * 256 + 8192
        )

    def snapshot(self, owner, analysis_id, *, preparation=None):
        self.analyses.get(owner, analysis_id)
        e = self.analyses.entry(owner, analysis_id)
        with e.lock:
            if e.closed:
                raise KeyError("Analysis unavailable.")
            s = e.snapshot
            self.repository.assert_current(owner, s.dataset)
            styles = [
                x
                for x in s.spatial.layers
                if x.visible
                and (s.spatial.solo is None or x.signal_id == s.spatial.solo)
            ]
            frames = (
                (0, s.shape[0] - 1)
                if s.depth.mode == "all"
                else (
                    (s.depth.index, s.depth.index)
                    if s.depth.mode == "frame"
                    else (s.depth.first, s.depth.last)
                )
            )
            active = calibration(s) if s.depth_coordinates == "depth" else None
            known = calibrated_window(frames, active)
            omitted = (
                frames[1] - frames[0] + 1 - (known[1] - known[0] + 1 if known else 0)
            )
            empty = VolumeData(
                s.id,
                s.revision,
                s.dataset.generation,
                [],
                [],
                [],
                [],
                [],
                (0, 0, 0),
                "µm" if s.fov_um else "pixel",
                "µm" if active else "frame",
                (0.0, 0.0, 0.0),
                bool(s.fov_um and active),
                omitted,
                0,
                [],
            )
            if not styles or known is None:
                return empty
            estimate = self.preparation_bytes(s, len(styles), known, s.spatial.quality)
            with ExitStack() as local_preparation:
                admission = (
                    preparation if preparation is not None else local_preparation
                )
                admission.enter_context(
                    self.cache.budget.reserve(owner, s.id, estimate)
                )

                # One admitted original signal at a time; no prototype global cache.
                @contextmanager
                def source(recipe):
                    signal = next(
                        row
                        for row in s.signals
                        if row.recipe is not None and row.recipe.id == recipe.id
                    )
                    with self.cache.load(
                        owner,
                        s.id,
                        s.dataset,
                        recipe,
                        materialization_id=signal.materialization_id,
                    ) as lease:
                        yield lease.array

                previews = []
                layers = [
                    VolumeLayer(x.signal_id, get_signal(s, x.signal_id).recipe)
                    for x in styles
                ]
                # Builder releases each source lease after its reduction (also on error).
                with self.repository.access(owner, s.dataset) as path:
                    previews = build_layer_previews(
                        path,
                        layers,
                        s.roi,
                        frames,
                        quality=s.spatial.quality,
                        calibration=active,
                        use_cache=False,
                        reader_context=source,
                    )
                grid = previews[0].grid
                edges = grid.edges
                frame_centers = ((edges[0][:-1] + edges[0][1:] - 1) / 2).tolist()
                z = grid.z / 1000 if active else grid.z
                extent_z = float(z[-1] - z[0]) if len(z) > 1 else 0.0
                extent = (*grid.xy_extent, extent_z)
                payload = VolumeData(
                    s.id,
                    s.revision,
                    s.dataset.generation,
                    grid.x.tolist(),
                    grid.y.tolist(),
                    z.tolist(),
                    frame_centers,
                    [x.tolist() for x in edges],
                    previews[0].values.shape,
                    empty.xy_unit,
                    empty.z_unit,
                    extent,
                    empty.physical_aspect,
                    omitted,
                    sum(p.values.size for p in previews),
                    [
                        LayerData(
                            p.layer_id,
                            get_signal(s, p.layer_id).name,
                            p.recipe.frames,
                            finite(p.values.ravel()),
                            p.coverage.ravel().tolist(),
                            p.valid_counts.ravel().tolist(),
                        )
                        for p in previews
                    ],
                )
                self.repository.assert_current(owner, s.dataset)
                if (
                    len(json.dumps(payload.to_dict(), allow_nan=False).encode())
                    > self.settings.response_bytes
                ):
                    raise CapacityError(
                        "Volume exceeds configured response limit; choose Fast or hide layers."
                    )
                return payload
