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
local p50/p95 latency of 98.9/100.0 ms. The browser made no external requests
and reported no JavaScript errors. These checks used read-only acquisition
access.

The follow-up browser tests also verify square image stages, the ion-map/spectrum
top row and front-projection/depth-profile bottom row, ordinary wheel scrolling
without plot zoom, and Ctrl/Cmd-wheel zoom. Image charts now wait to mount until
the measured square viewport is ready, avoiding a stretched first paint; their
column stays sized for the square image while spectrum and depth plots use the
remaining width. All nine Playwright tests and six Vitest tests passed.
Frontend assets were rebuilt; the resulting wheel and sdist both passed the
installed-package smoke with Node absent and browser requests restricted to the
local service. No architecture or feature plan changed in this UI follow-up.

## Large-acquisition interaction follow-up (2026-10-19)

Maximize/restore was reproduced on the read-only 2.2 GB
`pfib_1301x128x128_AlTiPt.h5`. The per-pixel chart renderer took 443–533 ms in
the local event-to-two-animation-frame check. Replacing its per-pixel display
objects with a cached raster reduced the same check to 22–31 ms across twelve
events (three maximize/restore pairs for each image). The frontend still receives
the same original-resolution scientific arrays. The renderer decision document
records the measurement scope and the gap in the initial evaluation.

The spectrum scale toggle also had a missing React effect dependency: its label
changed without updating the chart. It now triggers a chart update. The browser
test verifies that the actual canvas changes for linear mode and returns to the
same rendered image when log mode is restored.

Nine unit tests and eleven browser tests pass, including full-size resize latency
under 200 ms, no data refetch on resize, canvas/stage size agreement, precise
pixel colors, orientation, missing-data transparency, zoom cropping and sharp
pixel boundaries. The real-file browser run made no external requests and
reported no JavaScript errors. Frontend assets were rebuilt, and both the wheel
and source distribution passed installed-package browser smoke checks with Node
absent and external browser requests blocked. Optional Python lint was unavailable
because Ruff is not installed in this environment. No backend, reader,
acquisition-write capability or future-feature plan changed.

## Contextual help and branding follow-up (2026-10-19)

The frozen prototype's pane help in `web/workspace.js` was restored and adapted
to the pilot's available controls. Compact info buttons cover all four panes,
signals, comparison profiles, mass windows, spatial ROI, loaded frames, display,
depth selection, exports and workspaces/files. Hover and keyboard focus reveal
help; clicking pins it. Escape or an outside click dismisses it. Tooltips have
unique accessible descriptions, float outside clipped chart/sidebar containers,
and stay within the viewport. Escape dismisses help before restoring a maximized
pane. Opening help does not change analysis state.

The header again uses the prototype's white T with a teal dot and its
FIB–SEM / TOF–SIMS subtitle. The mark is inline SVG, so it needs no font glyph,
external asset or CDN. Pane subtitles remain removed.

The production frontend build, nine unit tests and twelve browser tests pass.
The full-size resize regression still paints in 19–29 ms in this local run.
No backend, scientific reader or future-feature plan changed.

## Full-volume raw integration follow-up (2026-10-19)

The reported Apply slowdown was reproduced against the frozen prototype using
26.5–27.5 Th over all 1301 stored 128×128 frames. The previous pilot took 69.50 s;
the prototype took 15.80 s. Pooling the admitted raw-event allocations reduced
the pilot to 12.69 s. A new integration through the actual job service completed
and committed in 11.17 s. All 21.3 million output values match the frozen
prototype exactly; checksums and scope are recorded in
[integration-performance.json](integration-performance.json) and the
[reader decision](reader-decision.md).

Memory admission, cancellation, per-user scheduling and source checks remain
enabled. Reservation calls fell from 21.3 million to 6,514; prepaid arena space
increases the conservative managed reservation peak by 15.8 MiB, without raising
any configured limit. This is managed admission accounting, not process RSS.
The real acquisition's inode, size and modification time were unchanged.
No reader framework, public API, deployment architecture or completion-plan
feature scope changed.

After the change, all 89 Python tests and 12 browser tests passed. The seven new
raw-read regressions cover batched admission, exact cell counts, scratch and
arena lifetime, partial-read/caller failures, concurrent consumers and supported
integer byte orders. Both rebuilt wheel and source distribution passed the
installed-package offline plot/integration/export checks with no runtime Node.js.
The frozen prototype checkout remained clean. Existing unavailable NFS/hardware
checks were not promoted to passes by this local performance qualification.

### Profile identification (2026-10-19)

Depth profiles now have a wrapping legend and matching line markers beside the
active signal and each comparison. Labels retain mass windows, integration
frames and comparison identifiers. A single client-side mapping supplies the
renderer, sidebar and exported PNG; removing a comparison preserves surviving
colors during the open analysis. Colors are reassigned on a page reload.
Additional curves cycle through eight colors and then dashed/dotted styles.
The legend scrolls when necessary to preserve chart space, while PNG exports
include all labels. This changes presentation only; numerical data, APIs and
reader behavior are unchanged.

The new browser regression failed before implementation because the legend was
absent. After implementation all 13 browser tests and 9 frontend unit tests
passed. The regression checks actual curve pixels against sidebar/legend colors,
color stability after removal, the maximized legend, and PNG legend swatch/text
pixels. Existing full-size image maximize/restore checks remained below 28 ms in
this local run. TypeScript checking and the bundled production build passed.
No new real-acquisition or unavailable hardware/service qualification was claimed
for this presentation change. The completion plan and architectural decisions
remain unchanged.

### Selection visibility (2026-10-19)

Selection outlines now use one CSS pixel with SVG non-scaling strokes, replacing
strokes that expanded with the plot dimensions. The fill opacity fell from
13.3% to 6.3%. Separate transparent 12-pixel edge targets preserve resize gestures
without covering curves, including in maximized plots. The shared overlay applies
to spectra, profiles and image ROIs; selected numerical bounds are unchanged.

A browser regression reproduced 12-pixel solid boundaries before the fix. It now
checks rendered boundary pixels at two viewport sizes and resizes an edge from
four pixels away. All 14 browser tests, 9 frontend unit tests, TypeScript checking
and the production build passed. The running local service served the rebuilt
assets with matching hashes, without restarting or clearing workspaces. No
backend, acquisition, architectural or completion-plan changes were required.

### Display defaults and tool-panel height (2026-10-19)

New analyses default to logarithmic image colors and relative profiles. Explicit
per-analysis overrides remain independent; profile values and CSV data remain
at original scale. A new service test first failed on the previous false defaults,
then passed after changing DisplaySettings. The browser also checks that both
controls are selected on file open.

The desktop tool panel stretches to the bottom of the plot grid, rather than
using an unrelated viewport-height cap. Its controls scroll within that height;
the scope note sits below the grid. Size containment lets the plots determine
the row height. On narrow screens the tools retain their natural height above
the stacked plots. The browser regression reproduced a 182-pixel height mismatch,
then verified matching bottoms, resizing, scroll access and the narrow layout.

All 90 Python tests, 15 browser tests, 9 frontend unit tests, TypeScript checking
and the bundled production build passed. Updated layout assets were verified
through the running local service. That service was left running to preserve
active workspaces; the Python display defaults require its next restart.
No acquisition writes or additional hardware/service qualification were performed.
The architecture and completion plan remain unchanged.

## Signal workspace redesign (2026-10-19)

The approved design replaces active/comparison destinations with stable named
signals and independent image/profile choices. A tray replaces the permanent
sidebar. An explicit spectrum editor owns drafts; plot-local controls own ROI,
image colors, relative profiles and viewing depths. Jobs publish versioned signal
results atomically. Failed updates retain committed results, hidden updates stay
hidden without pinned leases, and removing a submitted signal closes its editor.

Validation: all 109 Python tests, 11 frontend unit tests, 21 browser tests and
TypeScript checking passed. The browser suite preserves numerical interactions,
owner isolation, multiple files/independent same-file analyses, precise interval
inputs, dirty-draft choices, late-data label safety, keyboard/help, square images,
PNG legends and wheel behavior. Full-size 1301×128 fixture maximize/restore stayed
under 33 ms in the final suite, without data fetches. A resident fixture switch
took 58 ms with no integration job and no spectrum refetch.

Both freshly built wheel and sdist passed independent installation and offline
browser checks without Node or runtime Marimo/RosettaSciIO dependencies. The smoke
creates a custom signal, switches images, toggles profile visibility and downloads
schema-4 settings, CSV and PNG. Its earlier run against the old packaged UI failed
at the missing Create from spectrum control, proving it detects stale assets.

Read-only checks on `pfib_1301x128x128_AlTiPt.h5` passed two-user/six-analysis
isolation, denied foreign IDs, independent revisions and integration completion.
The real browser opened that file and `pfib-tofwerk opened.h5` together, with no
browser errors or external requests. Initial four-panel load measured 1.39 s;
a resident stored-signal switch measured 312 ms without integration or spectrum
refetch. Image maximize/restore measured 26–31 ms. Four frame steps measured
about 182 ms median through replacement image data, rather than command response
alone. These are local observations, not NFS or cross-machine guarantees.

`pfib_1301x128x128_AlTiPt_raw.h5` is readable HDF5 but lacks PeakData. Its attempted
open is rejected as an unsupported layout and preserves the existing analysis.
The raw-only multi-file attempt is not a passing supported-file check. No raw-only
opening workflow was added by this redesign. NFS/proxy deployment, acquisition
hardware and controlled writes remain unqualified/unavailable as before.

Packaging uses a separate temporary staging copy while the user's old service
is active, to avoid serving the new frontend against its old in-memory API. The
staged frontend source digest matches the implementation source, and all bundled
asset hashes were verified. Activation and its required workspace-resetting
restart happen only after final review. Launch commands remain in README and
deployment.md. Full-volume raw reconstruction took 12.75 s; the signal-targeted service job took
11.67 s versus 17.18 s for the frozen direct function. All 21,315,584 float32
values matched exactly (SHA-256
`2c5b35292c24716b711345128552b05735d6ba178657eb64db34a3e18515523e`).
The source inode, size and modification time were unchanged. Prototype timing
uses its direct integration function, not the complete Marimo UI.
Numerical comparison details and machine-readable outcomes are
recorded in signal-workspace-qualification.json.


Final independent review found three Important issues; a stored-duplicate coverage
issue was regraded Important by the executor. All four were reproduced with
failing tests and fixed in one pass. The final suite passes 111 Python, 11 unit
and 23 browser tests plus TypeScript. See [review details](signal-workspace-review.md)
for fixes, review limits and the deferred deduplication-focus minor. Real-data
arithmetic is unchanged; timing/equality results above describe the preceding
qualification run, not a second full-volume benchmark after metadata-only fixes.


The rebuilt wheel and source distribution passed offline installed-app checks
again after review fixes. The exact verified staged assets were activated in the
implementation checkout and the local service restarted on port 8765. Health and
readiness returned 200; the new signal API schema and all served asset hashes
matched. This reset temporary analyses/unsaved drafts as communicated before the
restart. Canonical frontend source digest matches its manifest; the frozen
prototype remains clean. No external deployment or release was performed.
