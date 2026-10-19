# Packaged Explore qualification, 2026-10-18

Implementation is Explore-only. All acquisition operations in real-data checks
used HDF5 mode `r`; source size, inode and modification time were unchanged.
Disposable synthetic/copy tests alone exercise preserved write validators.
No release was published and no external deployment/service was changed.

Reference: frozen `37ecacf24c32388cd7f84bc11fa509989cc44775`, 87 original tests
passed; own locked environment and HTTP/widget Ready smoke passed independently.
See [baseline](prototype-baseline.md) and [coverage disposition](coverage-map.md).

Passed checks (final rerun counts are recorded in the execution ledger and CI):

- Migrated numerical/storage plus repository, canonical state, cache/admission,
  jobs, lifecycle, API/auth, presentation, CLI and distribution unit suites.
- TypeScript checks, generated OpenAPI/types, Vitest queue/ROI/gesture checks;
  Playwright Explore, A/B/A two-user concurrency and both renderer probes.
- Separate wheel and sdist installs outside the checkout, Node absent from PATH,
  no Marimo/AnyWidget/RosettaSciIO runtime dependency; same-origin-only browser
  plots, custom integration and settings download.
- Deterministic barriers: old Apply cannot overwrite newer Apply; ROI-only edits
  do not obsolete integration; new user runs before another user's backlog;
  request retry produces one result/job; close suppresses late commits.
- Source change invalidates canonical aliases across owners, refuses mixed
  exports and permits explicit transactional reopen. Tiny injected byte budgets
  reject allocations before production loaders run; shared leases stay read-only
  and survive another consumer closing.
- Read-only file permissions with locks in an external writable directory;
  traversal/escaping symlinks, HDF5 external/virtual storage and foreign resources
  denied. Cookie/CSRF/Host/Origin checks and trusted-proxy identity denial pass.
- Missing SE pixels remain null with coverage masks; short final image averages
  use actual coverage. Front XZ sums retain full X and sum ROI Y. CSV is unchanged
  by log/relative display settings and keeps blank comparison gaps.

Real AlTiPt acquisition, Apple Silicon / Python 3.12.3 / headless Google Chrome:

| Check | Observation |
| --- | --- |
| Stored / raw shape | 1301×128×128×217 / 1302×128×128 |
| Nominal 27 channel bytes | 85,262,336 (81.3 MiB) |
| Direct full-channel read + profile/front | 389.4 ms |
| Explicit float32 framework raw comparison, four frames | exact equality |
| Vendor reconstruction difference | max .25, sum -3.0; not a regression tolerance |
| Two owners / six same-file analyses | foreign access denied; independent revisions |
| API selection p50 / p95 | .921 / 1.028 ms (12 samples) |
| Health p95 during 64-frame raw integration | 2.222 ms |
| Full four-panel JSON | 2,455,692 bytes (under 32 MiB) |
| Qualification process peak RSS | 259,309,568 bytes |
| Initial browser four-panel load | 1,344.6 ms |
| Browser frame update p50 / p95 | 92.2 / 101.2 ms (12 samples) |
| Offline browser / JS errors | no external requests / no errors |

The browser timings above precede the final whole-image rendering fix; final
post-fix timings are appended below. Large-image qualification exposed default
progressive drawing leaving late rows unfinished during rapid updates. The
1301×128 last-row pixel test failed before disabling those batches and passed
afterward. This is why canvas inspection accompanies numeric/API checks.
Measurements are local workload evidence, not universal capacity claims. Runner
subset comparison favored threads including process startup; HDF5 operations
serialize on the dataset lock and HDF5's own lock. Managed bytes do not include
all Python/HDF5/browser allocator overhead.

Not established: actual NFS mount behavior, acquisition hardware/timing/SE
registration, commercial numerical/save round-trip, multi-host/API-worker
scaling, durable workspace restoration and deferred completion-plan screens.
Neither local POSIX nor the read-only container check establishes NFS locking or
atomic replacement on the eventual deployment mount. These are explicit
qualification limits, not passed or silently skipped checks.

## Final review fixes and packaged rerun (2026-10-19)

A fresh read-only review identified ten Important issues and no Critical issues.
All ten were fixed and covered before completion. Browser regressions now check
single-active-tab keyboard handling, drawing a replacement ROI over the initial
full-field selection, rejecting a late partial response assembled for an older
revision, reusing/recovering workspaces through ten reloads, and reattaching an
expired view lease. Python regressions check that metadata admission precedes
array reads and is released, raw variable-length allocation is refused before
exceeding the configured memory budget, infinity becomes a missing value with a
coverage mask, SE contrast does not change with the selected ion channel, and a
missing source becomes stale and can be replaced.

Final local checks after these changes: 82 Python tests, 6 Vitest tests, 8
Playwright tests, TypeScript typecheck, and generated OpenAPI client checks passed.
Wheel and sdist clean-install checks passed without Node.js in runtime PATH or
Marimo, AnyWidget, or RosettaSciIO installed. Both installed builds served plots,
ran a synthetic custom integration, and exported data with browser network
requests limited to the app origin. The local container passed with UID 10001,
read-only root filesystem and acquisition mount, writable runtime mount, one
port, and successful readiness and plotting checks. The frozen 37ecacf prototype
still passes its separate launch smoke and has an unchanged, clean checkout.

A final read-only custom integration job against the provided AlTiPt acquisition
completed one 128×128 frame through the admitted HDF5 variable-length reader.
The source file's size, modification time, and inode were unchanged. Existing
full stored-channel and framework comparisons remain exact; see the acquisition
and isolated reader reports. The final real-browser run loaded four panels in
1.62 s, had no browser errors or external requests, and measured frame updates
at p50 215 ms / p95 217 ms. This is local workload evidence; the previous run
was faster, so these numbers should not be treated as a stable latency promise.

The service restores owner-scoped in-memory workspaces across browser reloads
and new tabs. State still resets when the service restarts. Actual NFS lock and
replacement behavior, acquisition hardware timing/SE registration, commercial
format save/readback, and multi-host service scaling were unavailable and were
not verified. No release, external deployment, or acquisition write occurred.

## Demo interaction follow-up (2026-10-19)

The provided `pfib-tofwerk opened.h5` (10×64×64×259) and
`fake_fib_sims_opened.h5` (5×16×16×10) were opened as independent analyses in
one workspace. The 259-signal picker stayed within 200 px, search narrowed its
options, and Escape dismissed it. Nine frame steps on the ToF-Werk file had
local p50/p95 latency of 98.9/99.8 ms. The browser made no external requests and
reported no JavaScript errors. These checks used read-only acquisition access.

The follow-up browser tests also verify square image stages, the ion-map/spectrum
top row and front-projection/depth-profile bottom row, ordinary wheel scrolling
without plot zoom, and Ctrl/Cmd-wheel zoom. All nine Playwright tests and six
Vitest tests passed. Frontend assets were rebuilt; the resulting wheel and sdist
both passed the installed-package smoke with Node absent and browser requests
restricted to the local service. No architecture or feature plan changed in
this UI follow-up.
