# Prototype reference, 2026-10-18

Frozen commit: `37ecacf24c32388cd7f84bc11fa509989cc44775`.
Detached checkout: `/private/tmp/tofscope-prototype-37ecacf` (retain it; can
recreate with `git worktree add --detach PATH 37ecacf`). Its own environment:
`uv sync --frozen`; lock SHA256
`08c7af7a1379e28953f7cadfa030b68be3d816ff260b30d4dca7bb0c9bb848f2`.
Launch: `.venv/bin/marimo run app.py --headless --host 127.0.0.1 --port 27991`.
Python 3.12.3, NumPy 2.5.4, h5py 3.16.0, Marimo 0.25.1.
Reference numerical/controller suite: **87 passed**, 4.407 seconds.
The sandbox blocked local socket binding and Marimo's state directory; a launch
with OS approval started the server. HTTP/browser verification is recorded in
pilot qualification when completed.

Synthetic fixture: three stored frames, four raw writes, two channels, inclusive
mass bins 0–5, two active channels × two waveforms. Disjoint [1,2] ∪ [4,5]
produces exactly `[[1,.25],[1,.5],[1,.75]]`; overlap is counted once. ROI
[2,6,8,4] on a 128² field of 20 µm gives [13,37,26,50]. SE includes a short image.
`capture_reference.py` saves canonical NPZ and timing manifest outside git.
Warm synthetic h5py metadata/channel/profile/front capture: p50 .507 ms,
p95 .845 ms, peak RSS 50,348,032 bytes, NPZ 1,418 bytes (20 repetitions).
These are small-fixture server measurements, not acquisition/browser claims.

Pilot acceptance thresholds: health p95 <250 ms while integration runs;
interactive completed selections p95 <500 ms on this machine; display response
≤32 MiB; no full 4-D acquisition response. Real acquisition thresholds require
measurements, not extrapolation from this fixture. Exact equality is required
for unchanged integer selections/float32 integration; float64 sums/means use
1e-12 relative comparison only if reduction order changes (roundoff, not vendor
agreement). Real paths provided later are read-only and may still be hydrating.
