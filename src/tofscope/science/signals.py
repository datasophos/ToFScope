"""Immutable scientific signal definitions, independent of presentation state."""
from dataclasses import dataclass,field
from operator import index
from uuid import UUID,uuid4

from tofscope.science.integration import canonical_intervals
from tofscope.storage.dataset_io import locked_read


def _integer(value):
    if isinstance(value,bool):
        raise ValueError('Frame and channel indices must be integers.')
    try:
        return index(value)
    except TypeError as exc:
        raise ValueError('Frame and channel indices must be integers.') from exc


def interval_label(intervals):
    return ' ∪ '.join(f'{low:.4f}–{high:.4f}' for low,high in intervals)+' Th'


@dataclass(frozen=True)
class SignalRecipe:
    id: str=field(default_factory=lambda:str(uuid4()))
    label: str=''
    source: str='custom'
    stored_index: int|None=None
    saved_id: str|None=None
    intervals: tuple[tuple[float,float],...]=()
    frames: tuple[int,int]=(0,0)

    def __post_init__(self):
        try:
            identifier=str(UUID(self.id))
        except (ValueError,AttributeError,TypeError) as exc:
            raise ValueError('Signal ID must be a UUID.') from exc
        if self.source not in ('stored','custom','saved'):
            raise ValueError('Unknown signal source.')
        if not isinstance(self.label,str):
            raise ValueError('Signal label must be text.')
        try:
            first,last=map(_integer,self.frames)
        except (TypeError,ValueError) as exc:
            raise ValueError('Frames must contain two inclusive integer limits.') from exc
        if not 0<=first<=last:
            raise ValueError('Frames must be nonnegative and first <= last.')
        stored=_integer(self.stored_index) if self.stored_index is not None else None
        if ((self.source=='stored' and (stored is None or stored<0))
                or (self.source!='stored' and stored is not None)):
            raise ValueError('Only stored signals must reference a stored channel index.')
        if self.source=='saved':
            try:
                saved=str(UUID(self.saved_id))
            except (TypeError,AttributeError,ValueError) as exc:
                raise ValueError('Saved signals must reference a saved UUID.') from exc
        elif self.saved_id is not None:
            raise ValueError('Only saved signals may reference saved data.')
        else:
            saved=None
        windows=canonical_intervals(self.intervals,(float('-inf'),float('inf')))
        object.__setattr__(self,'id',identifier)
        object.__setattr__(self,'stored_index',stored)
        object.__setattr__(self,'saved_id',saved)
        object.__setattr__(self,'intervals',windows)
        object.__setattr__(self,'frames',(first,last))

    def to_dict(self):
        return dict(schema_version=3,id=self.id,label=self.label,source=self.source,
                    stored_index=self.stored_index,saved_id=self.saved_id,
                    intervals=[list(w) for w in self.intervals],frames=list(self.frames))

    @classmethod
    def from_dict(cls,value):
        version=value.get('schema_version')
        if version==2:
            source={'raw_reconstruction':'custom','stored':'stored'}.get(value.get('source'))
            if source is None:
                raise ValueError('Unknown legacy signal source.')
            if source=='stored' and value.get('stored_index') is None:
                raise ValueError('Legacy stored recipes need a stored channel index; choose that channel to restore it.')
            return cls(label=value.get('signal',''),source=source,stored_index=value.get('stored_index'),
                       intervals=((value['lower_Th'],value['upper_Th']),),frames=tuple(value['frames_inclusive']))
        if version!=3:
            raise ValueError('Unsupported signal recipe schema version.')
        return cls(id=value['id'],label=value.get('label',''),source=value['source'],
                   stored_index=value.get('stored_index'),saved_id=value.get('saved_id'),
                   intervals=value['intervals'],frames=value['frames'])

    def computation_key(self,path):
        from tofscope.storage.explorer import file_key
        return (file_key(path),self.source,self.stored_index,self.saved_id,self.intervals,self.frames)


@locked_read
def read_signal(path, recipe, progress=None):
    """Return (depth,y,x), with array index zero at recipe.frames[0]."""
    import h5py
    from tofscope.storage.explorer import stored_peak
    from tofscope.science.integration import custom_peak_windows
    if recipe.source=='saved':
        from tofscope.storage.integration_store import read_saved_integration,saved_integration_info
        info=saved_integration_info(path,recipe.saved_id)
        first,last=info['derivation']['frames']
        if recipe.frames[0]<first or recipe.frames[1]>last or recipe.intervals!=tuple(tuple(w) for w in info['derivation']['intervals']):
            raise ValueError('Saved reference coverage or intervals do not match its derivation.')
        return read_saved_integration(path,recipe.saved_id)[recipe.frames[0]-first:recipe.frames[1]-first+1]
    if recipe.source=='custom':
        return custom_peak_windows(path,recipe.intervals,*recipe.frames,progress)
    with h5py.File(path,'r') as f:
        shape=f['PeakData/PeakData'].shape
        if recipe.frames[1]>=shape[0] or recipe.stored_index>=shape[-1]:
            raise ValueError('Stored channel or frame range is outside the acquisition.')
    return stored_peak(path,recipe.stored_index)[recipe.frames[0]:recipe.frames[1]+1]
