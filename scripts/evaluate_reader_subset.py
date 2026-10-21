"""Isolated real-file reader peaks. Run with h5py, RosettaSciIO, HyperSpy, psutil.

--compare launches a fresh interpreter for every backend/mode, avoiding cumulative
RSS measurements. The acquisition is read only and no adjacent locks are created.
"""

import argparse
import gc
import importlib.metadata
import json
from pathlib import Path
import resource
import subprocess
import sys
import time
import h5py
import numpy as np
import psutil


def measure(path, backend, lazy, channel):
    start = time.perf_counter()
    with h5py.File(path, "r") as f:
        table = f["PeakData/PeakTable"][:]
        stop = min(4, f["PeakData/PeakData"].shape[0])
        expected = f["PeakData/PeakData"][:stop, :, :, channel : channel + 1]
        mass = float(table[channel]["mass"])
        masses = np.sort(np.unique(table["mass"]))
        index = list(masses).index(mass)
        low = (float(masses[index - 1]) + mass) / 2 if index else mass - 0.1
        high = (
            (mass + float(masses[index + 1])) / 2
            if index + 1 < len(masses)
            else mass + 0.1
        )
        chunks = f["PeakData/PeakData"].chunks or (
            1,
            *f["PeakData/PeakData"].shape[1:3],
            1,
        )
    metadata = []
    if backend == "h5py":
        with h5py.File(path, "r") as f:
            data = f["PeakData/PeakData"][:stop, :, :, channel : channel + 1]
    else:
        from rsciio.utils.file import get_file_handle

        kwargs = dict(
            signal="nominal_peak_data",
            lazy=lazy,
            depth_range=(0, stop),
            mz_range=(low, high),
            chunks=chunks,
            show_progressbar=False,
        )
        if backend == "hyperspy":
            import hyperspy.api as hs

            signal = hs.load(path, file_format="Tofwerk", **kwargs)
            array = signal.data
            metadata = list(signal.metadata.as_dictionary())
        else:
            from rsciio.tofwerk import file_reader

            signal = file_reader(path, **kwargs)[0]
            array = signal["data"]
            metadata = list(signal["metadata"])
        handle = get_file_handle(array) if lazy else None
        try:
            data = array.compute() if lazy else array
        finally:
            if handle is not None:
                handle.close()
        del signal, array
    np.testing.assert_array_equal(data, expected)
    del data
    gc.collect()
    return dict(
        backend=backend,
        lazy=lazy,
        exact=True,
        peak_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        wall_ms=(time.perf_counter() - start) * 1000,
        open_files_after=[
            Path(f.path).name
            for f in psutil.Process().open_files()
            if f.path.endswith(".h5")
        ],
        metadata=metadata,
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file", type=Path, required=True)
    p.add_argument("--channel", type=int, default=0)
    p.add_argument("--backend", choices=["h5py", "rsciio", "hyperspy"], default="h5py")
    p.add_argument("--mode", choices=["eager", "lazy"], default="eager")
    p.add_argument("--compare", action="store_true")
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    if a.compare:
        results = []
        for backend in ["h5py", "rsciio", "hyperspy"]:
            for mode in ["eager"] if backend == "h5py" else ["eager", "lazy"]:
                text = subprocess.check_output(
                    [
                        sys.executable,
                        __file__,
                        "--file",
                        str(a.file),
                        "--channel",
                        str(a.channel),
                        "--backend",
                        backend,
                        "--mode",
                        mode,
                    ],
                    text=True,
                )
                results.append(
                    json.loads(
                        next(
                            line[7:]
                            for line in text.splitlines()
                            if line.startswith("METRIC ")
                        )
                    )
                )
        result = dict(
            versions={
                name: importlib.metadata.version(name)
                for name in ["h5py", "rosettasciio", "hyperspy"]
            },
            runs=results,
        )
        if a.output:
            a.output.mkdir(parents=True, exist_ok=True)
            (a.output / "readers.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
    else:
        print(
            "METRIC "
            + json.dumps(measure(a.file, a.backend, a.mode == "lazy", a.channel))
        )


if __name__ == "__main__":
    main()
