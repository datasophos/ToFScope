"""Shared, acquisition-aligned previews with a total visible-voxel budget."""
from collections import OrderedDict
from dataclasses import dataclass,replace
import math
import numpy as np
from explorer import inspect_file,file_key
from signals import SignalRecipe,read_signal

COLORSCALES=('Viridis','Magma','Plasma','Cividis','Reds','Blues','Greens','Purples')


@dataclass
class VolumeLayer:
    id: str
    recipe: SignalRecipe
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
    recipe: SignalRecipe
    grid: PreviewGrid
    values: np.ndarray
    coverage: np.ndarray
    valid_counts: np.ndarray


_CACHE=OrderedDict()
_CACHE_BYTES=0

def clear_preview_cache():
    global _CACHE_BYTES
    _CACHE.clear();_CACHE_BYTES=0


def build_layer_previews(path,layers,roi,frames,*,quality,voxel_budget=500_000,reader=None):
    global _CACHE_BYTES
    enabled=[layer for layer in layers if layer.visible]
    if not enabled:return []
    if type(voxel_budget) is not int or voxel_budget<len(enabled):raise ValueError('Preview budget must allow at least one voxel per visible layer.')
    if quality not in ('Fast','Detailed'):raise ValueError('Unknown preview quality.')
    meta=inspect_file(path);shape=meta['shape']
    if len(frames)!=2 or any(type(z) is not int for z in frames) or not 0<=frames[0]<=frames[1]<shape[0]:raise ValueError('Invalid preview depth window.')
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
    grid=PreviewGrid(z,y,x,edges,bool(fov),extent);result=[];identity=file_key(path)
    block_sizes=np.diff(edges[0])[:,None,None]*np.diff(edges[1])[None,:,None]*np.diff(edges[2])[None,None,:]
    for layer in enabled:
        r=layer.recipe
        key=(identity,r.source,r.stored_index,r.saved_id,r.intervals,r.frames,tuple(roi),tuple(frames),tuple(steps))
        cached=_CACHE.get(key)
        if cached is None:
            data=(reader or read_signal)(path,r)
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
            _CACHE[key]=cached;_CACHE_BYTES+=sum(a.nbytes for a in cached)
            while _CACHE_BYTES>64*2**20 and len(_CACHE)>1:
                _,old=_CACHE.popitem(last=False);_CACHE_BYTES-=sum(a.nbytes for a in old)
        else:_CACHE.move_to_end(key)
        result.append(VolumePreview(layer.id,r,grid,*cached))
    return result
