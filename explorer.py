"""Small, read-only Tofwerk data layer, independent of the notebook UI.

Direct HDF5 access keeps the prototype's reads bounded to a channel or a raw
depth slice. Raw reconstruction follows the TDC mapping and per-waveform /
active-channel normalization used by RosettaSciIO's Tofwerk reader.
"""
from functools import lru_cache
from pathlib import Path
import re

import h5py
import numpy as np
from dataset_io import locked_read


DEFAULT_FILE = (
    Path(__file__).resolve().parent.parent
    / "2025-12-05_example_datasets/pfib_1301x128x128_AlTiPt.h5"
)


def scalar(value):
    return np.asarray(value).reshape(-1)[0].item()


def decode(value):
    return value.decode(errors="replace") if isinstance(value, bytes) else str(value)


@locked_read
def inspect_file(path):
    path = Path(path).expanduser().resolve()
    with h5py.File(path, "r") as f:
        if "PeakData/PeakData" not in f:
            raise ValueError("This prototype requires a file containing PeakData/PeakData.")
        data = f["PeakData/PeakData"]
        if data.ndim != 4:
            raise ValueError("Expected a (depth, y, x, peak) data array.")
        table = f["PeakData/PeakTable"][:]
        if len(table) != data.shape[-1]:
            raise ValueError("Peak table length does not match the peak data channels.")
        peaks = [dict(index=i, label=decode(r['label']), mass=float(r['mass']),
                      low=float(r['lower integration limit']),
                      high=float(r['upper integration limit'])) for i, r in enumerate(table)]
        spectrum = f['FullSpectra/SumSpectrum'][:]
        masses = f['FullSpectra/MassAxis'][:]
        fib = f.get('FIBParams')
        fov = float(scalar(fib.attrs['ViewField'])) * 1000 if fib is not None and 'ViewField' in fib.attrs else None
        raw_shape = f['FullSpectra/EventList'].shape if 'FullSpectra/EventList' in f else None
        image_names = sorted(f['FIBImages'].keys()) if 'FIBImages' in f else []
        return dict(path=str(path), name=path.name, bytes=path.stat().st_size,
                    shape=data.shape, peaks=peaks, masses=masses, spectrum=spectrum,
                    fov_um=fov, raw_shape=raw_shape, image_names=image_names)


def file_key(path):
    p = Path(path)
    return (str(p.resolve()), p.stat().st_mtime_ns, p.stat().st_size)


@lru_cache(maxsize=3)
def _stored_peak(key, index):
    with h5py.File(key[0], 'r') as f:
        d = f['PeakData/PeakData']
        if not 0 <= index < d.shape[-1]:
            raise ValueError('Peak index is outside the available channels.')
        result = np.asarray(d[:, :, :, index], dtype=np.float32)
        result.setflags(write=False)
        return result


@locked_read
def stored_peak(path, index):
    return _stored_peak(file_key(path), int(index))


def integrate_events(events, mass_axis, clock_ratio, normalization, low, high):
    """Compatibility adapter for one inclusive mass interval."""
    from integration import integrate_event_windows
    return integrate_event_windows(events,mass_axis,clock_ratio,normalization,[(low,high)])


def integration_parameters(f):
    fs = f['FullSpectra'].attrs
    required = ('SampleInterval', 'ClockPeriod')
    if any(k not in fs for k in required) or 'NbrWaveforms' not in f.attrs:
        raise ValueError('Raw reintegration requires timing and NbrWaveforms metadata.')
    ratio = float(scalar(fs['SampleInterval'])) / float(scalar(fs['ClockPeriod']))
    if not np.isfinite(ratio) or ratio < 1 or not np.isclose(ratio, round(ratio), rtol=1e-5):
        raise ValueError('Unsupported noninteger TDC/sample clock ratio.')
    ini = decode(f.attrs.get('Configuration File Contents', b''))
    channels = re.findall(r'Ch\d+Record\s*=\s*(\d+)', ini)
    if not channels:
        raise ValueError('Cannot determine active recording channels for normalization.')
    normalization = int(scalar(f.attrs['NbrWaveforms'])) * sum(int(v) != 0 for v in channels)
    if normalization <= 0:
        raise ValueError('No active channels or waveforms recorded.')
    return round(ratio), normalization


def custom_peak(path, low, high, first, last, progress=None):
    """Compatibility adapter for a single raw integration interval."""
    from integration import custom_peak_windows
    return custom_peak_windows(path,[(low,high)],first,last,progress)


@locked_read
def se_image(path, names, frame):
    if not names or not 0 <= frame < len(names):
        return None
    with h5py.File(path, 'r') as f:
        return f[f'FIBImages/{names[frame]}/Data'][:]


def sum_depth_window(volume, frames, window):
    """Sum original ion intensities over an inclusive depth interval."""
    first,last=window
    if not frames[0]<=first<=last<=frames[1]:
        raise ValueError('Depth window lies outside the loaded frames.')
    return volume[first-frames[0]:last-frames[0]+1].sum(axis=0,dtype=np.float64)


@locked_read
def se_mean(path, names, first, last):
    return _se_mean(file_key(path),tuple(names),int(first),int(last))


@lru_cache(maxsize=2)
def _se_mean(key, names, first, last):
    """Stream an unregistered SE mean, averaging only valid pixel coverage."""
    total=np.zeros((0,0),dtype=np.float64)
    counts=np.zeros((0,0),dtype=np.uint32)
    used=0
    with h5py.File(key[0],'r') as f:
        for z in range(max(0,first),min(last+1,len(names))):
            data=f[f'FIBImages/{names[z]}/Data'][:]
            ny,nx=data.shape
            if ny>total.shape[0] or nx>total.shape[1]:
                padding=((0,max(0,ny-total.shape[0])),(0,max(0,nx-total.shape[1])))
                total=np.pad(total,padding)
                counts=np.pad(counts,padding)
            valid=np.isfinite(data)
            total[:ny,:nx]+=np.where(valid,data,0)
            counts[:ny,:nx]+=valid
            used+=1
    if not used:
        return None,0
    result=np.divide(total,counts,out=np.zeros_like(total),where=counts>0)
    result.setflags(write=False)
    return result,used


def roi_from_bounds(bounds, shape, fov=None):
    """Convert dragged plot bounds to inclusive pixel-center selections."""
    if len(bounds) != 4 or not np.isfinite(bounds).all():
        raise ValueError('Region coordinates must be finite.')
    result = []
    for a, b, n in [(bounds[0], bounds[1], shape[2]), (bounds[2], bounds[3], shape[1])]:
        a, b = sorted((a, b))
        spacing, offset = (fov / n, .5) if fov else (1., 0.)
        first = int(np.clip(np.ceil(a / spacing - offset - 1e-9), 0, n-1))
        last = int(np.clip(np.floor(b / spacing - offset + 1e-9), 0, n-1))
        if first > last:
            first = last = int(np.clip(round((a+b)/2/spacing-offset), 0, n-1))
        result.extend([first, last])
    return tuple(result)


def preview_grid(volume, frames, roi, max_depth=96, max_xy=32,*,z_coordinates=None):
    """Block means for a compact display volume; profiles use original data.

    Unlike simple striding, pooling preserves contributions from thin features.
    Partial edge blocks are averaged only over their actual extent.
    """
    x0, x1, y0, y1 = roi
    a = volume[:, y0:y1 + 1, x0:x1 + 1]
    axes = [np.arange(frames[0], frames[0] + len(a), dtype=float),
            np.arange(y0, y1 + 1, dtype=float), np.arange(x0, x1 + 1, dtype=float)]
    if z_coordinates is not None:
        axes[0]=np.asarray(z_coordinates,dtype=float)
        if axes[0].shape!=(len(a),) or not np.isfinite(axes[0]).all():raise ValueError('Preview depth coordinates must cover every input frame.')
    for dim, limit in enumerate((max_depth, max_xy, max_xy)):
        stride = max(1, int(np.ceil(a.shape[dim] / limit)))
        starts = np.arange(0, a.shape[dim], stride)
        sizes = np.diff(np.append(starts, a.shape[dim]))
        shape = [1, 1, 1]
        shape[dim] = len(sizes)
        a = np.add.reduceat(a, starts, axis=dim) / sizes.reshape(shape)
        axes[dim] = np.add.reduceat(axes[dim], starts) / sizes
    return np.asarray(a, dtype=np.float32), axes
