"""Native PeakData copies; only full-coverage contiguous recipes are eligible.

Reader compatibility is testable here. Commercial software compatibility needs
an observed round trip in ToF-Explorer before it can be claimed.
"""
from pathlib import Path
import h5py
import numpy as np

_FIELDS={'label','mass','lower integration limit','upper integration limit'}


def validate_native_recipe(h5,recipe):
    data=h5['PeakData/PeakData'];table=h5['PeakData/PeakTable']
    if data.ndim!=4 or data.dtype!=np.float32 or set(table.dtype.names or ())!=_FIELDS or len(table)!=data.shape[-1]:raise ValueError('Unsupported native PeakData/PeakTable schema.')
    if len(recipe.intervals)!=1 or tuple(recipe.frames)!=(0,data.shape[0]-1):raise ValueError('Commercial-native export currently requires one contiguous mass interval and every acquisition frame.')
    if data.compression not in (None,'gzip'):raise ValueError('Unsupported native compression pipeline.')
    label=recipe.label.encode('ascii')
    if not label or len(label)>=table.dtype['label'].itemsize:raise ValueError('Native labels must be nonempty ASCII and fit the vendor label field.')
    lo,hi=recipe.intervals[0];axis=np.asarray(h5['FullSpectra/MassAxis'],dtype=np.float64)
    limits=[]
    for value,field,direction in [(lo,'lower integration limit',np.inf),(hi,'upper integration limit',-np.inf)]:
        dtype=table.dtype[field];native=np.array(value,dtype=dtype)[()]
        if (direction>0 and native<value) or (direction<0 and native>value):native=np.nextafter(native,np.array(direction,dtype=dtype))
        limits.append(native)
    if limits[0]>=limits[1] or not np.array_equal((axis>=lo)&(axis<=hi),(axis>=float(limits[0]))&(axis<=float(limits[1]))):raise ValueError('Exact selected mass bins cannot be represented by this native peak-table dtype.')
    return label,*limits


def validate_native_layout(h5):
    seen={h5py.h5o.get_info(h5.id).addr}
    def contains_reference(dtype):
        dtype=np.dtype(dtype)
        if h5py.check_dtype(ref=dtype) is not None:return True
        if dtype.fields and any(contains_reference(field[0]) for field in dtype.fields.values()):return True
        if dtype.subdtype and contains_reference(dtype.subdtype[0]):return True
        variable=h5py.check_dtype(vlen=dtype)
        return isinstance(variable,np.dtype) and contains_reference(variable)
    def attributes(obj):
        for name in obj.attrs:
            identifier=obj.attrs.get_id(name)
            try:references=contains_reference(identifier.dtype)
            finally:identifier.close()
            if references:raise ValueError('HDF5 object-reference attributes are unsupported.')
    attributes(h5)
    def walk(group):
        for name in group:
            link=group.get(name,getlink=True)
            if isinstance(link,(h5py.ExternalLink,h5py.SoftLink)):raise ValueError('Linked HDF5 layouts require a separate compatibility review.')
            obj=group[name]
            address=h5py.h5o.get_info(obj.id).addr
            if address in seen:raise ValueError('Hard-linked aliases and cycles require a separate compatibility review.')
            seen.add(address);attributes(obj)
            if isinstance(obj,h5py.Group):walk(obj)
            elif contains_reference(obj.dtype):raise ValueError('HDF5 object-reference datasets are unsupported.')
            elif obj.is_virtual or obj.external:raise ValueError('Virtual datasets and external raw storage require a separate compatibility review.')
    walk(h5)


def export_native_copy(source_path,destination_path,recipes,*,volumes=None,progress=None):
    from dataset_io import dataset_lock
    with dataset_lock(source_path):
        return _export_native_copy(source_path,destination_path,recipes,volumes=volumes,progress=progress)


def _export_native_copy(source_path,destination_path,recipes,*,volumes=None,progress=None):
    from signals import read_signal
    source=Path(source_path).resolve();destination=Path(destination_path)
    if destination.exists():raise FileExistsError('Native output already exists; select a new output path.')
    recipes=tuple(recipes)
    if not recipes:raise ValueError('At least one native peak recipe is required.')
    with h5py.File(source,'r') as original:
        validate_native_layout(original);fields=[validate_native_recipe(original,r) for r in recipes]
        old=original['PeakData/PeakData'];table=original['PeakData/PeakTable']
        shape=(*old.shape[:-1],old.shape[-1]+len(recipes))
        with h5py.File(destination,'x') as result:
            for key,value in original.attrs.items():result.attrs[key]=value
            for name in original:
                if name!='PeakData':original.copy(name,result)
            peak=result.create_group('PeakData')
            for key,value in original['PeakData'].attrs.items():peak.attrs[key]=value
            for name in original['PeakData']:
                if name not in ('PeakData','PeakTable'):original['PeakData'].copy(name,peak)
            kwargs=dict(dtype=old.dtype,fillvalue=old.fillvalue)
            if old.chunks:
                kwargs.update(chunks=old.chunks,compression=old.compression,shuffle=old.shuffle,fletcher32=old.fletcher32)
                if old.compression:kwargs['compression_opts']=old.compression_opts
                if old.scaleoffset is not None:kwargs['scaleoffset']=old.scaleoffset
            new=peak.create_dataset('PeakData',shape=shape,**kwargs)
            for key,value in old.attrs.items():new.attrs[key]=value
            if old.chunks:
                total=old.id.get_num_chunks()
                for i,selection in enumerate(old.iter_chunks()):
                    offset=tuple(part.start for part in selection)
                    if old.id.get_chunk_info_by_coord(offset).size==0:continue
                    mask,payload=old.id.read_direct_chunk(offset)
                    new.id.write_direct_chunk(offset,payload,filter_mask=mask)
                    if progress and i%5000==0:progress('Copying native peaks',i,total)
            else:
                for z in range(old.shape[0]):new[z,:,:,:old.shape[-1]]=old[z]
            rows=np.zeros(shape[-1],dtype=table.dtype);rows[:len(table)]=table[:]
            for i,(recipe,fields_row) in enumerate(zip(recipes,fields)):
                values=np.asarray(volumes[i] if volumes is not None else read_signal(source,recipe))
                if values.shape!=shape[:-1] or values.dtype!=np.float32 or not np.isfinite(values).all():raise ValueError('Native channel must be finite full-XY float32 data covering every frame.')
                index=old.shape[-1]+i
                for z in range(shape[0]):new[z,:,:,index]=values[z]
                label,lo,hi=fields_row;rows[index]['label']=label;rows[index]['mass']=(float(lo)+float(hi))/2
                rows[index]['lower integration limit']=lo;rows[index]['upper integration limit']=hi
            rebuilt=peak.create_dataset('PeakTable',data=rows)
            for key,value in table.attrs.items():rebuilt.attrs[key]=value
            if 'NbrPeaks' in result.attrs:result.attrs.modify('NbrPeaks',shape[-1])
            else:result.attrs['NbrPeaks']=shape[-1]
            result.flush()
    return destination
