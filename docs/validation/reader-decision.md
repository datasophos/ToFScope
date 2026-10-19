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
