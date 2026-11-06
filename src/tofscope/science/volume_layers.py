from contextlib import nullcontext
"""Shared, acquisition-aligned previews with a total visible-voxel budget."""
from collections import OrderedDict
from dataclasses import dataclass,replace
import math
import h5py
import numpy as np
from tofscope.storage.explorer import inspect_file,file_key
from tofscope.science.signals import SignalRecipe,read_signal
from tofscope.science.depth_calibration import calibrated_window

COLORSCALES=('Viridis','Magma','Plasma','Cividis','Reds','Blues','Greens','Purples')


@dataclass
class VolumeLayer:
    id: str
    recipe: SignalRecipe | None
    visible: bool = True
    colorscale: str = 'Viridis'
    opacity: float = .12
    percentile: float = 70.

    def __post_init__(self):
        if not isinstance(self.id,str) or not self.id:raise ValueError('Layer ID is required.')
        if type(self.visible) is not bool or self.colorscale not in COLORSCALES:raise ValueError('Invalid layer visibility or colormap.')
        if not math.isfinite(self.opacity) or not 0<=self.opacity<=1:raise ValueError('Opacity must lie between 0 and 1.')
        if not math.isfinite(self.percentile) or not 0<=self.percentile<=100:raise ValueError('Percentile must lie between 0 and 100.')


@dataclass(frozen=True)
class PreviewGrid:
    z: np.ndarray
    y: np.ndarray
    x: np.ndarray
    edges: tuple[np.ndarray,np.ndarray,np.ndarray]
    physical_xy: bool
    xy_extent: tuple[float,float] | None = None


@dataclass(frozen=True)
class VolumePreview:
    layer_id: str
    recipe: SignalRecipe | None
    grid: PreviewGrid
    values: np.ndarray
    coverage: np.ndarray
    valid_counts: np.ndarray


_CACHE=OrderedDict()
_CACHE_BYTES=0

def reduce_se_frame(image, x_edges, y_edges, sims_shape):
    """Area-weight native SE pixels into SIMS-coordinate preview bins."""
    def overlaps(edges, native_size, sims_size):
        pixels = np.arange(native_size, dtype=np.float64)
        lo = edges[:-1, None] * native_size / sims_size
        hi = edges[1:, None] * native_size / sims_size
        return np.maximum(0., np.minimum(hi, pixels + 1) - np.maximum(lo, pixels)) * sims_size / native_size

    y = overlaps(np.asarray(y_edges), image.shape[0], sims_shape[0])
    x = overlaps(np.asarray(x_edges), image.shape[1], sims_shape[1])
    valid = np.isfinite(image)
    return y @ np.where(valid, image, 0.) @ x.T, y @ valid.astype(float) @ x.T

def clear_preview_cache():
    global _CACHE_BYTES
    _CACHE.clear();_CACHE_BYTES=0


def build_layer_previews(path,layers,roi,frames,*,quality,voxel_budget=500_000,reader=None,calibration=None,use_cache=True,reader_context=None):
    global _CACHE_BYTES
    enabled=[layer for layer in layers if layer.visible]
    if not enabled:return []
    if type(voxel_budget) is not int or voxel_budget<len(enabled):raise ValueError('Preview budget must allow at least one voxel per visible layer.')
    if quality not in ('Fast','Detailed'):raise ValueError('Unknown preview quality.')
    meta=inspect_file(path);shape=meta['shape']
    if len(frames)!=2 or any(type(z) is not int for z in frames) or not 0<=frames[0]<=frames[1]<shape[0]:raise ValueError('Invalid preview depth window.')
    frames=calibrated_window(frames,calibration)
    if frames is None:return []
    if len(roi)!=4 or any(type(z) is not int for z in roi) or not (0<=roi[0]<=roi[1]<shape[2] and 0<=roi[2]<=roi[3]<shape[1]):raise ValueError('Invalid preview ROI.')
    x0,x1,y0,y1=roi
    sizes=(frames[1]-frames[0]+1,y1-y0+1,x1-x0+1);limits=(96,32,32) if quality=='Fast' else (160,48,48)
    steps=[max(1,math.ceil(n/limit)) for n,limit in zip(sizes,limits)]
    counts=lambda:[math.ceil(n/step) for n,step in zip(sizes,steps)]
    while math.prod(counts())*len(enabled)>voxel_budget:
        axis=max(range(3),key=lambda i:counts()[i]);steps[axis]+=1
    starts=(frames[0],y0,x0)
    edges=tuple(np.r_[np.arange(start,start+size,step),start+size] for start,size,step in zip(starts,sizes,steps))
    z,y,x=((e[:-1]+e[1:]-1)/2 for e in edges)
    fov=meta['fov_um']
    if fov:y=(y+.5)*fov/shape[1];x=(x+.5)*fov/shape[2]
    extent=((x1-x0+1)*fov/shape[2],(y1-y0+1)*fov/shape[1]) if fov else (x1-x0+1,y1-y0+1)
    if calibration:
        z=np.array([np.mean(calibration.frame_to_depth(np.arange(lo,hi))) for lo,hi in zip(edges[0][:-1],edges[0][1:])])
    grid=PreviewGrid(z,y,x,edges,bool(fov),extent);result=[];identity=file_key(path)
    block_sizes=np.diff(edges[0])[:,None,None]*np.diff(edges[1])[None,:,None]*np.diff(edges[2])[None,None,:]
    for layer in enabled:
        r=layer.recipe
        if r is None:
            values=np.full(tuple(counts()),np.nan,dtype=np.float32)
            valid_counts=np.zeros(values.shape,dtype=np.float32)
            names=meta['image_names']
            with h5py.File(path,'r') as f:
                for i,(lo,hi) in enumerate(zip(edges[0],edges[0][1:])):
                    sums=np.zeros(values.shape[1:],dtype=np.float64)
                    weights=np.zeros_like(sums)
                    for frame in range(int(lo),min(int(hi),len(names))):
                        image=f[f'FIBImages/{names[frame]}/Data'][:]
                        frame_sums,frame_weights=reduce_se_frame(image,edges[2],edges[1],shape[1:3])
                        sums+=frame_sums;weights+=frame_weights
                    np.divide(sums,weights,out=values[i],where=weights>0)
                    valid_counts[i]=weights
            coverage=np.clip(valid_counts/block_sizes,0.,1.).astype(np.float32)
            coverage[np.isclose(coverage,1.,rtol=0.,atol=1e-6)]=1.
            result.append(VolumePreview(layer.id,None,grid,values,coverage,valid_counts))
            continue
        key=(identity,r.source,r.stored_index,r.saved_id,r.intervals,r.frames,tuple(roi),tuple(frames),tuple(steps))
        cached=_CACHE.get(key) if use_cache else None
        if cached is None:
            context=reader_context(r) if reader_context else nullcontext((reader or read_signal)(path,r))
            with context as data:
                if data.shape!=(r.frames[1]-r.frames[0]+1,shape[1],shape[2]):raise ValueError('Volume coverage does not match its recipe.')
                values=np.full(tuple(counts()),np.nan,dtype=np.float32);valid_counts=np.zeros(values.shape,dtype=np.int32)
                for i,(lo,hi) in enumerate(zip(edges[0],edges[0][1:])):
                    first=max(int(lo),r.frames[0]);last=min(int(hi)-1,r.frames[1])
                    if first>last:continue
                    part=data[first-r.frames[0]:last-r.frames[0]+1,y0:y1+1,x0:x1+1]
                    valid=np.isfinite(part);sums=np.where(valid,part,0).sum(axis=0,dtype=np.float64);numbers=valid.sum(axis=0,dtype=np.int32)
                    for axis,offset in ((0,y0),(1,x0)):
                        idx=edges[axis+1][:-1]-offset
                        sums=np.add.reduceat(sums,idx,axis=axis);numbers=np.add.reduceat(numbers,idx,axis=axis)
                    valid_counts[i]=numbers;np.divide(sums,numbers,out=values[i],where=numbers>0)
                coverage=(valid_counts/block_sizes).astype(np.float32)
            cached=(values,coverage,valid_counts)
            for array in cached:array.setflags(write=False)
            if use_cache:
                _CACHE[key]=cached;_CACHE_BYTES+=sum(a.nbytes for a in cached)
                while _CACHE_BYTES>64*2**20 and len(_CACHE)>1:
                    _,old=_CACHE.popitem(last=False);_CACHE_BYTES-=sum(a.nbytes for a in old)
        else:_CACHE.move_to_end(key)
        result.append(VolumePreview(layer.id,r,grid,*cached))
    return result
