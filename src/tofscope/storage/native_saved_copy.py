"""Add vendor-readable channels to a private saved copy, preserving exact recipes separately."""
import json
from dataclasses import replace
from math import prod

import h5py
import numpy as np

from tofscope.science.signals import SignalRecipe
from tofscope.storage.vendor_export import validate_native_layout


def native_fields(handle, recipe):
    """Validate native bounds with bounded mass-axis scratch."""
    data = handle['PeakData/PeakData']
    table = handle['PeakData/PeakTable']
    if len(recipe.intervals) != 1 or tuple(recipe.frames) != (0, data.shape[0] - 1):
        raise ValueError('Native peaks require all acquisition frames.')
    label = recipe.label.encode('ascii')
    if not label or len(label) >= table.dtype['label'].itemsize or any(char < 32 or char == 127 for char in label):
        raise ValueError('Native labels must be nonempty ASCII and fit the peak table.')
    lo, hi = recipe.intervals[0]
    limits = []
    for value, field, direction in [(lo, 'lower integration limit', np.inf), (hi, 'upper integration limit', -np.inf)]:
        dtype = table.dtype[field]
        native = np.array(value, dtype=dtype)[()]
        if (direction > 0 and native < value) or (direction < 0 and native > value):
            native = np.nextafter(native, np.array(direction, dtype=dtype))
        limits.append(native)
    axis = handle['FullSpectra/MassAxis']
    if axis.ndim != 1 or limits[0] >= limits[1]:
        raise ValueError('Native mass bounds cannot represent this signal.')
    for start in range(0, len(axis), 65536):
        values = np.asarray(axis[start:start + 65536], dtype=np.float64)
        if not np.array_equal((values >= lo) & (values <= hi), (values >= float(limits[0])) & (values <= float(limits[1]))):
            raise ValueError('Exact selected mass bins cannot be represented in the native peak table.')
    return label, *limits


def prepare_native_channels(handle, document, check, progress, previous=None, reserve_rebuild=lambda: None, previous_stale=()):
    """Modify only the unpublished copy. Return its updated document and notices."""
    warnings = list(previous_stale)
    try:
        validate_native_layout(handle)
        peak = handle['PeakData']
        old = peak['PeakData']
        table = peak['PeakTable']
        if old.ndim != 4 or old.dtype != np.float32 or len(table) != old.shape[-1]:
            raise ValueError('Unsupported native peak layout.')
        if table.size * table.dtype.itemsize > 1024 * 1024:
            raise ValueError('Native peak table exceeds the export memory limit.')
        if old.compression not in (None, 'gzip'):
            raise ValueError('Unsupported native compression.')
        if old.scaleoffset is not None:
            raise ValueError('Lossy native scale-offset filters cannot preserve exported signal values.')
        # HDF5 may decode a whole chunk even when reading only one frame.
        # Keep native chunk scratch within the copy/frame memory allowance.
        if old.chunks and prod(old.chunks) * old.dtype.itemsize > max(8 * 1024**2, old.shape[1] * old.shape[2] * old.dtype.itemsize):
            raise ValueError('Native chunks exceed the export memory limit.')
        if set(table.dtype.names or ()) != {'label', 'mass', 'lower integration limit', 'upper integration limit'}:
            raise ValueError('Unsupported native peak table.')
        if table.dtype['label'].kind != 'S' or any(
            table.dtype[field].kind != 'f'
            for field in ('mass', 'lower integration limit', 'upper integration limit')
        ):
            raise ValueError('Unsupported native peak-table field types.')
    except (ValueError, KeyError, TypeError) as exc:
        affected = [r.name for r in document.signals if r.recipe.source == 'custom' or r.name != r.recipe.label or tuple(r.recipe.frames) != (0, document.shape[0] - 1)]
        warnings.extend(f'{name}: TOFexplorer peak unavailable ({exc}).' for name in affected)
        payload = json.dumps({'signals': [], 'warnings': warnings, 'historical_warnings': list(previous_stale)}, ensure_ascii=False).encode('utf-8')
        if len(payload) > 1024 * 1024:
            raise ValueError('Native export report exceeds the metadata limit.')
        handle['ToFScope/Analysis'].create_dataset('native_export_json', data=np.frombuffer(payload, dtype='uint8'))
        return document, warnings

    # Every input channel is source data, even if an in-file attribute claims
    # ToFScope created it. In-file provenance is not evidence of ownership.
    keep = list(range(old.shape[-1]))
    remap = {old_index: i for i, old_index in enumerate(keep)}
    rows = list(table[:][keep])
    additions = []
    report = []
    updated_signals = []
    def matches(entry, source_frame):
        for index, existing in enumerate(rows):
            if existing != entry:
                continue
            for z in range(old.shape[0]):
                check()
                if not np.array_equal(old[z, :, :, index], source_frame(z), equal_nan=True):
                    break
            else:
                return index
        return None

    def record(row, index):
        report.append({'name': row.name, 'native_index': index, 'intervals': row.recipe.intervals, 'frames': row.recipe.frames})

    def write_report():
        historical = list(dict.fromkeys(w for w in warnings if 'may remain in the copy' in w or w in previous_stale))
        payload = json.dumps({'signals': report, 'warnings': warnings, 'historical_warnings': historical}, ensure_ascii=False).encode('utf-8')
        if len(payload) > 1024 * 1024:
            raise ValueError('Native export report exceeds the metadata limit.')
        handle['ToFScope/Analysis'].create_dataset('native_export_json', data=np.frombuffer(payload, dtype='uint8'))

    for row in document.signals:
        check()
        if row.recipe.source == 'stored':
            index = remap[row.recipe.stored_index]
            updated_signals.append(row.model_copy(update={'recipe': row.recipe.model_copy(update={'stored_index': index})}))
            if tuple(row.recipe.frames) != (0, old.shape[0] - 1):
                warnings.append(f'{row.name}: not available as a TOFexplorer peak with the selected frames; the original peak covers all frames.')
                continue
            if row.name == row.recipe.label:
                continue
            try:
                label = row.name.encode('ascii')
                if not label or len(label) >= table.dtype['label'].itemsize or any(char < 32 or char == 127 for char in label):
                    raise ValueError('label must fit the native ASCII field')
                entry = np.array(rows[index], dtype=table.dtype)[()]
                entry['label'] = label
                match = matches(entry, lambda z: old[z, :, :, index])
                if match is None:
                    additions.append((row, entry, index))
                else:
                    record(row, match)
            except (UnicodeEncodeError, ValueError) as exc:
                warnings.append(f'{row.name}: TOFexplorer label unavailable ({exc}).')
            continue
        updated_signals.append(row)
        try:
            recipe = SignalRecipe.from_dict(row.recipe.model_dump())
            disjoint = len(recipe.intervals) > 1
            recipe = replace(recipe, label=('Disjoint: ' if disjoint else '') + row.name)
            if disjoint:
                recipe = replace(recipe, intervals=((recipe.intervals[0][0], recipe.intervals[-1][1]),))
            label, low, high = native_fields(handle, recipe)
            if disjoint:
                warnings.append(f'{row.name}: TOFexplorer peak bounds include gaps; its displayed mass is the midpoint of those bounds. Exact intervals remain in ToFScope.')
            entry = np.zeros((), dtype=table.dtype)
            entry['label'], entry['mass'] = label, (float(low) + float(high)) / 2
            entry['lower integration limit'], entry['upper integration limit'] = low, high
            # Reuse only an exact native match; do not change or delete input peaks.
            data = handle[f'ToFScope/Integrations/{row.materialization_id}/data']
            match = matches(entry, lambda z: data[z])
            if match is None:
                additions.append((row, entry, None))
            else:
                record(row, match)
        except (ValueError, UnicodeEncodeError) as exc:
            warnings.append(f'{row.name}: not available as a TOFexplorer peak ({exc}).')

    if previous:
        current_ids = {r.materialization_id for r in document.signals if r.materialization_id}
        for row in previous.signals:
            if row.materialization_id and (row.materialization_id not in current_ids or not any(
                current.materialization_id == row.materialization_id and current.name == row.name and current.recipe.intervals == row.recipe.intervals and current.recipe.frames == row.recipe.frames
                for current in document.signals
            )):
                warnings.append(f'{row.name}: an earlier TOFexplorer peak may remain in the copy; original native peaks are preserved.')
            if row.recipe.source == 'stored' and row.name != row.recipe.label and not any(
                current.recipe.source == 'stored' and current.recipe.stored_index == row.recipe.stored_index and current.name == row.name
                for current in document.signals
            ):
                warnings.append(f'{row.name}: an earlier TOFexplorer label may remain in the copy; original native peaks are preserved.')

    new_count = len(keep) + len(additions)
    if not additions and keep == list(range(old.shape[-1])):
        write_report()
        return document.model_copy(update={'signals': tuple(updated_signals)}), warnings

    check()
    # The copied integration datasets must be reflected in free-space accounting
    # before the copy reservation is transferred to the rebuild reservation.
    handle.flush()
    reserve_rebuild()
    old_name = '_tofscope_original_peak_data'
    if old_name in peak:
        raise ValueError('Unexpected temporary native peak dataset.')
    peak.move('PeakData', old_name)
    old = peak[old_name]
    kwargs = {'dtype': old.dtype, 'fillvalue': old.fillvalue}
    if old.chunks:
        kwargs.update(chunks=(*old.chunks[:-1], min(old.chunks[-1], new_count)), compression=old.compression, shuffle=old.shuffle, fletcher32=old.fletcher32)
        if old.compression:
            kwargs['compression_opts'] = old.compression_opts
        if old.scaleoffset is not None:
            kwargs['scaleoffset'] = old.scaleoffset
    new = peak.create_dataset('PeakData', shape=(*old.shape[:-1], new_count), **kwargs)
    for key, value in old.attrs.items():
        new.attrs[key] = value
    # Raw chunk reads allocate the whole encoded chunk. Limit them to at most
    # one XY frame; larger chunks are copied through bounded frame slices.
    hdf_version = h5py.version.hdf5_version_tuple
    has_chunk_iterator = hasattr(old.id, 'chunk_iter') and (
        hdf_version >= (1, 12, 3) or (1, 10, 10) <= hdf_version < (1, 12, 0)
    )
    if old.chunks and old.chunks[-1] == 1 and prod(old.chunks) <= old.shape[1] * old.shape[2] and has_chunk_iterator:
        total = old.id.get_num_chunks()
        copied = 0
        def copy_chunk(info):
            nonlocal copied
            i = copied
            copied += 1
            if i % 1000 == 0:
                check()
                progress('Copying native peaks', i, total)
            offset = info.chunk_offset
            if offset[-1] not in remap:
                return None
            mask, payload = old.id.read_direct_chunk(offset)
            target = (*offset[:-1], remap[offset[-1]])
            new.id.write_direct_chunk(target, payload, filter_mask=mask)
            if new.id.read_direct_chunk(target) != (mask, payload):
                raise ValueError('Native peak chunk verification failed.')
            return None
        old.id.chunk_iter(copy_chunk)
    else:
        for z in range(old.shape[0]):
            for old_index in keep:
                check()
                values = old[z, :, :, old_index]
                new[z, :, :, remap[old_index]] = values
                if not np.array_equal(new[z, :, :, remap[old_index]], values, equal_nan=True):
                    raise ValueError('Native peak verification failed.')
    for n, (row, entry, source_index) in enumerate(additions):
        data = handle[f'ToFScope/Integrations/{row.materialization_id}/data'] if source_index is None else None
        for z in range(old.shape[0]):
            check()
            values = data[z] if data is not None else old[z, :, :, source_index]
            new[z, :, :, len(keep) + n] = values
            if not np.array_equal(new[z, :, :, len(keep) + n], values, equal_nan=True):
                raise ValueError('Native signal verification failed.')
            progress('Preparing TOFexplorer peak ' + row.name, z + 1, old.shape[0])
        rows.append(entry)
        record(row, len(keep) + n)
    attrs = dict(table.attrs)
    del peak['PeakTable']
    table = peak.create_dataset('PeakTable', data=np.asarray(rows, dtype=table.dtype))
    for key, value in attrs.items():
        table.attrs[key] = value
    del peak[old_name]
    if 'NbrPeaks' in handle.attrs:
        original_count = handle.attrs['NbrPeaks']
        dtype = np.asarray(original_count).dtype
        if np.issubdtype(dtype, np.integer) and new_count > np.iinfo(dtype).max:
            raise ValueError('Native peak count exceeds the vendor attribute range.')
        handle.attrs.modify('NbrPeaks', new_count)
    else:
        handle.attrs['NbrPeaks'] = new_count
    write_report()
    return document.model_copy(update={'signals': tuple(updated_signals), 'shape': (*document.shape[:-1], new_count)}), warnings
