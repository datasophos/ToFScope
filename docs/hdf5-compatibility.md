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

File-centered Save as creates an acquisition copy and stores a versioned
`/ToFScope/Analysis/state_json` document and full-resolution custom values under
`/ToFScope/Integrations/<uuid>`. It also attempts to add native vendor peak
channels for renamed stored signals and full-frame custom signals, preserving
all original native peaks. Full-frame disjoint signals are marked `Disjoint:`;
their vendor bounds enclose the gaps and their displayed mass is the midpoint,
while their precomputed values and ToFScope recipes retain the exact intervals.
Partial-frame signals and other unsupported cases remain ToFScope-only and are
listed in the save result. A bounded `native_export_json` report in the analysis
group records exported indices, intervals and warnings. On repeated saves,
original vendor peaks are never removed; older exported peaks can remain and are
reported. This unified workflow has not yet been tested in commercial software.
The document records committed signal relationships and selections; credentials, leases, jobs
and original server paths are excluded. Unknown, incomplete, oversized or corrupt
documents fail explicitly. Custom records are checksum-verified on open, including
hidden results, and restored without raw reintegration. Original files remain
unchanged. Commercial-software round trips for the unified workflow and NFS crash durability remain
unverified; these outputs are supported by ToFScope's own reader.

Integration `recipe_json` uses a bounded one-dimensional uint8 UTF-8 encoding
(maximum 64 KiB), checked before allocation. Restoring an analysis admits its
combined embedded recipe decoding scratch in addition to state JSON and frame
scratch. Unsupported earlier experimental encodings are rejected explicitly.


## Saved-copy observation (2026-10-28)

Josh confirmed that a ToFScope saved analysis copy opens in TOFexplorer Viewer
mode. The copied acquisition's original labeled and nominal peaks appear in its
peak selector. The saved analysis names `Al 27`, `Ti 48`, and `Fe(?) 54` do not
appear as labeled peaks in TOFexplorer. Read-only inspection shows that those
three ToFScope signals refer to existing nominal peak-table indices 26, 47, and
53; their names are stored in `/ToFScope/Analysis/state_json`. The vendor peak
table still contains the nominal labels and its existing `[194Pt]` label.
This observation establishes that the copy opens, not that TOFexplorer reads
ToFScope analysis names or that numerical values agree across applications.

A second saved analysis copy, observed by Josh in TOFexplorer on 2026-10-28,
contains the custom signal `48 + 56 + 64`, which also does not appear in its
labeled peaks. Read-only inspection shows its full-resolution float32 result
under `/ToFScope/Integrations` and its three disjoint mass intervals in the
ToFScope analysis document; the native peak cube and table still have 217
channels and only the existing `[194Pt]` non-nominal label. The current native
exporter rejects disjoint intervals, because one vendor peak-table lower/upper
bound cannot faithfully represent the gaps. The screenshot and file inspection
do not establish numerical agreement or whether a different vendor representation
could support this recipe.

Josh also opened a third saved analysis copy in TOFexplorer on 2026-10-28.
Its custom `Wide 27` signal spans one continuous interval, approximately
23.5275–34.1502 Th, over frames 0–1300. It did not appear in the vendor peak
list. Read-only inspection confirms the full-resolution result is stored in
`/ToFScope/Integrations` and the native peak cube and table remain at 217
channels, with `[194Pt]` as the only non-nominal label. A continuous interval
alone does not cause Save as to create a vendor peak; native export has other
validation requirements and is a separate workflow.

## Disjoint native-channel experiment (2026-10-28)

A disposable copy of the saved `48 + 56 + 64` analysis was constructed with
one additional native peak channel containing the exact precomputed disjoint
signal. All added frames matched the saved ToFScope result; the original peak
table and three original frames matched, and the source file identity was
unchanged. TOFexplorer Viewer mode 2.9.7+3484e0dd displayed the
`DISJOINT_TEST_48_56_64` entry under Labelled Peaks, and Josh's screenshots show
its top and front projections and depth profile.

The native peak table in this experiment used the outermost mass bounds and
their midpoint (displayed as 57.023 Th). Those bounds include gaps that were
not integrated: they are not an accurate description of the channel. The
ToFScope integration metadata retains the real three intervals. These observations
show that TOFexplorer can display this precomputed channel, not that it understands
the disjoint recipe, would preserve it after editing, or produces numerically
identical measurements. The artifact is an experiment, not a validated export.

## Saved spatial views (analysis document version 4)

Save as writes schema 4 with validated named-signal references for 3D layers,
visibility/Solo, colormaps, opacity, percentile, quality, layout/page, numerical
scale, linked/independent cameras, frame stretch and calibrated exaggeration.
Opening a saved copy remaps spatial references to the restored signal IDs.
Older schemas 1–3 default to Explore with no configured spatial layers. The
preview arrays are disposable display products and are not stored as scientific
results; saved custom arrays and original-resolution calculations are unchanged.
This does not implement native acquisition write-back.
