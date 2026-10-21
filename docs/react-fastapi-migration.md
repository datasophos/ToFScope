# React/FastAPI replacement proposal

Recorded 2026-10-18; packaged Explore implementation completed on the isolated
implementation branch. See [qualification evidence](validation/pilot-qualification.md)
and [deployment](deployment.md) for current commands and measured limits. Read alongside [platform and deployment](platform-and-deployment.md).

## Outcome and approach

Deliver a maintainable instrument workspace while retaining scientific behavior
and a single-service installation. Start with architecture boundaries and a
packaged, read-only Explore pilot. The app is unreleased: replace its structure
wholesale where useful, without maintaining compatibility with the old UI. Keep
the complete Marimo prototype runnable in a separate frozen reference checkout. Acceptance is based on numerical results, interactions, installation,
and resource use, rather than visual resemblance alone.

Recommended: build one new React/FastAPI application, reusing the scientific
modules and tests while freely reorganizing the package and replacing controller
and frontend code. There are no released clients, APIs or installation workflows
to support. Do not build an AnyWidget compatibility adapter, compatibility imports,
or a dual-runtime package. The prototype is a behavioral reference, not a second
application to maintain alongside the replacement.

A wholesale replacement does not require rewriting validated numerical algorithms.
Preserve scientific semantics while changing interfaces, file layout and state
management as needed. Explore is the first runnable milestone for validating the
architecture and packaging, not a compatibility rollout or a separate product.

Assumptions for review: the first pilot has no HDF5 write endpoint, active analyses are
ephemeral and shared deployment initially uses one API process with bounded
background computation. Renderer
selection remains open pending the comparison below. No database, broker or
desktop shell is required for the pilot.

## Current seams

- `app.py` is a small Marimo entry point; preserve its run command in the
  frozen reference checkout, not in the replacement package.
- `workspace.py:ExplorerWorkspace` owns analysis state, commands, exports,
  figure preparation, and AnyWidget messaging. Use it to identify behavior, then
  replace it with explicit application services; do not expose the widget over HTTP.
- `explorer.py`, `signals.py`, `integration.py`, `depth_calibration.py`,
  `isotopes.py`, `abundance.py`, and `volume_layers.py` provide reusable science.
- `file_browser.py`, `server_config.py`, `dataset_io.py`, `integration_store.py`,
  and `vendor_export.py` contain access and persistence policy worth retaining.
- `plots.py` provides reference display behavior and transforms; Python-generated
  Plotly figures will not define the new API contract.
  `web/workspace.js` and its editors are interaction references, not the new
  application's state store.
- `pyproject.toml` currently describes `tofscope-prototype`; it has no release
  asset pipeline or launcher. Packaging is part of the pilot, not follow-up work.

## Boundaries and ownership

Proposed package layout; modules may move directly into their final locations:

```text
src/tofscope/
  science/          # numerical functions, recipes, calibration
  storage/          # HDF5 access, identity, locks, root confinement
  application/      # sessions, typed commands, jobs, exports
  presentation/     # renderer-independent display data and exports
  api/              # FastAPI schemas, routes, session ownership
  static/           # release-built frontend assets
  cli.py            # launcher, service mode, diagnostics
frontend/src/
  app/              # workspace shell and API client
  explore/          # signal sidebar and linked Explore panels
  plots/            # renderer lifecycle and interaction adapters
```

| Boundary | Owns | Must not depend on |
| --- | --- | --- |
| Science | Signal definitions, original-resolution values, calibration and reductions | HTTP, React, widgets, browser state |
| Storage | Validated root-relative acquisition access, file identity, locks and cache invalidation | UI events or client-supplied absolute paths |
| Application | Authoritative selections, applied recipes, comparisons, revisions and job lifecycle | FastAPI request objects, traitlets, DOM |
| Presentation | Display data, coordinates, coverage, export formatting and transport-safe values | Renderer-specific figure schemas or mutation of scientific arrays |
| API transport | Validation, ownership checks, command dispatch, responses | Reimplementation of integration or selection semantics |
| React | Layout, focus, zoom, draft editing and interaction feedback | HDF5 access or scientific normalization |

The dependency flow is React → API → application → science/storage, with
presentation reading application snapshots. Reorganize reusable Python modules
into this package and update their imports and tests directly. The new application
has no dependency on Marimo, AnyWidget or traitlets. The frozen prototype retains
its own source and locked environment; it does not consume the new services.

The server owns canonical integer pixel/frame selections and applied recipes.
The client owns transient drag positions and unsubmitted drafts. Server responses
return validated canonical selections. Zoom/maximize state stays in React and
must survive data updates. Express all-depth, single-frame and depth-window modes
as explicit alternatives so contradictory selection state cannot occur.

## Scientific contract

Carry these invariants into tests before changing controller ownership:

- Frame indices are zero-based and inclusive within the stored frame domain.
  Do not guess the mapping of the extra raw write.
- Mass endpoints are inclusive and retain input precision. Preserve disjoint
  interval canonicalization and existing normalization; missing calibration is
  an error. Reconstructed channels remain independently derived from vendor data.
- Original-resolution arrays drive profiles, spatial selection and exports.
  Log colors and relative display scaling never change scientific values.
- Preserve ROI rounding/clamping, exact front XZ sums, window ion sums, and SE
  means divided by actual pixel coverage, including the shorter final image.
- Preserve comparison coverage and frame alignment. Missing data remains missing.
- Preserve canonical nm anchors, interpolation only between anchors, unknown
  later depths, and frame-based selection without resampling intensities.
- CSV remains unscaled ROI mean intensity over the selected window or loaded
  frames. JSON retains exact recipes, loaded/selected ranges and calibration;
  do not imply recipe import is available.
- Later 3D migration retains valid partial-block means, physical geometry,
  coverage clipping and the shared voxel budget. It cannot silently alter science.

Use exact comparisons for discrete selections and unchanged numerical paths.
For serialization/representation differences, specify tolerances per quantity
with a scientific justification before accepting them. Do not treat the reported
vendor/reconstruction discrepancy as a blanket regression tolerance.

## Multiple users, workspaces and open analyses

Concurrent users and multiple open files per user are first-class requirements
for the initial architecture and Explore pilot. A browser connection, a login
session and an analysis are different objects; avoid using “session” to mean all
three. There is no application-global current acquisition or current selection.

| Object | Owns or identifies |
| --- | --- |
| User | Authenticated identity, permissions and resource quota; local mode supplies a local owner identity. |
| Workspace | A user-owned collection of open analyses and their ordering. |
| Analysis | One acquisition reference with independent ROI, signals, comparisons, calibration, selections, revision and jobs. |
| Dataset | Validated acquisition identity/generation and reusable immutable data, subject to access checks. |
| Job | One analysis's computation, captured input dependencies, progress, cancellation and result. |
| Client view | Browser-local focus, zoom and layout, plus a connection to an authorized analysis. |

Use workspace tabs for open analyses. Opening a file creates a new analysis by
default; replacing an analysis's acquisition is an explicit separate action and
must be transactional. Allow the same file in multiple analyses, including for
one user, with independent selections. Different users may read the same dataset
without sharing mutable analysis state. Shared cache entries must not bypass
acquisition authorization.

New browser tabs restore the owner’s in-memory workspace and open analyses;
each acquisition opened from the picker still creates an independent analysis.
Explicit analysis-ID reattachment remains available when a link or another
client provides the ID. Multiple client views attached to an analysis receive
canonical revision updates; stale commands reconcile against the latest state.
Client-local zoom and focus remain independent. Workspace state resets when the
service restarts.

Closing an analysis cancels queued work, requests cancellation of running jobs,
suppresses late results and releases its retained arrays. Reference-count shared
cache entries so closing one analysis cannot invalidate another's data. Expire
abandoned analyses after a documented reconnect grace/idle timeout; a brief
network interruption must not immediately discard a running integration. A
remaining connected view keeps the analysis active. Polling/heartbeat lifecycle
must distinguish temporary absence from an explicit close.

Enforce limits at analysis, user and server levels for open analyses, retained
bytes and queued/running jobs. Schedule fairly between users, with bounded work
per analysis, so one user opening many files cannot monopolize the service.
Account for in-flight allocations and shared versus private arrays; report
resource-limit failures without silently closing another user's analysis.

Retain acquisition identity/generation independently of analysis revisions.
Future writes coordinate by dataset across all users and analyses. A successful
replacement invalidates cached data and marks every affected analysis stale;
reload is explicit and cannot silently change the scientific source mid-analysis.

Active arrays/jobs and workspace metadata have separate lifecycles. The pilot
keeps workspace metadata in memory and documents loss on restart, with recipe
exports available. Durable restoration of open-file references, selections and
recipes is a later capability; it must validate source identity and recompute
arrays, not serialize live HDF5 handles or promise recovery of running jobs.
Define workspace storage behind an interface now without adding a database to
the pilot solely for this future capability.

## API, analysis state and long computations

Start with versioned HTTP commands and polling; defer WebSockets/SSE until there
is a measured need. Publish OpenAPI schemas and generate TypeScript API types in
the build, with a drift check in CI. Do not maintain parallel handwritten schemas.

Proposed surface:

- Create/read/delete owner-scoped workspaces and analyses; list open analyses;
  browse the configured data root. Explicitly distinguish create, replace,
  reconnect and close operations.
- Open a root-relative acquisition transactionally: a failed open preserves the
  existing analysis. Return an opaque dataset generation and public metadata.
- Submit typed commands for stored signals, comparisons, ROI, frame/window,
  drafts and display settings. Fetch canonical state and renderer-independent
  display data snapshots.
- Submit custom integration and expensive preparation as jobs; poll status and
  progress, request cancellation, and obtain results only through their owning analysis.
- Download analysis-scoped CSV/JSON exports. Provide health/readiness and version
  metadata without exposing filesystem paths or private analysis data.

Every command includes request ID, expected analysis revision and dataset
generation. Serialize commits within an analysis; reject stale commands explicitly
and return current state for reconciliation. Every job captures its recipe,
dataset identity and relevant state revision. Publish a result only if its
dependencies still match; an obsolete job cannot overwrite newer selections.
Keep drag feedback local, coalesce intermediate updates, and submit a final
selection so request order cannot undo the last user action.

Use an explicit bounded job runner outside the ASGI event loop. Begin with a
small executor and a bounded queue; measure HDF5 locking, GIL contention and memory
before selecting threads versus processes for production. Processes must reopen
files themselves and avoid copying full channel arrays through IPC. Cancellation
is cooperative at available frame/chunk boundaries; always suppress obsolete
results even when a running operation cannot immediately stop.

Configure analysis/user/global limits, idle lifetime, jobs, queue length,
retained bytes and response size. Account for active and custom comparison volumes, not just
the stored-channel LRU; one example channel already costs about 81 MiB. Reject
excess work with an actionable error before allocating. Share only immutable,
identity-keyed data under a global byte budget; never share mutable analysis state.
Release arrays/jobs on expiry and shutdown. On disconnect retain work only for
the configured reconnect grace period; restart explicitly loses ephemeral state.

Opaque workspace/analysis IDs are not authorization. Bind analyses/jobs/downloads to an
owner credential; enforce same-origin requests and CSRF protection where cookies
are used. Local mode uses loopback and a launcher-established secret. Shared mode
requires a configured authenticated proxy or application authentication, with
trusted identity headers accepted only from that proxy. Test cross-owner access
denial before recommending shared use. Keep root confinement and stale-source
checks on every relevant acquisition operation.

## Explore pilot scope

Include the file picker and empty/error states; stored signal search and recent
signals; stored/custom comparisons; exact single/disjoint mass drafts with
explicit Apply; loaded-frame range; and custom integration with progress and
obsolete-result handling. Include ROI drawing/editing/reset and exact entries,
all-depth/single-frame/window navigation, spectrum/profile interval editing,
SIMS/SE toggle, log/relative display settings and CSV/settings JSON exports.

Recreate the four-panel Explore grid: ion top map and front projection, spectrum
and depth profile. Include resizing, maximize/restore, Escape, preserved zoom,
keyboard controls and clear loading/failure feedback. Bundle the selected
rendering libraries locally. Test data serialization for arrays, non-finite
values, precision and payload size. Send derived display data, not whole
acquisition volumes; refresh only affected panels.

Defer the dedicated depth-anchor editor and calibrated-view UI, identification
and isotope dialogs, 3D/layer tools, remaining cross-section screens and native
saves until after the Explore milestone. Preserve their core models/tests now;
the frozen prototype remains available to inspect the complete workflows. The pilot must identify itself as Explore-only; it must not advertise
full feature parity or silently discard unsupported recipe fields.

## Renderer evaluation before Explore implementation

Retaining Plotly is a baseline option, not a settled architectural choice.
Evaluate alternatives now, before implementing the Explore rendering layer.
The recommended comparison is Plotly.js versus Apache ECharts for Explore,
with vtk.js assessed separately for spatial visualization. Multiple renderers
are acceptable when their responsibilities are clear and justified.

| Candidate | Fit for ToFScope | Trade-off to investigate |
| --- | --- | --- |
| Plotly.js | Baseline for spectra, profiles, images and existing 3D behavior | Existing custom selection logic; measure whether it remains maintainable in React. |
| Apache ECharts | Alternative for Explore 2D charts, with Canvas/SVG rendering and chart interactions | Prove exact image coordinates, editable ROI and mass-window behavior. |
| visx + Canvas | React visualization primitives for custom instrument interactions | More application code for axes, interaction, image rendering and export. |
| vtk.js | Dedicated volume rendering, image slices and spatial widgets | Requires another library for spectra/profiles; validate calibrated depth geometry. |
| uPlot | Candidate for dense spectrum/profile plotting if performance requires it | Narrower scope adds another renderer for images and volumes. |

Start with Plotly.js and ECharts. Consider visx if both make required direct
manipulation awkward; introduce uPlot only if measurements establish a line-chart
bottleneck. vtk.js is a separate 3D/spatial decision, not a prerequisite for the
Explore pilot. A renderer switch must preserve physical coordinates, coverage,
missing values and scientific intensity semantics.

Use the same representative acquisition, selections and hardware for a focused
comparison that exercises:

- A spectrum with exact, draggable mass-window edges and preserved zoom.
- An ion image with pixel-accurate ROI drawing, moving and resizing.
- A linked depth profile with frame/window selection.
- Resizing and maximizing while asynchronous data updates arrive.

Compare interaction correctness, latency, payload size, export quality, local
asset/bundle cost and the amount and clarity of custom code. Include narrow
peaks, edge pixels, window endpoints and stale responses. Record the result and
chosen renderer with the baseline measurements; a simple chart demo is not
sufficient evidence. This is a focused evaluation, not a commitment to build
complete interfaces in every candidate.

The API returns scientific arrays, coordinates, coverage and metadata independently
of the renderer. Keep canonical values distinct from display transforms and
preserve full-resolution scientific operations on the server. Frontend adapters
construct library-specific figures and translate gestures into typed selections.
Do not return Python Plotly figure JSON as the canonical API. This boundary allows
2D charts and a specialized volume renderer to coexist without coupling science
or session services to either library.

## Delivery sequence and exit gates

These are engineering milestones within one replacement effort, not staged
releases or compatibility gates. Establish A/B and the renderer evaluation first; C–E deliver the packaged
Explore pilot. Remaining screens can follow once the architecture works; F is
required before recommending shared deployment, not before further UI work.

| Step | Concrete work | Exit evidence |
| --- | --- | --- |
| A: baseline | Record reference commit `37ecacf`, fixture identity, representative workflows and environment. Add small synthetic fixtures; keep large acquisitions external. | Existing numerical suite and relevant prototype browser checks run; baseline failures recorded separately; reference launch verified in a separate checkout with its own locked environment. |
| A2: renderer evaluation | Compare Plotly.js and ECharts using the interaction probe above; assess vtk.js separately for later spatial views. | Record correctness, performance, export and maintenance findings; select the Explore renderer before D; API remains renderer-independent. |
| B: boundaries | Create typed workspace/analysis state and Explore services, using `workspace.py` as a behavior inventory; reorganize science/storage modules directly; separate display data/exports and API transport. | Application tests import without Marimo/AnyWidget; equivalent workflows match reference selections, values and exports; no compatibility adapter or imports required. |
| C: service | Add validated workspace/analysis API, owner checks, revision/generation protocol, fair job scheduling and bounded caches. | Tests force out-of-order completion, dataset replacement, cancellation, failed open, expiry, queue exhaustion, multi-analysis isolation and cross-owner access; health remains responsive during real integration. |
| D: React Explore | Build shell, selected renderer adapter, sidebar and linked selections in the new application. | Adapt existing Explore browser scenarios; check ROI replacement and interval races, maximize/resize/zoom and export values against the reference. |
| E: packaged pilot | Add build backend, bundled assets/reference catalog, CLI, config, diagnostics and release CI. | Wheel and sdist built; wheel installed and sdist rebuilt/installed outside checkout; launches without Node or source files and works with runtime CDN requests blocked. |
| F: deployment qualification | Exercise localhost and authenticated shared service against representative mounted data. | Two users each open multiple analyses, including the same file and duplicate same-file analyses for one user; selections, jobs and downloads remain isolated. Exercise explicit reattachment, stale revisions, disconnect/reconnect, close during integration, fair scheduling and memory pressure. Measured RSS, retained cache bytes, queue depth, payload size and latency stay within configured limits; shutdown/reconnect and rollback documented. |
| G: complete replacement | Implement calibration, identification/isotopes, sections, 3D and write-back using the new boundaries. | Scientific parity, browser checks and packaged smoke tests cover the complete workspace; remove obsolete prototype files/dependencies from the main tree. |

For D, adapt `check_browser.py`, `check_depth_window.py`, `check_all_depths.py`,
`check_spectrum.py`, `check_peak_picker.py`, `check_window_sets.py`,
`check_interval_selection_race.py`, `check_roi_replacement.py`,
`check_file_browser.py`, and relevant layout/viewport checks. Separate shared
behavior assertions from transport-specific selectors; replace widget-specific
harnesses as needed rather than preserving their implementation. Preserve numerical suites for integrations, comparisons,
calibration, file access and write-back throughout.

Record pilot p50/p95 interaction latency, integration duration, payload sizes and
peak RSS on the same dataset, hardware and selections as the reference. Require
no unexplained regression and no stale updates. Choose explicit numerical budgets
from those baseline measurements in A before qualifying D/F; the published 3D
32 MiB/200 ms measurements are not Explore acceptance thresholds.

## Packaging and operation

Build React/TypeScript with locked developer tooling (Vite is a proposed build
tool); copy hashed assets into the Python package during release preparation.
Include offline isotope reference data. Exclude the prototype UI and dependencies
from the new distribution. CI must fail if frontend assets are absent or stale.
Ship prebuilt assets in the sdist too, so user-side Python builds need no Node.
Remove Marimo/AnyWidget from replacement dependencies directly. Document the
separate reference checkout command for developers who need behavior comparisons.

Target commands, not available interfaces yet: `tofscope` for local browser
launch, `tofscope serve --no-browser` for a service, and `tofscope doctor` for
configuration/data-access diagnostics. Final distribution naming and publishing
availability must be checked before promising `uv tool install tofscope`.
Launch only after readiness; explain missing data roots, occupied ports and
unreadable acquisitions in startup errors.

Serve API and bundled assets on one port. Keep `/api` errors separate from SPA
fallback routing. Use one worker initially because workspace/analysis/job state is in memory;
do not document multiple Uvicorn workers as a scaling option without shared-state
design. No Node server runs in production.

One TOML configuration covers data root, bind/port, write policy and resource
limits; define precedence as CLI > environment > file > defaults. Retain useful
`TOFSCOPE_*` overrides and explicitly document the prototype-only settings.
Bind loopback by default, disable writes, and keep service mode browser-free.
Provide a versioned optional container with the same wheel and configuration,
an unprivileged user and mounted acquisitions. Test the actual POSIX/NFS mount.

Upgrade by installing a pinned artifact; rollback by reinstalling the previous
artifact/container and restarting, acknowledging lost ephemeral workspaces/analyses.
Neither process reverses HDF5 writes. Later write migration must preserve both
experimental opt-ins, locking, free-space checks, backup, sibling verification,
replacement and stale-session handling. Commercial reading/display passed for
one representative addition; numerical agreement and full save workflow remain
unverified. Framework migration cannot broaden that claim.

## Reference preservation and review

Before replacing files, record the immutable prototype commit (`37ecacf` as
inspected for this proposal) and verify its documented launch in a separate
checkout with its locked dependencies. Keep a fixture/workflow manifest with
that reference. The main tree can then replace or delete `app.py`, `workspace.py`
and legacy `web/` files without compatibility shims. Keep the reference runnable
for comparisons; do not port new architecture into it.

There is no deployed-user cutover, legacy API support period or requirement to
ship both UIs. If a milestone fails validation, correct the replacement and use
the reference to investigate. Avoid freezing known scientific bugs into the new
implementation: intentional behavior corrections need their own explanation and
regression evidence.
The [packaged Explore implementation plan](superpowers/plans/2026-10-18-react-fastapi-pilot.md)
implements A–F with concrete interfaces, tasks and verification. The
[completion plan](superpowers/plans/2026-10-18-react-fastapi-completion.md) covers G.
Both await review before execution. Application implementation, publishing and
removal of legacy code are outside this planning change.

## Framework references

- [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/)
  documents serving packaged assets; select the precise frontend mounting API
  against the version pinned during implementation.
- [FastAPI background tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
  provides background-task guidance; the bounded scientific job lifecycle above
  is an application design responsibility.
- [React state structure](https://react.dev/learn/choosing-the-state-structure)
  supports keeping state explicit and avoiding duplicated/contradictory values.

- [Apache ECharts features](https://echarts.apache.org/en/feature.html) and
  [Canvas/SVG rendering](https://echarts.apache.org/handbook/en/best-practices/canvas-vs-svg/).
- [visx](https://github.com/airbnb/visx).
- [vtk.js volume rendering](https://kitware.github.io/vtk-js/api/Rendering_Core_Volume.html)
  and [widgets](https://kitware.github.io/vtk-js/docs/concepts_widgets.html).
- [uPlot](https://github.com/leeoniya/uPlot).

- [FastAPI worker processes](https://fastapi.tiangolo.com/deployment/server-workers/):
  adding API processes requires explicit shared-state ownership and routing.
- [h5py threading](https://docs.h5py.org/en/stable/threads.html): HDF5 API calls
  are serialized by a global lock; benchmark threads versus compute processes
  rather than assuming threaded reads scale across files.


## Explore interaction redesign (2026-10-19)

The approved [signal workspace design](superpowers/specs/2026-10-19-explore-signal-workspace-design.md)
supersedes active/comparison destination controls and snapshots in this proposal.
Analyses own stable named signal records; image choice and profile visibility
reference their IDs. A signal tray replaces the permanent sidebar, custom drafts
use an explicit spectrum editor, and display/ROI controls live beside plots.
Calculation coverage belongs to each signal; viewing depths selects frames for
the image without recalculating signals. The separate analysis range was removed
on 2026-10-21: profiles and navigation use the acquisition domain, with image
navigation limited to the image signal's coverage. Viewing controls expose All
frames, Single frame and Frame range, and CSV export lives in the profile toolbar.
Jobs target versioned signal IDs and commit atomically; display choices do not
invalidate scientific work. Hidden signals count toward record quotas without
pinning every volume. Settings use schema 4. Reader/renderer boundaries, scientific
calculations, multi-user admission and the one-service offline package remain.

The signal tray now uses a compact strip: Images selects the displayed signal,
Profiles lists colored chips, and Add signal combines stored-channel search with
Create from spectrum. Manage signals opens the complete collection on demand.
This keeps the plots near the top of the viewport while retaining access to hidden
signals and exact provenance. Calculation progress appears on the relevant chip.

## File-centered persistence amendment (2026-10-19)

The approved file-centered design supersedes public workspace grouping, manual
analysis-ID reattachment and the earlier lack of durable restoration. Independent
file tabs remain owner-scoped. Save as writes a new self-contained HDF5 copy and
opening it restores committed state/results; original acquisitions stay immutable.
Downloads are optional and never automatic. See the
[file-centered plan](superpowers/plans/2026-10-19-file-centered-analysis.md).
This does not implement the completion plan's native save-back feature.
