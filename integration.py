"""Inclusive mass-window unions; display transforms never enter this module."""
import numpy as np


def canonical_intervals(intervals, axis_limits):
    """Sort and merge touching/overlapping intervals, rejecting invalid limits."""
    try:
        limits=np.asarray(axis_limits,dtype=float)
        pairs=np.asarray(tuple(intervals),dtype=float)
    except (ValueError,TypeError) as exc:
        raise ValueError('Mass windows must contain finite lower/upper pairs.') from exc
    if limits.shape!=(2,) or np.isnan(limits).any() or limits[0]>=limits[1]:
        raise ValueError('Invalid calibrated mass-axis limits.')
    if pairs.ndim!=2 or pairs.shape[1]!=2 or not len(pairs):
        raise ValueError('Add at least one mass interval with lower and upper limits.')
    if (not np.isfinite(pairs).all() or np.any(pairs[:,0]>=pairs[:,1])
            or np.any(pairs[:,0]<limits[0]) or np.any(pairs[:,1]>limits[1])):
        raise ValueError('Mass windows must be finite, lower < upper, and within the calibrated mass axis.')
    merged=[]
    for low,high in sorted(map(tuple,pairs)):
        if merged and low<=merged[-1][1]:
            merged[-1]=(merged[-1][0],max(high,merged[-1][1]))
        else:
            merged.append((float(low),float(high)))
    return tuple(merged)


def integrate_event_windows(events, mass_axis, clock_ratio, normalization, intervals):
    """Count each raw event once when its calibrated mass belongs to the union."""
    axis=np.asarray(mass_axis)
    if axis.ndim!=1 or not axis.size or not np.isfinite(axis).all():
        raise ValueError('Mass axis must be a nonempty finite one-dimensional array.')
    windows=canonical_intervals(intervals,(float(axis.min()),float(axis.max())))
    if (not np.isfinite([clock_ratio,normalization]).all() or clock_ratio<1
            or int(clock_ratio)!=clock_ratio or normalization<=0):
        raise ValueError('Invalid timing ratio or normalization.')
    included=np.zeros(len(axis),dtype=bool)
    for low,high in windows:
        included|=(axis>=low)&(axis<=high)
    cells=events.ravel()
    lengths=np.fromiter((len(cell) for cell in cells),dtype=np.int64,count=cells.size)
    if not lengths.sum():
        return np.zeros(events.shape,dtype=np.float32)
    samples=np.concatenate(list(cells)).astype(np.int64)//int(clock_ratio)
    valid=(samples>=0)&(samples<len(axis))
    selected=np.zeros(len(samples),dtype=np.int32)
    selected[valid]=included[samples[valid]]
    boundaries=np.concatenate(([0],np.cumsum(lengths)))
    counts=np.concatenate(([0],np.cumsum(selected,dtype=np.int64)))
    return (np.diff(counts[boundaries]).reshape(events.shape)/normalization).astype(np.float32)
