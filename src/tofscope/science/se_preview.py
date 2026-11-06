"""Bounded, acquisition-aligned secondary-electron preview reduction."""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from itertools import pairwise
from threading import BoundedSemaphore

import h5py
import numpy as np

# Avoid multiplying subprocess counts when several analyses request SE at once.
_PARALLEL_SLOT = BoundedSemaphore(1)


def reduce_se_frame(image, x_edges, y_edges, sims_shape):
    """Area-weight native SE pixels into SIMS-coordinate preview bins."""

    def overlaps(edges, native_size, sims_size):
        pixels = np.arange(native_size, dtype=np.float64)
        lo = edges[:-1, None] * native_size / sims_size
        hi = edges[1:, None] * native_size / sims_size
        return (
            np.maximum(0.0, np.minimum(hi, pixels + 1) - np.maximum(lo, pixels))
            * sims_size
            / native_size
        )

    y = overlaps(np.asarray(y_edges), image.shape[0], sims_shape[0])
    x = overlaps(np.asarray(x_edges), image.shape[1], sims_shape[1])
    valid = np.isfinite(image)
    return y @ np.where(valid, image, 0.0) @ x.T, y @ valid.astype(float) @ x.T


def _serial(path, names, edges, sims_shape):
    z_edges, y_edges, x_edges = edges
    shape = (len(z_edges) - 1, len(y_edges) - 1, len(x_edges) - 1)
    values = np.full(shape, np.nan, dtype=np.float32)
    counts = np.zeros(shape, dtype=np.float32)
    with h5py.File(path, "r") as f:
        for i, (lo, hi) in enumerate(pairwise(z_edges)):
            sums = np.zeros(shape[1:], dtype=np.float64)
            weights = np.zeros_like(sums)
            for frame in range(int(lo), min(int(hi), len(names))):
                image = f[f"FIBImages/{names[frame]}/Data"][:]
                frame_sums, frame_weights = reduce_se_frame(
                    image, x_edges, y_edges, sims_shape
                )
                sums += frame_sums
                weights += frame_weights
            np.divide(sums, weights, out=values[i], where=weights > 0)
            counts[i] = weights
    return values, counts


def _subprocess(request):
    result = subprocess.run(
        [sys.executable, "-m", "tofscope.science.se_preview"],
        input=json.dumps(request).encode(),
        capture_output=True,
        check=True,
    )
    with np.load(BytesIO(result.stdout), allow_pickle=False) as data:
        return data["values"], data["counts"]


def prepare_se_preview(path, names, edges, sims_shape, *, workers=1):
    """Reduce every selected frame; parallel workers own independent HDF5 handles."""
    z_edges, y_edges, x_edges = (np.asarray(edge) for edge in edges)
    count = min(workers, len(z_edges) - 1)
    if count <= 1 or not _PARALLEL_SLOT.acquire(blocking=False):
        return _serial(path, names, (z_edges, y_edges, x_edges), sims_shape)
    try:
        boundaries = np.linspace(0, len(z_edges) - 1, count + 1, dtype=int)
        requests = [
            {
                "path": str(path),
                "names": list(names),
                "edges": [
                    z_edges[first : last + 1].tolist(),
                    y_edges.tolist(),
                    x_edges.tolist(),
                ],
                "sims_shape": list(sims_shape),
            }
            for first, last in pairwise(boundaries)
        ]
        try:
            with ThreadPoolExecutor(max_workers=count) as executor:
                chunks = list(executor.map(_subprocess, requests))
        except (OSError, subprocess.SubprocessError):
            return _serial(path, names, (z_edges, y_edges, x_edges), sims_shape)
        return tuple(
            np.concatenate([part[i] for part in chunks], axis=0) for i in (0, 1)
        )
    finally:
        _PARALLEL_SLOT.release()


def _main():
    request = json.load(sys.stdin)
    values, counts = _serial(
        request["path"], request["names"], request["edges"], request["sims_shape"]
    )
    np.savez(sys.stdout.buffer, values=values, counts=counts)


if __name__ == "__main__":
    _main()
