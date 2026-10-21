# Compact raw preparation

New raw preparations copy live HDF5 objects into a fresh file instead of copying
unused source-file space. Reconstructed float32 PeakData uses gzip level 1,
no shuffle, and `(1, ny, nx, 1)` chunks: one channel image per frame, matching
the TOFexplorer baseline's layout. This changes storage and access cost only;
integration and normalization are unchanged. Existing files are not rewritten.

Full-dataset qualification used the 1,301-frame, 128 × 128, 216-channel raw
AlTiPt acquisition and the earlier LZF ToFScope preparation. Both outputs were
created in disposable directories. Every reconstructed value matched exactly;
every raw event cell, including the spare uncompleted frame, was checked.
The source SHA-256 remained unchanged and the result reopened normally.
The machine-readable measurements are in `compact-raw-preparation.json`.

The final full run took 105.93 seconds versus the earlier 84.45-second LZF
preparation. File size fell from 2,483,743,396 to 2,205,777,623 bytes, a reduction
of about 278 MB (11.2%). Three complete single-channel reads with fresh HDF5
handles took 0.259/0.099/0.099 seconds, versus 3.336/2.925/2.925 seconds for LZF.
These are local warm-cache observations, not cold-storage guarantees. Sampled
preparation RSS peaked at 390 MB; managed payload peaked at 121 MB.

Raw events are copied through the admitted VLEN reader and a public HDF5 VLEN
writer using existing sample buffers. Numerical datasets retain their original
filters and values. Internal hard aliases, soft links, object references and
region references are preserved; references are remapped after objects exist.
Cancellation, quota failures and copy errors remove the private temporary file
and never publish a partial result. Original acquisitions remain read-only.

Metadata strings use an admitted fixed-size destination buffer and a 1 MiB
per-string limit; ambiguous truncation is rejected. Unsupported nonstring VLEN
metadata (including VLEN dimension-reference lists) is rejected rather than
silently altered. HDF5 attribute reads lack the public dataset allocator hook:
HDF5 may temporarily materialize a full VLEN string before fixed-size conversion.
Consequently the managed Python-payload budget is not a strict process-RSS cap.
Native HDF5 caches/conversion buffers also contribute to RSS.

Regression coverage includes deleted source space, channel chunk/filter settings,
raw event aliases and exact payloads, object/region/compound/array references,
Unicode attributes, oversized metadata rejection, and cancellation cleanup.
All 167 Python tests and 44 browser workflows passed. Independently installed
wheel and source distributions passed the offline browser, raw preparation,
save/restart/reopen, integration and export checks without Node or RosettaSciIO.
Docker qualification could not run because the local Docker daemon was stopped.

The local service was restarted with this implementation on port 8765; readiness,
health and the raw-preparation API schema returned HTTP 200.
