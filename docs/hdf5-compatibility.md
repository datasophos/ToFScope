# HDF5 write-back status

Commercial TOFexplorer **reading and visualization passed for one representative
native addition**, as reported by Josh on 2026-10-18 in Viewer mode,
version **2.9.7+3484e0dd**. This is limited evidence, not general compatibility
certification. Exact numerical agreement and an end-to-end save through the
ToFScope UI remain unverified. The application's experimental write gates and
conservative “unverified” status remain in place pending those checks.

## Commercial observations (2026-10-18)

Test artifact: `tofscope-native-validation.h5`, prepared as described below.
The source acquisition was not modified.

- The file opens and the added `ToFScope_Al_26p8_27p2` channel is selectable.
- Its peak-table bounds display as 26.799999–27.200001 Th, consistent with
  native float32 representation of 26.8–27.2 Th.
- The added channel renders top/front projections and a structured depth
  profile. An original `[194Pt]` channel also renders.
- Josh confirms FIB SE images work and closing/reopening appears normal.

The initial empty depth-profile panel subsequently displayed the added
channel's curve; no write-back defect was established by that initial state.
Screenshots and user observations establish display behavior, not an exact
cross-application numerical comparison. Commercial editing/resaving has not
been tested. RosettaSciIO round-trip checks below are separate evidence.

## What has been checked

The AlTiPt example was copied to `/private/tmp/tofscope-native-validation.h5`.
The copy contains an added `ToFScope_Al_26p8_27p2` native peak spanning
26.8–27.2 Th, frames 0–1300. Existing compressed peak chunks were compared
byte-for-byte; the new channel matches reconstructed full-resolution values.
The official RosettaSciIO reader at commit
`9959c56799693418182d3c175c7261a3d7f9f1b8` reads the addition correctly.
The source SHA256 remained
`914fd248ced472358e47c7180733f2715998d957ac3c384c11d42f1cd6938c8d`.
The report is `/private/tmp/tofscope-native-validation.json`; temporary files
are not durable project artifacts. Recreate a new copy using
`scripts/prepare_native_validation.py --output /path/to/new-copy.h5`.

Synthetic tests cover native and ToFScope round trips, sparse gzip chunks,
original channels, backup retention, failure before replacement, stale sessions,
separate-process locks, post-publication errors and source path confinement.
No supplied client acquisition was modified during development.

## Eligible native additions

Experimental native saves currently require one contiguous mass interval,
every acquisition frame, full XY float32 scientific values, and a nonempty
ASCII label shorter than the vendor fixed-width label field. Native float32
integration bounds must select exactly the same calibrated mass bins as the
requested bounds. Disjoint and partial-frame recipes are rejected for native
saves; neither bounding windows nor zero padding would preserve their meaning.
Those recipes remain usable for exploration and JSON exports. The independent
ToFScope schema and reader can represent disjoint or partial saved records.

The source peak cube and table are fixed-size. Saves therefore rebuild larger
native datasets in a sibling temporary file, preserving original peak rows,
channels, metadata and other groups, and updating the peak counter together.
The `/ToFScope/Integrations/<uuid>` extension retains the exact derivation,
full-resolution data, source identity, normalization convention and calibration.
Labels are metadata, never HDF5 path components. Unsupported link/reference
layouts are rejected. The full multi-ion cube is never expanded in memory.

## Deployment and recovery

The default is read only. Experimental saves require **both**
`TOFSCOPE_ALLOW_WRITES=true` and `TOFSCOPE_ALLOW_UNVERIFIED_NATIVE=true`.
Enabling the latter acknowledges experimental access; it does not change the
scope of commercial validation. Use disposable acquisitions first.

Use a trusted, administrator-owned POSIX data root. Read and write operations
use adjacent hidden `.filename.tofscope.lock` files, so the service needs
permission to create those files (or appropriate pre-created lock files).
Do not remove a lock file while servers are running. Locks coordinate
cooperating ToFScope processes; they do not prevent an acquisition program or
other software from writing the file. Keep acquisitions closed in those programs
during saves. HDF5's own file locking remains enabled.

Before enabling writes on a deployment mount, run:

```sh
uv run python scripts/probe_storage.py /configured/data/root
```

This checks separate-process exclusion, same-directory replacement and fsync
using only its own temporary directory. It does not establish cross-host NFS
lock behavior or crash durability. For multiple server hosts, also verify that
a lock held on one host blocks acquisition of that same lock on another host.
Do not enable multi-host writes without that deployment check.

Saving retains a uniquely named hidden `.bak` beside the acquisition and builds
a hidden `.tmp.h5` copy. Free-space preflight reserves two source sizes, two
uncompressed derived volumes, and a 64 MiB margin. The final file contains the
derived channel twice (native and extension). A failure before replacement leaves
the original path untouched and identifies recovery paths. A successful atomic
replacement reports saved even if later cache clearing or reload fails.
Backups and failed prepared copies are retained for manual recovery; there is
no automatic backup pruning. Original permission bits are preserved. ACLs and
ownership beyond the writing service's POSIX ownership are not guaranteed;
hard-linked acquisition files are rejected.

File identities include inode, size, mtime and a generation UUID. A session
whose source has changed must reload before another analysis operation or save.
Settings JSON can be exported first to retain the old analysis recipe. These
checks cannot guarantee safety against a non-cooperating writer racing the
final identity check, or administrator changes to the trusted directory tree.

## Remaining commercial checks

- Compare numerical values for matching frames, ROIs and aggregation between
  ToFScope and TOFexplorer. Visual structure alone is not numerical agreement.
- Save a fresh contiguous, full-acquisition integration through the ToFScope UI
  on a separate disposable acquisition, then open it in commercial TOFexplorer.
  Check the new channel, original channels, SE images, and reopening. This tests
  the UI publication workflow in addition to the native-copy exporter already
  exercised by the representative artifact.
- Broader metadata behavior and commercial editing/resaving remain untested.

eXSpy itself has not been exercised here.

## Review follow-up

The final review's reference-dtype, external-dependency, exporter-locking and
transactional saved-selection findings have regression coverage. Immediate
post-save active-layer export consistency is also checked. Further malformed
saved-metadata cases and an independent comparison of a representative unknown
vendor metadata tree remain useful test improvements; the current verification
does not claim exhaustive coverage of every vendor metadata field.

## Saved analysis copies

File-centered Save as creates a byte-preserving acquisition copy, then writes a
version-1 `/ToFScope/Analysis/state_json` uint8 document and full-resolution custom
values under `/ToFScope/Integrations/<uuid>`. It does not rebuild vendor PeakData
or flatten disjoint/partial integrations into native vendor channels. The document
records committed signal relationships and selections; credentials, leases, jobs
and original server paths are excluded. Unknown, incomplete, oversized or corrupt
documents fail explicitly. Custom records are checksum-verified on open, including
hidden results, and restored without raw reintegration. Original files remain
unchanged. Vendor/commercial-software round trips and NFS crash durability remain
unverified; these outputs are supported by ToFScope's own reader.
