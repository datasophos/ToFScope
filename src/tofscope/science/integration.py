"""Inclusive mass-window unions; display transforms never enter this module."""
import numpy as np
from tofscope.storage.dataset_io import locked_read


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
    # Compare exact stored bin values with user bounds without rounding those
    # bounds down to the file's (often float32) dtype.
    axis=np.asarray(mass_axis,dtype=np.float64)
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


@locked_read
def custom_peak_windows(path, intervals, first, last, progress=None, cancel=None):
    """Reconstruct a union in one read per supported acquisition depth slice."""
    import h5py
    from operator import index
    from tofscope.storage.explorer import integration_parameters
    try:
        if isinstance(first,bool) or isinstance(last,bool):
            raise TypeError
        first,last=index(first),index(last)
    except TypeError as exc:
        raise ValueError('Integration frames must be integers.') from exc
    with h5py.File(path,'r') as f:
        if 'FullSpectra/EventList' not in f:
            raise ValueError('This file does not retain raw events.')
        nz,ny,nx,_=f['PeakData/PeakData'].shape
        raw=f['FullSpectra/EventList']
        axis=f['FullSpectra/MassAxis'][:]
        windows=canonical_intervals(intervals,(float(axis.min()),float(axis.max())))
        if not 0<=first<=last<nz or last>=raw.shape[0] or raw.shape[1:]!=(ny,nx):
            raise ValueError('Requested frame range or raw spatial shape is invalid.')
        ratio,normalization=integration_parameters(f)
        volume=np.empty((last-first+1,ny,nx),dtype=np.float32)
        for i,z in enumerate(range(first,last+1)):
            if cancel is not None and cancel():raise InterruptedError('Integration cancelled.')
            volume[i]=integrate_event_windows(raw[z,:,:],axis,ratio,normalization,windows)
            if progress is not None:
                progress(i+1,len(volume))
        return volume
