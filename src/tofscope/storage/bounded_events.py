"""Admitted, pooled VLEN reads using the public HDF5 memory-manager API.

Reserve each arena (including numerical scratch) before allocating its memory.
HDF5's per-cell callbacks only hand out slices; they create no per-cell budget
objects, malloc/free calls or NumPy arrays. No on-disk format parsing is used.
"""

from contextlib import contextmanager, ExitStack
import ctypes as C
import h5py
from h5py._objects import phil
import numpy as np

from tofscope.science.integration import EventBatch


class VLen(C.Structure):
    _fields_ = [("length", C.c_size_t), ("pointer", C.c_void_p)]


@contextmanager
def admitted_events(raw, frame, reserve):
    """Borrow a packed event batch until the context exits, with bounded scratch."""
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
    arenas = []
    failure = []
    with phil, ExitStack() as stack:

        def manage(identifier):
            stack.callback(identifier.close)
            return identifier

        shape = raw.shape[1:]
        count = int(np.prod(shape))
        # Descriptors, offset/length tables, masks and per-cell reduction scratch.
        stack.enter_context(reserve(count * 512 + 4096))
        buffer = (VLen * count)()
        next_capacity = max(4096, min(count * base.itemsize, 1024**2))

        @allocate_type
        def allocate(size, _):
            nonlocal next_capacity
            try:
                if size % base.itemsize:
                    raise ValueError("Raw event allocation is not a whole sample.")
                size = max(base.itemsize, int(size))
                if not arenas or arenas[-1][1] + size > arenas[-1][0].nbytes:
                    capacity = max(size, next_capacity)
                    # Payload plus conversions, indices, masks, prefix sums and copies.
                    stack.enter_context(
                        reserve(capacity + capacity // base.itemsize * 64)
                    )
                    arena = np.empty(capacity // base.itemsize, dtype=base)
                    arenas.append([arena, 0, arena.ctypes.data])
                    next_capacity = min(capacity * 2, 1024**2)
                arena, used, start = arenas[-1]
                pointer = start + used
                arenas[-1][1] += size
                return pointer
            except BaseException as exc:
                failure.append(exc)
                return None

        @free_type
        def free(pointer, _):
            # Arena memory is owned by this context, including failed reads.
            pass

        memory_type = manage(raw.id.get_type())
        file_space = manage(raw.id.get_space())
        file_space.select_hyperslab((frame, 0, 0), (1, *shape))
        memory_space = manage(h5py.h5s.create_simple(shape))
        transfer = manage(h5py.h5p.create(h5py.h5p.DATASET_XFER))
        if set_manager(transfer.id, allocate, None, free, None) < 0:
            raise ValueError("HDF5 bounded allocator unavailable.")
        status = read(
            raw.id.id, memory_type.id, memory_space.id,
            file_space.id, transfer.id, C.byref(buffer),
        )
        if failure:
            raise failure[0]
        if status < 0:
            raise ValueError("Raw event read failed.")

        descriptors = np.frombuffer(
            buffer,
            dtype=np.dtype([("length", np.uintp), ("pointer", np.uintp)], align=True),
        )
        lengths = descriptors["length"].astype(np.int64)
        pointers = descriptors["pointer"]
        offsets = np.zeros(count, dtype=np.int64)
        assigned = lengths == 0
        prefix = 0
        pieces = []
        for arena, used, start in arenas:
            cells = (pointers >= start) & (pointers < start + used) & (lengths > 0)
            relative = pointers[cells] - start
            local = (relative // base.itemsize).astype(np.int64)
            if np.any(relative % base.itemsize) or np.any(
                local + lengths[cells] > used // base.itemsize
            ):
                raise ValueError("Raw event descriptor exceeds admitted memory.")
            offsets[cells] = prefix + local
            assigned |= cells
            pieces.append(arena[:used // base.itemsize])
            prefix += used // base.itemsize
        if not assigned.all() or np.any(lengths < 0):
            raise ValueError("Raw event descriptor is outside admitted memory.")
        samples = np.concatenate(pieces) if pieces else np.empty(0, dtype=base)
        yield EventBatch(samples, offsets, lengths, shape)
