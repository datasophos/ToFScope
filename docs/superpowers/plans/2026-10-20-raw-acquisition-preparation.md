# Raw TOFexplorer acquisition preparation

Inline execution extends the approved packaged Explore pilot. Original acquisitions
remain read only; preparation is an explicit, cancellable operation on a new copy.

## Evidence and decisions

- Inspected RosettaSciIO 0.15.0's installed `tofwerk/_api.py` and
  `_reconstruction.py`, and the upstream TOFWERK reader documentation:
  https://rosettasciio.readthedocs.io/en/latest/supported_formats/tofwerk.html
- Both supplied raw files retain PeakTable, MassAxis, SumSpectrum and EventList,
  but lack PeakData. The small pair has 10×64×64 pixels and 259 channels.
  The large raw file has 216 table entries, 1302 event slots, and NbrWrites=1301;
  its processed sibling has 217 channels (including a later added channel).
  Reconstruct only the raw table, in its original order, for completed writes.
  Do not invent the processed sibling's extra channel or include spare slots.
- Follow the timestamp integer division and waveform×active-channel normalization.
  Use float32, avoiding RosettaSciIO's default uint16 fractional truncation.
  Its single-window searchsorted assignment does not preserve overlapping peaks;
  preserve inclusive per-window semantics, including shared endpoints, and compare
  disjoint channels to RosettaSciIO with explicit float32 plus independent overlap
  references. Group disjoint windows for vectorized, one-pass-per-group counting.
- Retain bounded h5py event reads and the existing resource budget. Do not add
  RosettaSciIO or HyperSpy runtime dependencies or couple the API to a reader.
- Materialize all table channels to chunked, losslessly compressed PeakData in a
  new owner-scoped saved copy. Preserve other source contents and source metadata;
  update NbrPeaks to the actual table length and record preparation provenance.
  Reserve source-copy and worst-case frame disk headroom before starting, and
  recheck/reserve headroom before each compressed frame write. Whole-volume
  uncompressed reservation was rejected: the large output would be ~17 GiB
  uncompressed while this machine has ~12 GiB free. Stop and clean up if
  compressed growth exhausts the available headroom. Copy with
  bounded memory; integrate and write one frame at a time. Verify numerical
  content/checksums before exclusive publication. Never overwrite any existing file.

## Work

1. Add failing numerical, preparation/lifecycle and browser confirmation tests.
2. Add read-only inspection/preflight reporting generation, dimensions, channels,
   preparation requirement, suggested filename and conservative space estimate.
3. Reuse the fair owner job scheduler for preparation; enforce existing global,
   user, memory and job limits, cancellation and source-generation checks.
4. Confirm in the file explorer before copying/integration, with editable output
   name, folder tooltip, progress/cancel and clear failure/retry. Open only after
   success; cancellation/failure preserves current analyses and source.
5. Verify disposable fixtures, RosettaSciIO parity and the actual small raw pair;
   qualify the large raw file when locally accessible. Distinguish blocked checks.
6. Regenerate schema/assets, package and document launch/limitations; coherent commits.

## Completion

Steps 1–6 implemented. Full-volume large-file preparation, verification/reopening
and first/middle/last frame RosettaSciIO comparisons passed; the raw source hash
was unchanged. All small-file channels matched RosettaSciIO; 50 vendor-edge
mismatches are explicitly recorded in `docs/validation/raw-acquisition-preparation.md`.
The final review's disk double-counting and retained-buffer findings were fixed
and regression-checked. Validation includes 156 Python tests, 42 browser workflows,
11 frontend unit tests, wheel/sdist offline installs and non-root Docker checks.
Activation of the local service requires a restart; open unsaved analyses must
be saved/discarded before that restart. No acquisition writes or external deploys.

Local activation completed after explicit restart approval. The subsequent
preparation action-height correction is live via refreshed bundled frontend assets.
