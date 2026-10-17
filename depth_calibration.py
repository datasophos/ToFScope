"""Physical profile coordinates; acquisition intensities and frames stay intact."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class DepthAnchor:
    frame: int
    depth_nm: float


def convert_depth(value,source_unit,target_unit):
    scales={'nm':1.,'µm':1000.,'um':1000.,'mm':1e6}
    if source_unit not in scales or target_unit not in scales:raise ValueError('Depth units must be nm, µm or mm.')
    return np.asarray(value)*scales[source_unit]/scales[target_unit]


def validate_anchors(anchors,acquisition_frames):
    if type(acquisition_frames) is not int or acquisition_frames<1:raise ValueError('Acquisition must contain frames.')
    rows=[]
    for a in anchors:
        if type(a.frame) is not int or not 0<=a.frame<acquisition_frames:raise ValueError('Depth anchor frame must be an acquisition frame integer.')
        if not np.isfinite(a.depth_nm):raise ValueError('Depths must be finite.')
        if a.frame==0 and a.depth_nm!=0:raise ValueError('Frame 0 is fixed at depth 0.')
        rows.append(DepthAnchor(a.frame,float(a.depth_nm)))
    if not any(a.frame==0 for a in rows):rows.append(DepthAnchor(0,0.))
    rows.sort(key=lambda a:a.frame)
    for a,b in zip(rows,rows[1:]):
        if a.frame==b.frame:raise ValueError('Depth anchor frames must be unique.')
        if a.depth_nm>=b.depth_nm:raise ValueError('Depth must increase with acquisition frame.')
    return tuple(rows)


@dataclass(frozen=True)
class DepthCalibration:
    anchors: tuple[DepthAnchor,...]
    acquisition_frames: int

    def __post_init__(self):
        rows=validate_anchors(self.anchors,self.acquisition_frames)
        if len(rows)<2:raise ValueError('Add a positive-depth anchor to activate calibration.')
        object.__setattr__(self,'anchors',rows)

    def frame_to_depth(self,frames):
        return np.interp(frames,[a.frame for a in self.anchors],[a.depth_nm for a in self.anchors],left=np.nan,right=np.nan)

    def depth_to_frame(self,depth_nm):
        return np.interp(depth_nm,[a.depth_nm for a in self.anchors],[a.frame for a in self.anchors],left=np.nan,right=np.nan)

    def to_dict(self,unit='nm'):
        convert_depth(1,'nm',unit)
        return dict(anchors=[dict(frame=a.frame,depth_nm=a.depth_nm) for a in self.anchors],
                    acquisition_frames=self.acquisition_frames,unit='µm' if unit=='um' else unit,
                    interpolation='piecewise_linear',extrapolation=False)

    @classmethod
    def from_dict(cls,data):
        if data.get('interpolation')!='piecewise_linear' or data.get('extrapolation') is not False:
            raise ValueError('Unsupported depth interpolation policy.')
        convert_depth(1,'nm',data['unit'])
        return cls(tuple(DepthAnchor(**a) for a in data['anchors']),data['acquisition_frames'])
