"""Compact HDF5 copying with bounded event payloads and preserved internal links."""
from contextlib import ExitStack
import h5py
import numpy as np
from tofscope.storage.bounded_events import admitted_events, write_events
from tofscope.storage.saved_files import COPY_BYTES


# Attributes are metadata, not unbounded acquisition payloads. HDF5 attribute
# reads lack the dataset VLEN allocator hook. Fixed-buffer conversion bounds
# Python payloads; HDF5 can still use its own transient conversion buffers.
ATTRIBUTE_STRING_BYTES = 1024 * 1024


def _remap(value, dtype, source, target, seen):
    reference = h5py.check_dtype(ref=dtype)
    if reference is not None:
        result = np.empty(np.shape(value), dtype=dtype)
        for idx in np.ndindex(result.shape):
            ref = np.asarray(value)[idx]
            if not ref:
                result[idx] = reference()
                continue
            address = h5py.h5o.get_info(source.file[ref].id).addr
            if address not in seen:
                raise ValueError('Attribute references an object without an internal link.')
            path = seen[address]
            if reference is h5py.RegionReference:
                space = h5py.h5r.get_region(ref, source.file.id)
                try:
                    result[idx] = h5py.h5r.create(target.file.id, path.encode(), h5py.h5r.DATASET_REGION, space)
                finally:
                    space.close()
            else:
                result[idx] = target.file[path].ref
        return result
    if dtype.subdtype:
        return _remap(value, dtype.subdtype[0], source, target, seen)
    if dtype.fields:
        result = np.array(value, copy=True)
        for field in dtype.names:
            result[field] = _remap(result[field], dtype[field], source, target, seen)
        return result
    return value


def _attributes(source, target, reserve, seen):
    for key in source.attrs:
        identifier = source.attrs.get_id(key)
        try:
            dtype = identifier.dtype
            string = h5py.check_string_dtype(dtype)
            if _has_vlen(dtype):
                if string is None:
                    raise ValueError('Unsupported variable-length attribute in raw acquisition.')
                count = int(np.prod(identifier.shape))
                with reserve(count * ATTRIBUTE_STRING_BYTES * 4 + 4096):
                    buffer = np.zeros(identifier.shape, dtype=h5py.string_dtype(string.encoding, ATTRIBUTE_STRING_BYTES))
                    identifier.read(buffer)
                    # Leave one byte for the terminator; reject ambiguous truncation.
                    if any(len(cell) >= ATTRIBUTE_STRING_BYTES - 1 for cell in buffer.flat):
                        raise ValueError('Raw acquisition attribute exceeds the 1 MiB string limit.')
                    value = buffer.astype(object)
                    target.attrs.create(key, value, dtype=dtype)
                    del value, buffer
            else:
                with reserve(int(identifier.get_storage_size()) * 8 + 4096):
                    value = _remap(source.attrs[key], dtype, source, target, seen)
                    target.attrs.create(key, value, dtype=dtype)
                    del value
        finally:
            identifier.close()


def _has_vlen(dtype):
    if h5py.check_dtype(vlen=dtype) is not None:
        return True
    if dtype.subdtype:
        return _has_vlen(dtype.subdtype[0])
    return bool(dtype.fields and any(_has_vlen(dtype[name]) for name in dtype.names))


def compact_copy(source, target, check, progress, reserve):
    """Copy live objects only, keeping original values, filters and aliases.

    Numerical datasets use HDF5 object copying with admitted chunk scratch.
    Raw VLEN events use our bounded allocator one frame at a time. No acquisition
    data is re-integrated by this operation and no deleted file space is copied.
    """
    seen = {h5py.h5o.get_info(source.id).addr: '/'}
    event_address = h5py.h5o.get_info(source['FullSpectra/EventList'].id).addr
    attributes = [(source.name, target.name)]

    def group(src, dst):
        for key in src:
            check()
            link = src.get(key, getlink=True)
            if isinstance(link, h5py.SoftLink):
                dst[key] = h5py.SoftLink(link.path)
                continue
            if not isinstance(link, h5py.HardLink):
                raise ValueError('External HDF5 links cannot be copied.')
            item = src[key]
            address = h5py.h5o.get_info(item.id).addr
            if address in seen:
                dst[key] = target[seen[address]]
                continue
            destination = (dst.name.rstrip('/') + '/' + key)
            seen[address] = destination
            if isinstance(item, h5py.Group):
                properties = item.id.get_create_plist()
                try:
                    copied = h5py.Group(h5py.h5g.create(dst.id, key.encode(), gcpl=properties))
                finally:
                    properties.close()
                attributes.append((item.name, copied.name))
                group(item, copied)
            elif item.dtype.hasobject:
                if address != event_address or item.ndim != 3:
                    raise ValueError('Unsupported variable-length dataset in raw acquisition.')
                with ExitStack() as stack:
                    datatype = item.id.get_type(); stack.callback(datatype.close)
                    space = item.id.get_space(); stack.callback(space.close)
                    properties = item.id.get_create_plist(); stack.callback(properties.close)
                    copied = h5py.Dataset(h5py.h5d.create(dst.id, key.encode(), datatype, space, dcpl=properties))
                attributes.append((item.name, copied.name))
                for z in range(item.shape[0]):
                    check()
                    with admitted_events(item, z, reserve) as events:
                        write_events(copied, z, events, reserve)
                    progress('Copying raw events', z + 1, item.shape[0])
            else:
                chunk_bytes = int(np.prod(item.chunks)) * item.dtype.itemsize if item.chunks else min(item.size * item.dtype.itemsize, COPY_BYTES)
                with reserve(int(chunk_bytes) * 3 + 4096):
                    src.copy(key, dst, name=key, without_attrs=True)
                attributes.append((item.name, destination))
                progress('Copying acquisition metadata and images', 0, 0)
            check()
    group(source, target)
    for src_path, dst_path in attributes:
        check()
        _attributes(source[src_path], target[dst_path], reserve, seen)
    target.flush()
