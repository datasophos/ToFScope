"""Run in a disposable environment with h5py, RosettaSciIO, HyperSpy, psutil."""

from concurrent.futures import ThreadPoolExecutor
import gc
import json
import os
from pathlib import Path
import sys
import time
import h5py
import numpy as np
import psutil
import rsciio
import hyperspy.api as hs
from rsciio.tofwerk import file_reader
from rsciio.utils.file import get_file_handle

path = Path(sys.argv[1])
process = psutil.Process()
report = {
    "versions": {
        "h5py": h5py.__version__,
        "rsciio": rsciio.__version__,
        "hyperspy": __import__("hyperspy").__version__,
    },
    "runs": [],
}
with h5py.File(path) as f:
    expected = f["PeakData/PeakData"][1:3, :, :, 0:1]


def run(backend, lazy):
    before = process.num_fds()
    rss = process.memory_info().rss
    t = time.perf_counter()
    meta = []
    if backend == "h5py":
        with h5py.File(path) as f:
            data = f["PeakData/PeakData"][1:3, :, :, 0:1]
    elif backend == "rsciio":
        s = file_reader(
            path,
            lazy=lazy,
            signal="nominal_peak_data",
            depth_range=(1, 3),
            mz_range=(1.5, 2.5),
            show_progressbar=False,
        )[0]
        a = s["data"]
        meta = list(s["metadata"])
        handle = get_file_handle(a) if lazy else None
        data = a.compute() if lazy else a
        if handle is not None:
            handle.close()
    else:
        s = hs.load(
            path,
            file_format="Tofwerk",
            lazy=lazy,
            signal="nominal_peak_data",
            depth_range=(1, 3),
            mz_range=(1.5, 2.5),
            show_progressbar=False,
        )
        meta = list(s.metadata.as_dictionary())
        a = s.data
        handle = get_file_handle(a) if lazy else None
        data = a.compute() if lazy else a
        if handle is not None:
            handle.close()
    np.testing.assert_array_equal(np.asarray(data).reshape(expected.shape), expected)
    gc.collect()
    return dict(
        backend=backend,
        lazy=lazy,
        ms=(time.perf_counter() - t) * 1000,
        rss_delta=process.memory_info().rss - rss,
        open_fds_delta=process.num_fds() - before,
        shape=list(data.shape),
        equal=True,
        metadata_keys=meta,
    )


for backend in ["h5py", "rsciio", "hyperspy"]:
    for lazy in [False] if backend == "h5py" else [False, True]:
        try:
            report["runs"].append(run(backend, lazy))
            with ThreadPoolExecutor(2) as pool:
                report["runs"].extend(pool.map(lambda _: run(backend, lazy), range(2)))
        except Exception as e:
            report["runs"].append(dict(backend=backend, lazy=lazy, error=str(e)))
print(json.dumps(report, indent=2))
