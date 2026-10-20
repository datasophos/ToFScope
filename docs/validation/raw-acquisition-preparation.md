# Raw TOFexplorer preparation — 2026-10-20

Raw acquisitions retain PeakTable, MassAxis, SumSpectrum and EventList but may
lack PeakData. Opening now performs read-only inspection. The app asks before
preparing a named new copy in the Saved files folder. It reconstructs every
original table channel for completed writes, with progress/cancel, then opens the
prepared copy through the usual Explore API. Original acquisitions are unchanged.
Prepared files retain the raw events and metadata, so custom integrations and
saved-analysis copies continue to work. TOFexplorer-generated additional channels
absent from the raw table are not invented.

## Scientific method

Reviewed the installed RosettaSciIO 0.15.0 `tofwerk/_api.py` and
`_reconstruction.py`, plus the [upstream reader documentation](https://rosettasciio.readthedocs.io/en/latest/supported_formats/tofwerk.html).
Use integer TDC-to-sample conversion, the stored calibrated mass axis, and
normalization by waveforms × active recording channels. Retain float32 fractional
intensities; RosettaSciIO's default uint16 conversion can truncate them. The
reference comparison explicitly requests float32. Each integration window has
inclusive endpoints; overlaps independently count events in each applicable
channel. Unlike RosettaSciIO's single-bin searchsorted assignment, overlapping
windows are preserved. Nonoverlapping groups allow vectorized counting without
reading events once per peak. The runtime still needs only h5py/NumPy, not
RosettaSciIO, HyperSpy or Node. Reader and renderer details stay behind the API.

## Real acquisitions

- Small raw file `pfib-tofwerk raw.h5`: all 10×64×64×259 values exactly match
  RosettaSciIO float32 reconstruction. Preparation took 0.182 seconds, producing
  4,824,710 bytes; the prepared file reopened normally. Original checksum unchanged.
- Its TOFexplorer processed sibling is **not bit-identical**: 50 of 10,608,640
  values differ, maximum absolute difference 0.25. Both files have identical
  mass axes, peak tables, timing calibration and the inspected raw events.
  Inspected mismatches occur near window boundaries. This establishes a measured
  vendor integration edge difference, not its exact proprietary implementation.
  We retain the documented calibrated-bin rule shared with existing custom
  integration and RosettaSciIO, rather than silently changing boundaries to fit
  these examples. Commercial vendor equivalence is not claimed.
- Large raw file `pfib_1301x128x128_AlTiPt_raw.h5`: fully reconstructed and verified
  1301×128×128×216 values in 84.45 seconds. Losslessly compressed output:
  2,483,743,409 bytes. All channel values at frames 0, 650 and 1300 exactly match
  RosettaSciIO float32. The 1302nd EventList slot is excluded because NbrWrites
  reports only 1301 completed frames. The processed sibling has 217 channels;
  that later additional channel is absent from this raw table.
- The large source SHA-256 remained
  `695d82ceff8d769ac2e38d18aa5be24898a15581ce293d059a916662485061c4`.
  Sampled peak RSS was 246,890,496 bytes and managed allocation 121,569,536 bytes.
  These are sampled maxima, not continuous high-water measurements.
- Real-file outputs were created in disposable temporary directories, reopened,
  checked, then removed. Original files were only read.

## Lifecycle and limits

Preparation shares the round-robin owner queue and its global/user limits with
integration and saves. Jobs/results are owner scoped. Source generation is bound
to confirmation and checked during copying/integration/verification. Budget
metadata before decoding, raw events with the bounded allocator, and all frame
and histogram scratch; no whole-volume allocation. Write chunked LZF PeakData,
verify every written frame against a running checksum and preserve PeakTable.
Reserve source-copy plus frame disk headroom and recheck during compressed growth;
reserving all ~17 GiB uncompressed would unnecessarily block the real file on this
machine's ~12 GiB free disk. Failure, cancellation and low space clean temporary
files. Exclusive publication never overwrites originals or existing saved files.
All generation contexts exit before publication, so a later source change cannot
turn a committed copy into a reported failure. Failed automatic opening leaves
the completed saved copy available for retry.

Missing peak tables, mass axes, event lists, timing/channel normalization or
completed-frame metadata are rejected; no uncalibrated windows are invented.
Preparation uses cooperative source locking. Reloading the page does not cancel
a queued job; a completed copy remains in Saved files. NFS locking, power-loss
durability and a commercial TOFexplorer roundtrip remain unqualified.
