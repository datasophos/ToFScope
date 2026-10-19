"""Versioned full-resolution integration records in an additive HDF5 namespace."""
from dataclasses import dataclass,field,asdict
from datetime import datetime,timezone
from uuid import UUID
import json
import h5py
import numpy as np
from tofscope.storage.dataset_io import locked_read

ROOT='ToFScope/Integrations'


def checked_uuid(value):
    if not isinstance(value,str):raise ValueError('A canonical integration UUID is required.')
    try:parsed=UUID(value)
    except (ValueError,AttributeError):raise ValueError('A canonical integration UUID is required.') from None
    if str(parsed)!=value:raise ValueError('A canonical integration UUID is required.')
    return value


@dataclass(frozen=True)
class IntegrationRecord:
    id: str
    derivation: dict
    spatial_shape: tuple[int,int]
    source_identity: dict
    normalization: dict
    calibration: dict | None = None
    created_utc: str = field(default_factory=lambda:datetime.now(timezone.utc).isoformat())
    app_version: str = '0.1.0'
    schema_version: int = 1

    def __post_init__(self):
        checked_uuid(self.id)
        if self.schema_version!=1:raise ValueError('Unsupported integration schema version.')
        recipe=self.derivation
        if recipe.get('schema_version')!=3 or recipe.get('source') not in ('stored','custom'):raise ValueError('Saved records must retain an underlying derivation recipe.')
        checked_uuid(recipe['id'])
        frames=recipe['frames']
        if len(frames)!=2 or any(type(v) is not int for v in frames) or not 0<=frames[0]<=frames[1]:raise ValueError('Invalid integration frame coverage.')
        if len(self.spatial_shape)!=2 or any(type(v) is not int or v<=0 for v in self.spatial_shape):raise ValueError('Integration shape must be full XY.')
        from tofscope.science.integration import canonical_intervals
        canonical_intervals(recipe['intervals'],(-float('inf'),float('inf')))


def write_integration_group(h5,record,frame_data):
    checked_uuid(record.id)
    parent=h5.require_group(ROOT)
    if record.id in parent:raise ValueError('An integration with this UUID already exists.')
    group=parent.create_group(record.id);group.attrs.update(schema_version=1,complete=False)
    metadata=asdict(record);metadata['spatial_shape']=list(record.spatial_shape)
    group.create_dataset('recipe_json',data=json.dumps(metadata,ensure_ascii=False),dtype=h5py.string_dtype('utf-8'))
    first,last=record.derivation['frames'];ny,nx=record.spatial_shape
    data=group.create_dataset('data',shape=(last-first+1,ny,nx),dtype='float32',chunks=(1,ny,nx),compression='gzip',shuffle=True)
    count=0
    for frame in frame_data:
        array=np.asarray(frame)
        if count>=data.shape[0] or array.shape!=(ny,nx) or array.dtype!=np.float32 or not np.isfinite(array).all():raise ValueError('Integration frames must be finite full-XY float32 data with exact declared coverage.')
        data[count]=array;count+=1
    if count!=data.shape[0]:raise ValueError('Integration frame count does not match declared coverage.')
    group.attrs['complete']=True
    return record.id


def _read_info(group):
    if not bool(group.attrs.get('complete',False)):raise ValueError('Integration is incomplete.')
    if int(group.attrs.get('schema_version',0))!=1:raise ValueError('Unsupported integration schema version.')
    raw=group['recipe_json'][()];metadata=json.loads(raw.decode() if isinstance(raw,bytes) else raw)
    record=IntegrationRecord(**{**metadata,'spatial_shape':tuple(metadata['spatial_shape'])})
    if group.name.rsplit('/',1)[-1]!=record.id:raise ValueError('Integration UUID does not match its group.')
    first,last=record.derivation['frames']
    if group['data'].shape!=(last-first+1,*record.spatial_shape) or group['data'].dtype!=np.float32:raise ValueError('Saved integration shape/dtype mismatch.')
    return metadata


@locked_read
def list_saved_integrations(path):
    result=[]
    with h5py.File(path,'r') as h5:
        for name,group in h5.get(ROOT,{}).items():
            try:checked_uuid(name);result.append(_read_info(group))
            except (ValueError,KeyError,TypeError):continue
    return result


@locked_read
def saved_integration_info(path,saved_id):
    checked_uuid(saved_id)
    with h5py.File(path,'r') as h5:return _read_info(h5[f'{ROOT}/{saved_id}'])


@locked_read
def read_saved_integration(path,saved_id):
    checked_uuid(saved_id)
    with h5py.File(path,'r') as h5:
        group=h5[f'{ROOT}/{saved_id}'];_read_info(group);data=group['data'][:]
    if not np.isfinite(data).all():raise ValueError('Saved integration contains non-finite values.')
    return data
