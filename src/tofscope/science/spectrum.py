"""Full-resolution spectra reconstructed from selected raw event cells."""

import h5py
import numpy as np

from tofscope.storage.bounded_events import admitted_events
from tofscope.storage.dataset_io import locked_read
from tofscope.storage.explorer import integration_parameters


@locked_read
def subvolume_spectrum(path, roi, frames, *, reserve, progress=None, cancel=None):
    """Sum selected events into native mass bins and normalize per waveform/channel."""
    with h5py.File(path, "r") as f:
        if "FullSpectra/EventList" not in f:
            raise ValueError("This file does not retain raw events.")
        raw = f["FullSpectra/EventList"]
        peak_shape = f["PeakData/PeakData"].shape
        if (
            len(raw.shape) != 3
            or len(peak_shape) != 4
            or raw.shape[1:] != peak_shape[1:3]
        ):
            raise ValueError("Raw event spatial shape does not match the ion map.")
        first, last = frames
        if (
            type(first) is not int
            or type(last) is not int
            or not 0 <= first <= last < raw.shape[0]
        ):
            raise ValueError("Invalid raw event frame range.")
        axis = f["FullSpectra/MassAxis"]
        ratio, normalization = integration_parameters(f)
        with reserve(axis.size * 32 + 4096):
            counts = np.zeros(axis.size, dtype=np.int64)
            for z in range(first, last + 1):
                if cancel and cancel():
                    raise InterruptedError("Spectrum calculation cancelled.")
                with admitted_events(raw, z, reserve, roi=roi) as events:
                    for offset, length in zip(events.offsets, events.lengths):
                        samples = events.samples[offset : offset + length]
                        valid = samples[(samples >= 0) & (samples < axis.size * ratio)]
                        bins = valid.astype(np.int64) // ratio
                        np.add.at(counts, bins, 1)
                if progress:
                    progress(z - first + 1, last - first + 1)
            return counts.astype(np.float64) / normalization
