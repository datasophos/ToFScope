"""Read primitive VLEN events with admission before HDF5 allocates their payload.

h5py does not expose H5Pset_vlen_mem_manager. Use the public HDF5 API from
h5py's own linked library, under its global lock. Missing symbols fail closed.
The allocator charges payload plus a conservative 64 bytes/event for the
NumPy integration temporaries, before calling malloc. No on-disk format parsing.
"""

from contextlib import contextmanager, ExitStack
import ctypes as C
import h5py
from h5py._objects import phil
import numpy as np


class VLen(C.Structure):
    _fields_ = [("length", C.c_size_t), ("pointer", C.c_void_p)]


@contextmanager
def admitted_events(raw, frame, reserve):
    base = h5py.check_dtype(vlen=raw.dtype)
    if base is None or np.dtype(base).kind not in "iu" or np.dtype(base).itemsize > 8:
        raise ValueError("Raw event type cannot be safely bounded.")
    base = np.dtype(base)
    try:
        library = C.CDLL(h5py.h5d.__file__)
        set_manager = library.H5Pset_vlen_mem_manager
        read = library.H5Dread
    except (OSError, AttributeError):
        raise ValueError("This HDF5 build lacks bounded raw-event reading.") from None
    hid = C.c_int64
    allocate_type = C.CFUNCTYPE(C.c_void_p, C.c_size_t, C.c_void_p)
    free_type = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p)
    set_manager.argtypes = [hid, allocate_type, C.c_void_p, free_type, C.c_void_p]
    set_manager.restype = C.c_int
    read.argtypes = [hid, hid, hid, hid, hid, C.c_void_p]
    read.restype = C.c_int
    libc = C.CDLL(None)
    libc.malloc.argtypes = [C.c_size_t]
    libc.malloc.restype = C.c_void_p
    libc.free.argtypes = [C.c_void_p]
    allocations = {}
    failure = []

    @allocate_type
    def allocate(size, _):
        reservation = None
        try:
            # Payload, conversions, masks, indexing, cumsums and transient copies.
            reservation = reserve(
                int(size) + ((int(size) + base.itemsize - 1) // base.itemsize) * 64
            )
            pointer = libc.malloc(max(1, size))
            if not pointer:
                raise MemoryError("Raw allocation failed.")
            allocations[pointer] = reservation
            return pointer
        except BaseException as exc:
            if reservation is not None:
                reservation.release()
            failure.append(exc)
            return None

    @free_type
    def free(pointer, _):
        reservation = allocations.pop(pointer, None)
        if reservation is not None:
            libc.free(pointer)
            reservation.release()

    try:
        with phil, ExitStack() as stack:

            def manage(identifier):
                stack.callback(identifier.close)
                return identifier

            memory_type = manage(raw.id.get_type())
            file_space = manage(raw.id.get_space())
            shape = raw.shape[1:]
            count = int(np.prod(shape))
            # Descriptor/object arrays and per-pixel Python/NumPy headers.
            stack.enter_context(reserve(count * 512 + 4096))
            buffer = (VLen * count)()
            file_space.select_hyperslab((frame, 0, 0), (1, *shape))
            memory_space = manage(h5py.h5s.create_simple(shape))
            transfer = manage(h5py.h5p.create(h5py.h5p.DATASET_XFER))
            if set_manager(transfer.id, allocate, None, free, None) < 0:
                raise ValueError("HDF5 bounded allocator unavailable.")
            status = read(
                raw.id.id,
                memory_type.id,
                memory_space.id,
                file_space.id,
                transfer.id,
                C.byref(buffer),
            )
            if failure:
                raise failure[0]
            if status < 0:
                raise ValueError("Raw event read failed.")
            events = np.empty(shape, dtype=object)
            element_type = np.ctypeslib.as_ctypes_type(base)
            for i, cell in enumerate(buffer):
                events.flat[i] = (
                    np.ctypeslib.as_array(
                        (element_type * cell.length).from_address(cell.pointer)
                    )
                    if cell.length
                    else np.empty(0, dtype=base)
                )
            yield events
    finally:
        for pointer in list(allocations):
            free(pointer, None)
