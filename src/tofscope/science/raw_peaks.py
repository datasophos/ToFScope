"""Frame-sized floating-point peak reconstruction, independent of HDF5 and UI."""
import numpy as np
from tofscope.science.integration import EventBatch


def integrate_peak_table(events, mass_axis, clock_ratio, normalization, windows):
    """Count every event in each inclusive window, preserving overlaps and order.

    Disjoint windows are grouped so ordinary nominal tables take one or two
    vectorized passes through the events, rather than one pass per channel.
    """
    axis = np.asarray(mass_axis, dtype=np.float64)
    bounds = np.asarray(windows, dtype=np.float64)
    if (axis.ndim != 1 or not len(axis) or not np.isfinite(axis).all()
            or bounds.ndim != 2 or bounds.shape[1] != 2 or not len(bounds)
            or not np.isfinite(bounds).all() or np.any(bounds[:, 0] >= bounds[:, 1])
            or not np.isfinite([clock_ratio, normalization]).all()
            or clock_ratio < 1 or int(clock_ratio) != clock_ratio or normalization <= 0):
        raise ValueError('Invalid raw calibration or peak windows.')
    if isinstance(events, EventBatch):
        raw, lengths, offsets = events.samples, events.lengths, events.offsets
    else:
        cells = events.ravel()
        lengths = np.fromiter((len(cell) for cell in cells), dtype=np.int64, count=len(cells))
        offsets = np.concatenate(([0], np.cumsum(lengths[:-1])))
        raw = np.concatenate(list(cells)) if lengths.sum() else np.empty(0, dtype='uint32')
    result = np.zeros((len(lengths), len(bounds)), dtype=np.float32)
    if not lengths.sum():
        return result.reshape((*events.shape, len(bounds)))
    # Bounded HDF5 arenas may contain padding; select only each cell's events.
    positions = np.repeat(offsets - np.cumsum(lengths) + lengths, lengths) + np.arange(lengths.sum())
    samples = raw[positions].astype(np.int64) // int(clock_ratio)
    valid = (samples >= 0) & (samples < len(axis))
    masses = axis[samples[valid]]
    pixels = np.repeat(np.arange(len(lengths), dtype=np.int64), lengths)[valid]
    groups = []
    for index in np.argsort(bounds[:, 0], kind='stable'):
        for group in groups:
            if bounds[group[-1], 1] < bounds[index, 0]:
                group.append(index)
                break
        else:
            groups.append([index])
    for group in groups:
        subset = bounds[group]
        bins = np.searchsorted(subset[:, 0], masses, side='right') - 1
        selected = (bins >= 0) & (masses <= subset[np.maximum(0, bins), 1])
        counts = np.bincount(pixels[selected] * len(group) + bins[selected], minlength=len(lengths) * len(group))
        result[:, group] = (counts.reshape(len(lengths), len(group)) / normalization).astype(np.float32)
    return result.reshape((*events.shape, len(bounds)))
