# Scientific reader decision

Select **direct h5py**, retaining the validated NumPy integration. Keep the
repository interface independent of backend selection. Adding a general signal
framework would currently add lifecycle and conversion work without replacing
our exact disjoint integrations, byte admission, locking or source checks.
This is a maintenance choice for this schema, not a claim that higher-level
readers cannot read Tofwerk data.

Reproduce: install h5py 3.16.0, RosettaSciIO 0.15.0, HyperSpy 2.5.0 and psutil
in a disposable environment; run `scripts/evaluate_readers.py FILE`. The frozen
prototype also pins RosettaSciIO git 9959c5679. Compare exact selected frames
and channel with h5py. Synthetic eager/lazy stored values agreed exactly for
all three, including two concurrent independent calls. Serial descriptor counts
returned to baseline when explicitly closing lazy handles; counts sampled
inside concurrent calls fluctuate because descriptors are process-wide.

| Concern | h5py | RosettaSciIO | HyperSpy |
| --- | --- | --- | --- |
| Selective reads | exact integer channel/frame hyperslab | mass/depth filters; exclusive depth stop; lazy Dask graph | same underlying reader plus signal wrapping |
| Numerical behavior | preserved inclusive union/float32 normalization | stored exact; raw defaults uint16 after division, so fractions require explicit float dtype; multi-window peak assignment differs from union | inherits reader behavior |
| Memory | one channel or raw frame, explicit reservations | eager subset; lazy chunking can read more channels than desired; raw range can materialize ragged subset | adds axes/signal/dependency stack and same Dask allocations |
| Metadata | explicit supported schema, calibration absence errors | richer normalized and original metadata, root attributes influence dimensions | convenient signal metadata, unused by renderer-neutral contract |
| Handles | lexical `with`, no analysis-held descriptors | lazy graph retains HDF5 handle; close via public get_file_handle | same handle lifecycle beneath signal |
| Concurrency | bounded workers, per-dataset lock; independent arrays | concurrent equality passes with per-call handles; HDF5 still serializes | no independent concurrency benefit |

Measured small-fixture subset calls including collection: h5py 3–22 ms,
HyperSpy warm eager ~13 ms, lazy ~18–20 ms. These timings include framework
initialization/GC and are not throughput benchmarks. RSS deltas in the script
are allocation observations, not isolated peak measurements. No invented
large-data speed advantage is used in the decision.

The minimal reference fixture initially lacked NbrWrites: the frameworks assumed
one slice and rejected frames 1–2, although PeakData contained three. Adding
realistic NbrWrites exposed the raw-write versus stored-domain difference.
Our repository derives the supported domain from stored shape and never guesses
extra-write alignment. Missing normalization calibration remains an error;
RosettaSciIO defaults some missing fields, unsuitable for our contract.

Sources inspected: [RosettaSciIO Tofwerk API](https://hyperspy.org/rosettasciio/supported_formats/tofwerk.html)
and [HyperSpy lazy data](https://hyperspy.org/hyperspy-doc/v2.5.0/user_guide/big_data.html),
alongside installed `_api.py` and `_reconstruction.py`. The higher-level API's
supported lazy reads retain files; custom union recipes, progress/cancellation
and strict allocation admission would still need direct code. Real acquisition
results are appended in pilot qualification when hydration completes.

Real AlTiPt acquisition, read-only qualification: shape 1301×128×128×217;
raw 1302×128×128; nominal 27 channel 26, normalization 4. Direct full-channel
read/reductions 389.4 ms, 85,262,336 bytes. Four-frame framework eager subset
115.9 ms; Dask lazy subset 4397.5 ms and two simultaneous lazy subsets ~6.8 s
each with explicit native chunks. Stored arrays agreed exactly; direct NumPy
raw versus RosettaSciIO explicit float32 reconstruction agreed exactly. Raw
integration 17.4 ms for four frames. Vendor maximum discrepancy .25, sum
reconstruction minus vendor -3.0 (unchanged semantic difference, not tolerance).
Combined qualification process peak RSS 1,076,740,096 bytes includes all readers
and retained arrays; it does not isolate a per-library peak. Acquisition stat
identity remained unchanged. The fixture runner comparison gave threads
14.3 ms total versus processes 110.4 ms (four selected frames, includes process
startup); retain bounded threads, with service health separately measured.

Fresh isolated real-file subset processes (first four nominal-27 frames, same
native chunks; includes imports/startup): h5py peak RSS 47.9 MB / 14.5 ms;
RosettaSciIO eager 57.9 MB / 139.5 ms, lazy 437.0 MB / 3545.8 ms; HyperSpy eager
74.8 MB / 126.1 ms, lazy 453.0 MB / 3664.2 ms. Each matched the direct stored
values exactly and left no acquisition file open after cleanup. The lazy graphs
have overhead even for a selective result. These are process peak measurements,
not RSS deltas, and strengthen the direct-reader maintenance/resource decision.

Reproduce the isolated process measurements with
`python scripts/evaluate_reader_subset.py --file FILE --channel 26 --compare --output DIR`
in the disposable reader environment. This script selects one mass-table channel,
uses the file's native chunks, captures original metadata categories and explicitly
closes lazy handles. `evaluate_readers.py` is specifically the tiny synthetic
fixture/concurrent probe; `qualify_acquisition.py` checks raw numerical behavior.


Reproduced on 2026-10-19 with the committed runner against the real acquisition
(first four frames, channel 26, isolated processes): h5py 49.4 MB / 25.6 ms,
RosettaSciIO eager 57.7 MB / 127.7 ms and lazy 423.7 MB / 2981 ms, HyperSpy
eager 72.8 MB / 102.9 ms and lazy 433.0 MB / 3421 ms. All five reads matched
the selected stored values exactly and left no HDF5 handle open. The resulting
metadata category lists and raw measurements are in
[scientific-reader-comparison.json](scientific-reader-comparison.json).
The RSS and timing numbers are specific to this Apple Silicon host and include
interpreter/import overhead.

## Full raw-integration performance follow-up, 2026-10-19

The final pilot's per-pixel admission wrapper introduced a real regression that
the earlier four-frame reader evaluation did not cover. Profiling found one
budget reservation, malloc, NumPy view construction and free per spatial pixel:
21,316,887 reservations for a full 1301×128×128 reconstruction, including scratch
and output admission. The frozen prototype uses h5py's native VLEN object-array
read and does not perform these admission callbacks.

The reader now hands HDF5 slices of geometrically growing, prepaid NumPy arenas.
It still uses the public
[VLEN memory-manager API](https://support.hdfgroup.org/documentation/hdf5/latest/_h5_t__u_g.html).
Payload and conservative numerical scratch are reserved before each arena is
allocated. Per-pixel callbacks perform pointer arithmetic; reservations and
NumPy allocations occur per arena. Packed samples plus per-cell offsets and
lengths feed the same inclusive-union calculation. Cumulative-count differences
retain each cell's exact samples even when allocation order differs from spatial
order. HDF5 descriptors and all arenas are released on exit or failure. No native
extension, new dependency, on-disk parser or external API change was added.

A separate sizing read was considered and rejected: HDF5's
[size-query implementation](https://raw.githubusercontent.com/HDFGroup/hdf5/hdf5_1_14_6/src/H5Dint.c)
itself reads variable-length data into temporary allocation, so it is not a
replacement for enforcing admission in the allocator.

Read-only sequential reconstruction of **26.5–27.5 Th, frames 0–1300 inclusive**
on the supplied 2.2 GB `pfib_1301x128x128_AlTiPt.h5`:

| Path | Local elapsed time |
| --- | ---: |
| Frozen Marimo prototype integration | 15.80 s |
| Previous pilot (967e5cb reader) | 69.50 s |
| Pooled pilot reader | 12.69 s |
| Fresh job submission through successful state commit | 11.17 s |

All 21,315,584 float32 values agreed exactly in all four paths. The job reached
1301/1301 and revision 1. Source inode, size and mtime were unchanged. These are
single local observations in the same Python/h5py/NumPy environment; the
prototype measurement executes its frozen integration source without Marimo's UI.
The pilot runs benefit from warm OS caches, and job
timing excludes browser polling and final plot fetch/rendering. They establish
this regression's removal, not a general speed ranking across readers or hosts.

Admission calls fell to 6,514. Managed peak reservations including the 81.3 MiB
output rose from 106.8 to 122.6 MiB because unused arena capacity is prepaid.
These counters are not RSS; prototype scratch was unmanaged and is not comparable.
No memory limit was raised. Tests reject oversized cells before allocating their
payload, release partially allocated reads and caller failures, confirm arena
lifetimes and concurrent independent consumers, and preserve empty/signed and
nonnative integer data. Existing cancellation, fairness and numerical tests pass.

Raw observations are in [integration-performance.json](integration-performance.json).
Reproduce from the implementation checkout using its Python environment:

```sh
python scripts/check_integration_performance.py \
  --file /path/to/pfib_1301x128x128_AlTiPt.h5 \
  --prototype /path/to/frozen-prototype \
  --baseline-ref 967e5cb --frames 1301 --output /tmp/integration-performance.json
```
