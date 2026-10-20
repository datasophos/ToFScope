# File-centered analysis qualification — 2026-10-19

This supersedes the earlier pilot report's workspace/reconnect and restart-loss limitations for explicitly saved analyses. Unsaved analyses remain temporary. No release was published, external service deployed, or original acquisition modified.

## Passed checks

- 140 Python tests; 11 frontend unit tests; TypeScript typecheck; 32 Playwright workflows. These cover owner separation, independent file tabs, save/edit/close/cancel races, quota admission, corrupt metadata, filename collisions, hidden signals, union windows, partial coverage, exact restored profiles, explicit download, and dirty-state decisions.
- Production frontend build and fresh wheel/sdist builds. Both independently installed packages run with no Node.js in runtime PATH, no Marimo/AnyWidget/RosettaSciIO runtime dependency, and no external browser requests.
- Each installed package saved custom/hidden signals and display settings, restarted, removed its disposable original acquisition, reopened the saved copy, and produced exactly the original CSV. Saving did not initiate a download. Explicit download worked; disconnecting a download preserved the server file.
- Docker 29.7.2: local image build and readiness/plots, UID 10001, read-only root filesystem and acquisition bind mount, writable runtime/output mounts, one port. Saving and reopening a copy passed inside the container. Smoke output storage uses tmpfs; production needs a persistent output volume.
- Frozen prototype checkout remains clean at `/private/tmp/tofscope-prototype-37ecacf`.

## Real acquisition

The read-only qualification uses `pfib_1301x128x128_AlTiPt.h5`, 2,207,119,636 bytes, 1301 × 128 × 128 × 217. The original inode, size, mtime and SHA-256 remain unchanged. The generated copy is temporary and is moved to a new root, opened by a fresh service and owner, then removed with the qualification scratch directory.

Vendor group/dataset attributes, dataset layout, contiguous values and all allocated chunk payloads compare exactly. Full-resolution custom union values and ROI CSV compare exactly after reopening, with raw integration patched to fail if called. Hidden signals, ROI, display settings and saved revision restore correctly. Machine-readable measurements are in [file-centered-analysis-qualification.json](file-centered-analysis-qualification.json).

The browser check on the same acquisition reported no errors or external requests. Image maximize/restore took 21.6–33.8 ms; four frame steps had p50 268 ms and p95 331 ms. Initial four-panel loading took 3.22 s and a resident stored-signal switch 577 ms, with no raw integration or spectrum refetch. This run overlapped the content-verification workload, so it is not a clean-machine latency comparison. The picker contained 217 options within a 200-pixel list.

An extended run completed independent-owner reads, save and cancellation assertions, then failed reopening the ProtonDrive-backed original with macOS read timeout 60. Its retry stalled during the initial source hash and was interrupted. Therefore the combined extended real-data owner/cancellation/memory run is **blocked**, not passed; no high-water result is claimed. Owner/cancellation/admission behavior passes the deterministic automated tests. The earlier complete real-data preservation result above remains valid. It preceded final metadata-encoding and publication hardening; scientific calculations were unchanged, and the final encoding/restoration path was requalified using disposable package fixtures.

## Limits and operation

Use one service process. Keep acquisitions read only and configure a persistent output root:

```sh
tofscope --data-root /path/to/acquisitions --output-root /path/to/saved-analyses
```

Saving needs space for a complete acquisition copy plus custom volumes and verification overhead. It creates a new filename and never replaces an existing file. Browser download is optional and can take a long time. Saved files restore committed state; pending drafts/calculations must be resolved first.

NFS locking/publication and power-loss durability, commercial-software round trips, acquisition hardware and multi-host/multi-worker operation remain unverified. The raw-only example lacks the required stored PeakData and remains unsupported. Managed-memory measurements exclude Python/HDF5 allocator overhead and browser memory. Existing original-write denial remains in force; creating new copies does not enable commercial-native acquisition writes. Calibration, identification and 3D remain future features under the completion plan.

## Execution decisions

The plan was approved in Plannotator with no annotations after incorporating optional-download feedback. Implementation decisions and review outcomes are recorded below; numerical/owner boundaries remain independent of renderer and reader choices.

## Final review and fixes — 2026-10-20

The most-capable reviewer exhausted its usage allowance after confirming two
findings. A fresh gpt-6.1-sol high review completed the feature review and found
four material issues, all fixed in one pass with observed failing and passing
regressions. There were no deferred minor findings.

- Stale close requests now require a revision and validate it atomically. A
  browser tab cannot discard a newer committed revision from another view.
- Integration recipe metadata now uses bounded uint8 UTF-8 storage and decoding
  admission; scalar variable-length encodings fail before allocation. Combined
  recipe scratch is reserved when restoring, and result-cache reads admit their
  metadata separately.
- Copying reuses one admitted buffer. A 24-MiB fixture regression measured the
  former 16.8-MB Python peak and now enforces the one-buffer envelope.
- The saved-file descriptor is captured before exclusive publication; subsequent
  private temporary-file cleanup failure logs a warning without overturning a
  completed save. Such an exceptional failure can leave a hidden temporary file
  requiring operator cleanup, while the completed file remains usable.

Final checks: 140 Python tests, 11 frontend unit tests, TypeScript typecheck and
32 browser workflows passed. Frontend assets and wheel/sdist were rebuilt after
these fixes; package and container results below refer to those final artifacts.

### Execution rulings, in order

- Ruling: document JSON is a bounded uint8 dataset (1 MiB maximum), not a variable-length HDF5 string — permits rejecting malicious oversized metadata before allocating it — old unsupported document encodings are intentionally rejected.
- Ruling: before_publish may return a context manager held across final validation and exclusive link creation — closes the edit/publication race without holding the analysis lock during copying — callers must validate after acquiring the lock, not before returning the guard.
- Ruling: saved IDs encode confined leaf filenames; owner hash directories provide separation and restart persistence without a database — IDs are opaque API identifiers, never authorization — renaming an output externally invalidates its old ID.
- Ruling: source document validation reserves decoded JSON/single-frame scratch based on bounded metadata size, skipping reservation for ordinary acquisitions — preserves small configured budgets and avoids an unnecessary fixed 16-MiB cost — unknown JSON shapes are rejected before allocation.
- Ruling: output roots are created lazily by owner access, not on service construction — avoids unintended directories on unrelated service/tests/doctor startup — saved-file listing creates the configured private directory.
- Ruling: add snapshot.saved_revision now (persisted document sets it to initial revision, successful publish sets captured revision without scientific revision increment) — dirty state must survive same-owner browser reload rather than relying on a client-only map — publication guard updates this under the same analysis lock.
- Ruling: test fixture analyses_global increased to 128; production remains 32 — whole browser suite creates independent owners whose disconnected analyses correctly remain recoverable until idle expiry; new saved-file workflows exceeded shared fixture capacity — quota behavior remains directly tested in Python.
- Ruling: settings JSON remains a diagnostic API, removed from primary UI; browser export regression now uses Profile CSV — saved HDF5 is the restoration mechanism, as approved — external scripts using the removed UI button must adopt the new workflow in Task 7.
- Ruling: final review covers feature base 7c15baa through final persistence commits — earlier pilot changes already received a full review and are historical context — unrelated earlier pilot findings are not re-reviewed.
- Final: Ruling: most-capable reviewer hit its usage limit mid-review — used a fresh gpt-6.1-sol high reviewer to finish the single whole-feature review, carrying confirmed findings — less capable review model is the qualification limit.
- Final: Ruling: earlier pilot behavior remains outside this feature review — it already had its own review and qualifications — pre-existing defects outside this change may remain.
- Final: Ruling: NFS/native-commercial compatibility and power-loss guarantees remain unqualified — no matching mount/software/hardware was available and those guarantees are not asserted — deployments need separate qualification.
- Final: Ruling: extended real-source high-water run remains blocked — CloudStorage timed out, so deterministic owner/cancel/admission tests plus the earlier full data-preservation result are the evidence — complete real-source high-water behavior is not established.

## Local activation

The verified implementation was restarted on 2026-10-20 at
`http://127.0.0.1:8765`, using the provided acquisition directory read only and
`~/.local/share/tofscope/saved-acquisitions` for persistent output. Health reports
`original_writes=false` and `save_copies=true`; all served assets match the final
manifest hashes. The implementation branch and isolated worktree are retained;
no merge, push, release publication or external deployment was performed.

## Folder visibility and defaults — 2026-10-20

The acquisition folder now defaults to the process current working directory;
the saved copies folder defaults to the effective acquisition folder. Explicit
CLI/environment/TOML folder settings retain their precedence. The open-file
picker labels both configured folders, and Save as displays both the saved-copy
base folder and complete destination including its private owner subfolder.
This location display does not create directories.

When folders coincide, ordinary acquisitions remain browsable while owner hash
directories and symlink aliases into them remain unavailable through acquisition
access. Shared-root tests save a real fixture, check its physical destination,
and reject another owner’s attempt to open it through the shared acquisition
root. Existing files in previously configured output folders are not moved.

Checks passed: 142 Python tests, 11 frontend unit tests, TypeScript typecheck,
33 browser workflows and the production frontend build. Both rebuilt wheel and
sdist also passed independent offline installation, save/restart/source-removal,
exact CSV and optional/interrupted download checks.

## Familiar file explorer — 2026-10-20

The open-file modal now has location shortcuts, breadcrumbs, parent navigation,
a searchable Name/Size list and compact Cancel/Open actions. A click selects,
double-click or Open opens, and keyboard focus, arrows, Home/End and Enter
operate the list. Escape cancels and restores focus; Tab stays inside the modal.
Long folder paths are replaced by their last segment, with complete paths in
native hover tooltips, including the Save as destination. Explanatory paragraphs
and the large folder-path block were removed from the opening flow.

Three new browser cases failed before implementation and now pass. Additional
regressions caught keyboard focus not selecting a row and a shared primary
button style stretching Open across the footer; both were corrected and pass.
All 36 browser workflows, 11 frontend unit tests, TypeScript checks and the
production frontend build pass. Desktop and 560-pixel layouts were visually
inspected from browser screenshots. Scientific reading/writing code is unchanged.

Both rebuilt wheel and sdist also passed their independent offline installation,
new browser file selection, saved-copy restart/source-removal, exact CSV, and
optional/interrupted download checks.
