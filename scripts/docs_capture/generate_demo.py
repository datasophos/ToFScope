"""Generate the fixed, synthetic MOSFET-like documentation acquisition.

The output is an illustration, not an instrument measurement.  Elemental
distributions are deliberately simplified to make layers and features clear.
"""

from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / ".demo-data" / "mosfet-demo.h5"
SIZE = 128
SEED = 28


def generate(path=DEMO):
    """Write the reproducible 128-frame synthetic acquisition to *path*."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    y, x = np.mgrid[:SIZE, :SIZE]
    # Contact pads, narrow gate, and doped source/drain regions.
    gate = (abs(x - 64) < 9) & (y > 18) & (y < 110)
    source = (x > 12) & (x < 52) & (y > 25) & (y < 103)
    drain = (x > 76) & (x < 116) & (y > 25) & (y < 103)
    contacts = ((x > 15) & (x < 48) | (x > 80) & (x < 113)) & (y > 35) & (y < 93)
    axis = np.linspace(0, 200, 4096, dtype="f8")
    masses = np.array([26.9815, 27.9769, 47.9479, 30.9738])
    labels = ("Al", "Si", "Ti", "P")
    peak_bins = np.searchsorted(axis, masses)
    counts = np.empty((SIZE, SIZE, SIZE, len(labels)), dtype="f4")
    spectrum = np.zeros(len(axis), dtype="u8")
    with h5py.File(path, "w") as f:
        f.attrs["TofDAQ Version"] = "synthetic demo"
        f.attrs["NbrWrites"] = SIZE
        f.attrs["NbrSegments"] = SIZE
        f.attrs["NbrWaveforms"] = 1
        f.attrs["Configuration File Contents"] = "Ch1Record=1"
        f.create_group("TimingData")
        f.create_group("AcquisitionLog")
        full = f.create_group("FullSpectra")
        full.attrs["SampleInterval"] = 1.0
        full.attrs["ClockPeriod"] = 1.0
        full.create_dataset("MassAxis", data=axis)
        raw = full.create_dataset(
            "EventList",
            (SIZE, SIZE, SIZE),
            dtype=h5py.vlen_dtype(np.dtype("u4")),
            chunks=(1, SIZE, SIZE),
            compression="gzip",
        )
        for z in range(SIZE):
            # Top metallization, gate oxide, and silicon substrate/doped pockets.
            al = 0.02 + 0.9 * contacts * (z < 26) + 0.65 * gate * (z < 18)
            si = 0.04 + 0.6 * (z >= 42) + 0.15 * (z >= 25)
            ti = 0.02 + 0.65 * (gate | contacts) * (18 <= z < 34)
            phosphorus = 0.01 + 0.45 * (source | drain) * (42 <= z < 85)
            means = np.stack(np.broadcast_arrays(al, si, ti, phosphorus), axis=-1)
            frame_counts = rng.poisson(means).astype("u4")
            counts[z] = frame_counts
            # Each event is a native mass-axis bin. Spread it over nearby bins.
            cell_counts = frame_counts.reshape(-1, len(labels))
            background = rng.poisson(0.45, SIZE * SIZE)
            # Smaller molecular and isotope peaks make the overview spectrum
            # resemble an acquisition while retaining the spatial channels above.
            extra_masses = np.array(
                [
                    12,
                    16,
                    18,
                    23,
                    29,
                    39,
                    41,
                    55,
                    56,
                    69,
                    70,
                    71,
                    85,
                    87,
                    103,
                    107,
                    127,
                    133,
                    134,
                    135,
                    137,
                    138,
                    151,
                    185,
                ]
            )
            extra_weights = np.array(
                [
                    2,
                    5,
                    2,
                    3,
                    3,
                    2,
                    1,
                    4,
                    1,
                    6,
                    9,
                    4,
                    5,
                    3,
                    2,
                    4,
                    2,
                    6,
                    8,
                    4,
                    2,
                    1,
                    1,
                    1,
                ],
                dtype=float,
            )
            extra_weights /= extra_weights.sum()
            extra_counts = rng.poisson(0.12, SIZE * SIZE)
            cells = np.empty(SIZE * SIZE, dtype=object)
            for i, values in enumerate(cell_counts):
                bins = np.repeat(peak_bins, values)
                if bins.size:
                    bins = np.clip(
                        bins
                        + np.clip(np.rint(rng.normal(0, 1.1, bins.size)), -3, 3).astype(
                            int
                        ),
                        0,
                        len(axis) - 1,
                    )
                if background[i]:
                    noise = rng.integers(0, len(axis), background[i])
                    noise_masses = axis[noise]
                    counts[z, i // SIZE, i % SIZE] += np.count_nonzero(
                        np.abs(noise_masses[:, None] - masses) <= 0.20, axis=0
                    )
                    bins = np.concatenate((bins, noise))
                if extra_counts[i]:
                    centers = rng.choice(extra_masses, extra_counts[i], p=extra_weights)
                    # Narrow peaks with a weak, asymmetric instrumental tail.
                    offsets = rng.normal(0, 0.06, extra_counts[i]) + rng.exponential(
                        0.12, extra_counts[i]
                    )
                    extra_bins = np.searchsorted(axis, centers + offsets).clip(
                        0, len(axis) - 1
                    )
                    counts[z, i // SIZE, i % SIZE] += np.count_nonzero(
                        np.abs(axis[extra_bins, None] - masses) <= 0.20, axis=0
                    )
                    bins = np.concatenate((bins, extra_bins))
                if bins.size:
                    np.add.at(spectrum, bins, 1)
                cells[i] = bins.astype("u4")
            raw[z] = cells.reshape(SIZE, SIZE)
        full.create_dataset(
            "SumSpectrum", data=spectrum.astype("f4"), compression="gzip"
        )
        peak = f.create_group("PeakData")
        peak.create_dataset("PeakData", data=counts, compression="gzip", shuffle=True)
        dtype = np.dtype(
            [
                ("label", "S64"),
                ("mass", "f4"),
                ("lower integration limit", "f4"),
                ("upper integration limit", "f4"),
            ]
        )
        peak.create_dataset(
            "PeakTable",
            data=np.array(
                [
                    (label.encode(), mass, mass - 0.20, mass + 0.20)
                    for label, mass in zip(labels, masses)
                ],
                dtype=dtype,
            ),
        )
        f.create_group("FIBParams").attrs["ViewField"] = 0.02
        # A deterministic grayscale image aligned with the synthetic device.
        image = 25 + 75 * gate + 45 * contacts + 12 * np.sin(x / 6) * np.cos(y / 9)
        f.create_dataset(
            "FIBImages/Image0000/Data", data=image.astype("f4"), compression="gzip"
        )
        f.attrs["Synthetic demo"] = "Illustrative MOSFET-like layers; not measured data"
    return path


if __name__ == "__main__":
    temporary = DEMO.with_suffix(".partial")
    try:
        generate(temporary)
        temporary.replace(DEMO)
        print(DEMO)
    finally:
        temporary.unlink(missing_ok=True)
