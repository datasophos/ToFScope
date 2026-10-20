# File-centered analysis qualification — 2026-10-19

This supersedes the earlier pilot report's workspace/reconnect and restart-loss limitations for explicitly saved analyses. Unsaved analyses remain temporary. No release was published, external service deployed, or original acquisition modified.

## Passed checks

- 135 Python tests; 11 frontend unit tests; TypeScript typecheck; 32 Playwright workflows. These cover owner separation, independent file tabs, save/edit/close/cancel races, quota admission, corrupt metadata, filename collisions, hidden signals, union windows, partial coverage, exact restored profiles, explicit download, and dirty-state decisions.
- Production frontend build and fresh wheel/sdist builds. Both independently installed packages run with no Node.js in runtime PATH, no Marimo/AnyWidget/RosettaSciIO runtime dependency, and no external browser requests.
- Each installed package saved custom/hidden signals and display settings, restarted, removed its disposable original acquisition, reopened the saved copy, and produced exactly the original CSV. Saving did not initiate a download. Explicit download worked; disconnecting a download preserved the server file.
- Docker 29.7.2: local image build and readiness/plots, UID 10001, read-only root filesystem and acquisition bind mount, writable runtime/output mounts, one port. Saving and reopening a copy passed inside the container. Smoke output storage uses tmpfs; production needs a persistent output volume.
- Frozen prototype checkout remains clean at `/private/tmp/tofscope-prototype-37ecacf`.

## Real acquisition

The read-only qualification uses `pfib_1301x128x128_AlTiPt.h5`, 2,207,119,636 bytes, 1301 × 128 × 128 × 217. The original inode, size, mtime and SHA-256 remain unchanged. The generated copy is temporary and is moved to a new root, opened by a fresh service and owner, then removed with the qualification scratch directory.

Vendor group/dataset attributes, dataset layout, contiguous values and all allocated chunk payloads compare exactly. Full-resolution custom union values and ROI CSV compare exactly after reopening, with raw integration patched to fail if called. Hidden signals, ROI, display settings and saved revision restore correctly. Machine-readable measurements are in [file-centered-analysis-qualification.json](file-centered-analysis-qualification.json).

The browser check on the same acquisition reported no errors or external requests. Image maximize/restore took 21.6–33.8 ms; four frame steps had p50 268 ms and p95 331 ms. Initial four-panel loading took 3.22 s and a resident stored-signal switch 577 ms, with no raw integration or spectrum refetch. This run overlapped the content-verification workload, so it is not a clean-machine latency comparison. The picker contained 217 options within a 200-pixel list.

## Limits and operation

Use one service process. Keep acquisitions read only and configure a persistent output root:

```sh
tofscope --data-root /path/to/acquisitions --output-root /path/to/saved-analyses
```

Saving needs space for a complete acquisition copy plus custom volumes and verification overhead. It creates a new filename and never replaces an existing file. Browser download is optional and can take a long time. Saved files restore committed state; pending drafts/calculations must be resolved first.

NFS locking/publication and power-loss durability, commercial-software round trips, acquisition hardware and multi-host/multi-worker operation remain unverified. The raw-only example lacks the required stored PeakData and remains unsupported. Managed-memory measurements exclude Python/HDF5 allocator overhead and browser memory. Existing original-write denial remains in force; creating new copies does not enable commercial-native acquisition writes. Calibration, identification and 3D remain future features under the completion plan.

## Execution decisions

The plan was approved in Plannotator with no annotations after incorporating optional-download feedback. Implementation decisions and review outcomes are recorded below; numerical/owner boundaries remain independent of renderer and reader choices.
