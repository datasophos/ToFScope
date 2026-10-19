# Packaged React/FastAPI Explore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for inline execution, or superpowers:subagent-driven-development if the user chooses delegation. Implement task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an installable Explore application supporting concurrent users and multiple independent open analyses, with verified scientific behavior.

**Architecture:** Replace the unreleased application's shell, controller and layout directly. Reuse validated Python science/storage code under explicit application services; React consumes renderer-independent data through FastAPI. Preserve the complete prototype in a separate frozen checkout, without compatibility adapters.

**Tech Stack:** Python >=3.11, NumPy, h5py, filelock, FastAPI/Pydantic/Uvicorn; React/TypeScript/Vite; Plotly.js or ECharts selected in Task 7; unittest, Vitest and Playwright. Use setuptools for Python packaging and npm's committed lockfile for frontend builds.

**Spec:** [Replacement proposal](../../react-fastapi-migration.md), with deployment context in [platform and deployment](../../platform-and-deployment.md).

## Global constraints

- “Do not build an AnyWidget compatibility adapter, compatibility imports, or a dual-runtime package.”
- “Concurrent users and multiple open files per user are first-class requirements for the initial architecture and Explore pilot.”
- “There is no application-global current acquisition or current selection.”
- “Do not return Python Plotly figure JSON as the canonical API.”
- “Frame indices are zero-based and inclusive within the stored frame domain.”
- “Mass endpoints are inclusive and retain input precision.”
- “Shared cache entries must not bypass acquisition authorization.”
- “Ship prebuilt assets in the sdist too, so user-side Python builds need no Node.”
- “Bind loopback by default, disable writes, and keep service mode browser-free.”
- “No database, broker or desktop shell is required for the pilot.”

The executable scope is proposal milestones A–F, including renderer evaluation. The [completion plan](2026-10-18-react-fastapi-completion.md) implements G after the packaged Explore milestone. This is one replacement effort; milestones do not require intermediate public releases or retaining the old runtime in the new tree. Publishing artifacts is separate from building and testing them.

## Review focus

1. A read-only acquisition directory must work: reads currently create adjacent lock files. Task 2 tests a writable external lock directory and actual mount permissions.
2. A retry after a lost response must not apply a command or submit integration twice. Tasks 3/6 test request deduplication and stale revisions.
3. The same file opened through an allowed symlink must not produce independent write locks or cache identities. Tasks 2/4 test canonical identity and authorization before reuse.
4. Closing one of several same-file analyses must not evict data still being used or publish a late job into a new analysis. Tasks 4/5/12 test leases, closure and late results.
5. Non-finite coverage values, large arrays and malicious file labels must survive transport/rendering safely without changing intensities. Tasks 8/10 test masks, bounds and text-only rendering.

## Execution and file map

Before code changes, use the worktree skill to select an isolated implementation workspace. Preserve current uncommitted planning documents. No implementation, dependency installation, reference checkout creation, or acquisition writes are part of generating this plan.

| Area | Files and responsibilities |
| --- | --- |
| Science | Move `integration.py`, `signals.py`, `depth_calibration.py`, `isotopes.py`, `abundance.py`, `volume_layers.py` to `src/tofscope/science/`; preserve algorithms and tests. |
| Storage | Move `explorer.py`, `dataset_io.py`, `file_browser.py`, `integration_store.py`, `vendor_export.py` to `src/tofscope/storage/`; `acquisitions.py` provides authorized, generation-aware access. |
| Configuration | Move/extend `server_config.py` as `src/tofscope/config.py`; `resources.py` holds proposed limits. |
| Application | `models.py`, `commands.py`, `workspaces.py`, `explore.py`, `cache.py`, `jobs.py`, `lifecycle.py`: ownership, state transitions, leases and computation. |
| Display/export | `presentation/data.py`, `presentation/explore.py`, `presentation/exports.py`: original values, coordinate metadata, coverage masks and downloads. |
| API | `api/app.py`, `schemas.py`, `auth.py`, `routes.py`, `errors.py`: HTTP validation/ownership and OpenAPI. |
| Frontend | `frontend/src/api/`, `app/`, `explore/`, `plots/`: generated types, command queue, tabs, controls, renderer adapters. |
| Distribution | `cli.py`, `static/`, `resources/reference/`, `scripts/build_frontend.py`, `scripts/check_distribution.py`, `Dockerfile`, `.github/workflows/ci.yml`. |
| Reference/evidence | `docs/validation/prototype-baseline.md`, `docs/validation/renderer-decision.md`, `docs/validation/pilot-qualification.md`; generated measurements outside tracked acquisition data. |

Tests migrate with their owning behavior. Several existing files mix science and `ExplorerWorkspace` tests; split those cases into the new application tests rather than deleting them or requiring AnyWidget. Move Plotly-specific `plots.py` and its tests to the frozen reference only after their numerical assertions have equivalent renderer-independent coverage. Remove old application files from the main tree at Task 13.

## Shared implementation contracts

These names are decisions for this implementation, not existing APIs. Define them in the tasks indicated; later tasks use the same names.

- Task 2: `DatasetRef(key: str, generation: str, relative_path: str)`; `AcquisitionRepository.open(owner: str, relative_path: str) -> DatasetRef`, `metadata(owner, dataset) -> AcquisitionMetadata`, `read(owner, dataset, recipe: SignalRecipe, progress, cancel) -> ndarray`, `assert_current(owner, dataset) -> None`. Public keys/generations are opaque; absolute paths remain internal.
- Task 3: `AnalysisSnapshot` contains owner/workspace/analysis IDs, dataset reference, `revision`, loaded frames, ROI, `DepthSelection`, active recipe, comparisons and display settings; never arrays. `DepthSelection` is the tagged union `all | frame(index) | window(first,last)`. `WorkspaceService.create(owner)`, `create_analysis(owner, workspace_id, dataset)`, `get(owner, analysis_id)`, `replace(owner, analysis_id, dataset, expected_revision)`, `close(owner, analysis_id)` return snapshots where applicable.
- Task 3: `CommandEnvelope(request_id, expected_revision, dataset_generation, command)`; `ExploreService.apply(owner, analysis_id, envelope) -> AnalysisSnapshot`. Commands are `select_stored`, `set_roi`, `set_depth`, `set_loaded_frames`, `add_stored_comparison`, `remove_comparison`, `set_display`. Draft editing stays local; custom Apply is a Task 5 job capturing exact intervals/frames and target `active | comparison`.
- Task 4: `ArrayCache.acquire(owner, analysis_id, dataset, recipe, loader, estimated_bytes) -> ArrayLease`; lease exposes a read-only array and `release()`. Cache keys use canonical dataset identity/generation plus recipe computation inputs, excluding labels, UUIDs and display settings.
- Task 5: `JobService.submit(owner, analysis_id, envelope, spec: IntegrationSpec) -> JobSnapshot`, `get(owner, job_id)`, `cancel(owner, job_id)`, `close_analysis(analysis_id)`. Status is `queued | running | succeeded | failed | cancelled | obsolete`. `IntegrationSpec(intervals, frames, target)` captures the analysis's computational dependency token.
- Task 8: `ExplorePresenter.snapshot(owner, analysis_id, panels: set[str]) -> ExploreData`; `ExportService.render(owner, analysis_id, format: Literal['csv','json']) -> Download(filename, media_type, content)`.

All services take an authenticated owner supplied by server code, never by command JSON. Use injected clocks, repository and runner implementations for deterministic lifecycle/race tests. Unknown IDs and IDs owned by another user both return not-found externally. Views poll canonical revisions; view IDs and heartbeats are not authentication credentials.

Define shared dataclasses in their owning modules, rather than leaving return types implicit:

- `storage/acquisitions.py`: `AcquisitionMetadata(shape, peaks, mass_axis, sum_spectrum, fov_um, raw_shape, image_names)` uses `(depth,y,x,channel)` acquisition shape and existing stored peak metadata; public metadata has no absolute path. Spectrum arrays are transmitted through panel data rather than every analysis snapshot.
- `application/models.py`: `WorkspaceSnapshot(id, owner, analysis_ids)` and `AnalysisSnapshot` as above; recipe identifiers remain distinct from dataset and analysis identifiers. `application/cache.py` owns `ArrayLease`; `application/jobs.py` owns `IntegrationSpec` and `JobSnapshot(id, analysis_id, status, done, total, safe_error)`.
- `api/app.py`: `Services` is a dataclass holding repository, workspace, Explore, cache, jobs and lifecycle services; Task 8 adds presenter/export services. Construct it in application startup, not a global singleton holding current analysis state.
- `presentation/data.py`: `ExploreData` is a revision-tagged panel map; each panel declares kind, content version, coordinate axes, finite values/nulls, coverage, units, aggregation and display-transform metadata. `Download` lives in `presentation/exports.py`.

Representative acceptance assertions to carry into the named test modules (setup uses each task's services/fixtures):

```python
# test_explore_commands.py: applying one analysis never changes its sibling.
before = workspaces.get("owner-b", sibling.id)
explore.apply("owner-a", active.id, roi_command)
assert workspaces.get("owner-b", sibling.id) == before
# test_array_cache.py: borrowed arrays cannot be modified or prematurely freed.
assert not second_lease.array.flags.writeable
first_lease.release()
np.testing.assert_array_equal(second_lease.array, expected_values)
# test_exports.py: display settings cannot alter scientific export values.
assert csv_before_display_change == csv_after_display_change
```

## Task 1: Capture a reproducible scientific and interaction reference

**Files:** Create `docs/validation/prototype-baseline.md`, `scripts/capture_reference.py`, `tests/fixtures/acquisition.py`, `tests/fixtures/__init__.py`, `tests/test_reference_fixture.py`. Read `README.md`, `tests/test_data.py`, `tests/test_signal_recipes.py`, relevant `scripts/check_*.py`.

**Interfaces:** Produces `make_acquisition(path: Path) -> None` from the existing synthetic fixture, extended with two stored channels, SE coverage and missing calibration variants. `capture_reference.py --file PATH --output DIR` records fixture identity, canonical input/output JSON/NPZ, CSV and timing/memory metadata. Runtime measurements are evidence, not assertions inferred from this plan.

- [ ] Record full prototype commit `37ecacf24c32388cd7f84bc11fa509989cc44775`, lockfile hash, Python/browser versions and reference launch command. Create a detached reference checkout outside the implementation tree and verify launch with its own environment; do not copy acquisitions into git.
- [ ] Write `test_reference_fixture` assertions for three stored frames/four raw writes, inclusive custom windows and union overlap counted once. Include the existing exact expected custom values `[[1,.25],[1,.5],[1,.75]]` for intervals `[(1,2),(4,5)]` before extending the fixture.
- [ ] Run `uv run python -m unittest discover -s tests -p test_reference_fixture.py -v`; confirm failure before introducing the fixture helper, implement it and rerun to PASS.
- [ ] Run the reference numerical suite and Explore-related browser scripts listed in the proposal; distinguish preexisting failures and missing external-data checks. Capture ROI/full-field, single/window/all-depth, comparison, SE, draft/apply and export workflows. Extract canonical numerical values rather than image snapshots alone.
- [ ] Record same-machine p50/p95 latency, payload sizes and peak RSS. Set explicit pilot thresholds in the baseline document using these measurements, including a responsive-health threshold under integration; do not substitute 3D performance figures for Explore budgets.
- [ ] Commit the fixture, capture script and baseline manifest as `test: capture prototype behavior for replacement`.

## Task 1a: Evaluate scientific readers before storage implementation

Compare direct h5py, RosettaSciIO and HyperSpy against the frozen numerical
reference and the same synthetic/representative acquisitions. Record versions,
exact endpoint/normalization behavior, selective/lazy reads, peak memory,
metadata fidelity, file-handle ownership and simultaneous independent analyses.
Exercise eager and lazy candidates, including cancellation/close. Select the
lowest-maintenance approach that preserves exact scientific behavior; retain
direct h5py for unsupported or incorrect paths. Document reproducible evidence
in `docs/validation/reader-decision.md` before Task 2. Keep `DatasetRef`, recipes,
array leases and the HTTP/display contract independent of the selected backend.
Do not use the vendor/reconstruction discrepancy as a regression tolerance.

## Task 2: Establish the Python package and authorized storage boundary

**Files:** Create `src/tofscope/__init__.py`, `src/tofscope/{science,storage,resources}/__init__.py`, `storage/acquisitions.py`, `tests/test_acquisition_repository.py`. Move modules per file map; move `data/reference/` into `resources/reference/`. Modify `pyproject.toml`, `uv.lock`, affected tests/imports, `.gitignore`.

**Interfaces:** Implement Task 2 contracts and `load_settings(file: Path | None, env: Mapping[str,str], cli: Mapping[str,object]) -> Settings` in `config.py`. Read references with `importlib.resources`; no source-relative acquisition fallback. `Settings` adds `lock_dir`, `runtime_dir` and mode `local | proxy`. Keep old scientific function names/signatures except internal imports and optional cancellation hooks.

- [ ] Write repository tests: read from a read-only acquisition root with locks in writable `lock_dir`; reject traversal/escaping symlinks; internal symlink aliases share identity/lock; malformed/empty HDF5 and missing calibration report sanitized errors. Assert source bytes are unchanged and denied owners cannot retrieve a cacheable dataset.
- [ ] Run `uv run python -m unittest discover -s tests -p test_acquisition_repository.py -v` to observe the absent-package failure.
- [ ] Move modules/imports and configure setuptools `src` discovery. Keep the distribution name provisional until publication; expose `tofscope` as the import package. Use a configured writable runtime directory for an empty local data root. Map all cooperative reads and writes to stable locks keyed by canonical path, not changing inode/generation. Reads wait at most 30 s for a busy dataset lock on executor threads and return a typed retryable busy error; concurrent channels must not fail immediately just because the prototype used zero-timeout locks. All processes in this deployment use the same lock directory. Document that mixed legacy/new writers or multiple hosts require an explicitly shared lock scheme and mount validation.
- [ ] Remove hidden count-only LRUs from new storage reads when Task 4 takes ownership; meanwhile disable them in repository calls. Ensure metadata/open/read identity checks surround access and that aliasing cannot bypass root policy. Preserve low-level write functions without adding HTTP write access.
- [ ] Split existing controller/figure tests from numerical cases, preserving their assertions for Tasks 3/8 or the completion plan. Run migrated numerical/storage suites; use a clean subprocess importing `tofscope.science.signals` with no Marimo/AnyWidget installed. Confirm reference resources are accessible outside the source directory.
- [ ] Commit as `refactor: package scientific and storage services`.

## Task 3: Implement independent workspaces, analyses and Explore state

**Files:** Create `application/{__init__,models,commands,workspaces,explore}.py`, `tests/test_analysis_state.py`, `tests/test_explore_commands.py`.

**Interfaces:** Implement Task 3 contracts; `WorkspaceStore` protocol exposes owner-scoped CRUD and an in-memory implementation. Array access is injected through a loader until Task 4; do not store arrays in snapshots. A dataset replacement retains the analysis ID but resets acquisition-dependent state and increments revision atomically after successful preparation.

- [ ] Write `test_same_file_analyses_have_independent_selections`: two owners, three analyses of the same dataset; applying ROI/frame to one leaves the others unchanged. Add failed replace preserving the old snapshot; boolean/fractional indices rejected; inclusive bounds clamped only where reference behavior permits; all/frame/window are mutually exclusive.
- [ ] Write `test_command_retry_is_idempotent`: same owner/analysis/request ID and identical payload returns the original command result without a new revision; reusing the ID with different content fails. Cache the last 256 receipts per analysis; an older evicted retry cannot reapply because its expected revision is stale. Stale revisions/generations leave state unchanged and report current revision.
- [ ] Run each test module with `uv run python -m unittest discover -s tests -p test_analysis_state.py -v` and `-p test_explore_commands.py` to confirm failure.
- [ ] Implement typed commands and transactional state transitions. Separate canonical draft-independent analysis data from client-local editing. Preserve stored-channel search metadata, default nominal-27 selection, comparison frame alignment and explicit loaded-frame coverage. Validate unsupported commands without partial mutations.
- [ ] Run both modules to PASS and compare equivalent operations against Task 1 reference snapshots. Commit as `feat: add independent workspaces and analyses`.

## Task 4: Add memory admission and immutable shared array leases

**Files:** Create `application/{cache,resources}.py`, `tests/test_array_cache.py`, `tests/test_resource_limits.py`. Modify `storage/explorer.py`, `science/volume_layers.py` to prevent unaccounted parallel caches when used by new services.

**Interfaces:** Implement `ArrayCache.acquire` above and `ResourceBudget.reserve(owner, analysis_id, bytes: int) -> Reservation`. Count physical shared bytes once globally, and charge each referencing analysis/user its logical bytes for fairness. Private arrays and in-flight allocations are charged in addition. Dataset authorization precedes every cache hit.

- [ ] Write tests asserting read-only NumPy arrays, one physical allocation for concurrent identical reads, distinct entries after generation change, denied cache hits, and release of one lease leaving another valid. Failed loads release reservations. Replacement or analysis closure during load discards the result safely.
- [ ] Write tests with a 64-byte budget: a reserved 48-byte load prevents another 32-byte load before either allocates. Underestimation must acquire extra admission before allocation or fail without exceeding the budget. Count bounded transport/presentation temporaries as well as retained channels; stream or reject excessive responses.
- [ ] Run cache/resource modules to fail, then implement reservations, single-flight loading, byte LRU of unleased entries, reference counts and generation invalidation. Reads into custom arrays use preflight shapes/dtypes; reject unknown/unbounded allocations. Keep NumPy reductions chunked where temporary size would exceed admission.
- [ ] Proposed initial configurable limits: global managed bytes 4 GiB, per-user 2 GiB, per-analysis 1 GiB, 8 analyses/user, 32/server; queue limits 4/analysis, 8/user, 32/server. These are implementation starting values, subject to Task 1/12 measurements, not scientific caps. Startup diagnostics expose them and document additional interpreter/browser/allocator memory outside the managed budget.
- [ ] Run `uv run python -m unittest discover -s tests -p 'test_array_cache.py' -v` and `-p test_resource_limits.py` to PASS; verify existing 81 MiB/channel workload fits configured representative limits. Commit as `feat: bound analysis memory and share immutable data`.

## Task 5: Implement fair jobs, cancellation and connection lifecycle

**Files:** Create `application/{jobs,lifecycle}.py`, `tests/test_jobs.py`, `tests/test_analysis_lifecycle.py`, `scripts/benchmark_runner.py`. Modify `science/integration.py` for cooperative cancellation between frames and repository progress plumbing.

**Interfaces:** Implement Task 5 contracts. `Runner.submit(callable) -> Future` is an injected bounded executor; scheduler round-robins owners and analyses, defaults to two active jobs globally and one per user. `Lifecycle.attach(owner, analysis_id) -> ViewLease`, `heartbeat(owner, lease_id)`, `detach(owner, lease_id)`, `reap(now)` manage views separately from analysis state.

- [ ] Write barrier-controlled tests completing old integration after newer Apply, replacement and close; no obsolete result changes state or retains arrays. A display/ROI change during integration should not obsolete a result whose source/recipe/target inputs still match. Explicitly track computational dependency tokens rather than rejecting on every revision change.
- [ ] Test repeated submission of one request ID yields one job; round-robin B runs before A's backlog; cancelling one consumer of shared data does not cancel another's work. Close cancels queued jobs immediately; running cancellation becomes terminal only after resources stop being used and late results are discarded.
- [ ] Test injected-clock view leases: heartbeat every 15 s, lease expiry 45 s; retain work for 120 s without live views, request cancellation after that grace, expire abandoned analysis at 15 min. A second live view prevents expiry; explicit close overrides grace. No polling request may resurrect a closed analysis.
- [ ] Run both modules to fail; implement scheduler, cleanup and progress, without blocking the API loop. Benchmark two-file HDF5/integration workloads using threads and processes. Start with threads if measured budgets pass; if processes are needed, record the decision and use worker-opened HDF5 plus bounded file/shared-memory result descriptors and cleanup, never large ndarray pickling. Account for worker allocations before admission.
- [ ] Run tests to PASS and `uv run python scripts/benchmark_runner.py --file PATH --output DIR`. Record runner choice, observed HDF5 lock contention and health responsiveness. Commit as `feat: schedule bounded analysis jobs and reconnect leases`.

## Task 6: Expose an owner-scoped API with safe local and proxy access

**Files:** Create `api/{__init__,app,schemas,auth,routes,errors}.py`, `scripts/export_openapi.py`, `tests/test_api.py`, `tests/test_auth.py`; modify dependencies for FastAPI/Pydantic/Uvicorn and dev HTTP test client.

**Interfaces:** `create_app(settings: Settings, services: Services) -> FastAPI`; Pydantic tagged command schemas mirror Task 3. Routes below are all under `/api/v1`, except `/healthz` and `/readyz`:

```text
POST /workspaces                         GET /workspaces/{wid}
POST /workspaces/{wid}/analyses           GET /analyses/{aid}
DELETE /analyses/{aid}                    POST /analyses/{aid}/replace
POST /analyses/{aid}/commands             POST /analyses/{aid}/jobs
GET /analyses/{aid}/data?panels=...        GET /jobs/{jid}
POST /jobs/{jid}/cancel                   GET /analyses/{aid}/exports/{format}
POST /analyses/{aid}/views                POST /views/{vid}/heartbeat
DELETE /views/{vid}                       GET /files?directory=...&offset=...
```

Workspace deletion closes its analyses. Add `DELETE /workspaces/{wid}` and `GET /workspaces` for an owner-scoped workspace list. Data/export routes are added by Task 8. Use 202 for accepted jobs, 409 for stale revisions/source or retryable dataset-busy errors (distinct codes), 422 for invalid commands, 429 for configured capacity, 404 for missing/foreign resources, and 503 for not-ready. Error JSON has `code`, safe `message`, `request_id`, optional current revision; no absolute paths/tracebacks.

- [ ] Write API tests for owner A/B guessing every ID type, including view/job/download IDs; forged owner fields/headers; cross-origin mutation; duplicate commands/jobs; revision conflict; unknown `/api` routes returning JSON 404 rather than the SPA. Include paginated browsing and malformed shapes/bounds.
- [ ] Run API/auth tests to fail; implement authentication dependencies and strict schemas (`extra=forbid`, finite floats and true integers). Local launch bootstraps a random secret through the URL fragment, clears it immediately and exchanges it once for an HttpOnly SameSite cookie; mutation requests require a CSRF header and expected Origin/Host. Never log the bootstrap secret or store it in analysis JSON. Direct service access supplies a documented authenticated bootstrap flow.
- [ ] Proxy mode requires configured trusted proxy addresses and an authenticated identity header; reject missing identity and identity headers from untrusted peers. Deployment binds to an interface reachable only by that proxy. The trusted research-group data root initially grants all authenticated group users read access; per-file ACL policy remains behind the repository authorization function. Do not implement account administration or shared mutable editing.
- [ ] Keep HDF5, synchronous locks, reductions and response preparation in bounded executor work; lifespan owns runner cleanup. Health/readiness remains responsive while jobs execute. Generate OpenAPI deterministically and add request-size/interval-count bounds before constructing arrays.
- [ ] Run API/auth tests to PASS. Run `uv run python scripts/export_openapi.py --output frontend/openapi.json` (without startup dataset loading). Commit as `feat: expose authorized multi-analysis API`.

## Task 7: Select the Explore renderer using real interactions

**Files:** Create `frontend/{package.json,package-lock.json,tsconfig.json,vite.config.ts,index.html}`, `frontend/evaluation/{main.tsx,PlotlyProbe.tsx,EChartsProbe.tsx}`, `frontend/e2e/renderer.spec.ts`, `docs/validation/renderer-decision.md`. Read Task 1 fixture outputs and `web/interval_editor.js` from the frozen reference.

**Interfaces:** Evaluation-only adapters consume the same renderer-neutral probe fixture and emit `roiPixels`, `massIntervals`, `depthSelection` events. Keep candidate dependencies dev-only until the decision; only the selected Explore renderer enters the shipped bundle. Choose and record exact supported versions in the npm lockfile; no candidate library is preselected by this plan.

- [ ] Create Playwright assertions before adapters: reversed/clipped ROI selects the reference pixels; both interval endpoints survive edits; drag beginning on a peak works; window move/resize preserves inclusive frames; zoom survives data update and maximize; delayed old response does not reset the last selection.
- [ ] Run `npm --prefix frontend run test:renderer` to fail. Implement the same spectrum, image ROI and depth profile probe in Plotly.js and ECharts with delayed fixture updates, offline assets and consistent geometry. Do not build full duplicate applications.
- [ ] Run `test:renderer`, measure same-machine p50/p95, payload/bundle size and export quality, and count custom interaction code. If neither candidate can satisfy correctness without brittle internal APIs, evaluate visx + Canvas against the same tests; evaluate uPlot only if profiling isolates line-chart cost. Record why the chosen renderer passes and where custom overlays remain.
- [ ] Document vtk.js as a separate spatial evaluation in the completion plan, including nonuniform calibrated Z; it does not delay Explore. Remove the losing renderer from production imports. Commit as `spike: select Explore renderer with interaction evidence`.

## Task 8: Serve renderer-independent display data and scientific exports

**Files:** Create `presentation/{__init__,data,explore,exports}.py`, `tests/test_explore_data.py`, `tests/test_exports.py`. Modify API routes and extracted assertion cases from `tests/test_comparisons.py`, `test_calibrated_profiles.py`, `test_calibrated_views.py`.

**Interfaces:** Implement Task 8 contracts. `ExploreData` includes `analysis_id`, revision/generation, panel-specific content version and explicitly ordered axes. Matrix shape/order is `[y,x]`; spectrum/profile arrays include sample coordinates, original intensities and coverage masks. Use JSON finite number arrays initially; represent missing values by null plus coverage metadata, never by zero. Include units, pixel boundaries, aggregation, exact recipes, intensity range and display-transform instructions. Canonical values stay unscaled; client adapters apply declared display transforms once.

- [ ] Write `test_original_values_and_coverage`: original-resolution ROI means and XZ sums match the baseline, custom comparison gaps remain missing, SE final rows use actual coverage, all/window/frame modes aggregate correctly. Serialize float32 boundary cases without rounding input mass bounds. Test strict JSON with non-finite samples and a long acquisition rejected/chunked within the configured response budget.
- [ ] Write `test_exports_ignore_display_scaling`: toggling log/relative settings changes no CSV values; single-frame mode still exports loaded frames unless a window is selected; JSON preserves recipe v3 intervals, loaded/selected range and canonical calibration metadata. Root-relative paths only; unsupported future fields aren't silently dropped. Validate exact values against captured outputs with justified per-quantity tolerances only where representation changed.
- [ ] Run both test modules to fail, implement presenter/export service using Task 4 leases and bounded executor work, then connect routes. Panels have dependency/content versions so ROI changes do not force retransmission of the full spectrum. Check generation before and after preparing a snapshot; return 409 if the source changed.
- [ ] Run both modules and API tests to PASS; assert no Plotly figure schema or whole acquisition volume in responses. Commit as `feat: serve scientific display data and exports`.

## Task 9: Build React workspace tabs and a typed API client

**Files:** Create `frontend/src/api/{generated.ts,client.ts,commandQueue.ts}`, `frontend/src/app/{App.tsx,WorkspaceTabs.tsx,FilePicker.tsx,useAnalysis.ts}`, `frontend/src/main.tsx`, `frontend/src/styles.css`, `frontend/src/api/commandQueue.test.ts`, `frontend/e2e/workspaces.spec.ts`; configure Vitest and Playwright scripts.

**Interfaces:** Generate `generated.ts` from Task 6 OpenAPI using a locked generator. `useAnalysis(analysisId)` owns canonical snapshots/polling/view lease; client-local renderer/draft state is keyed by analysis and client view. `commandQueue.send(analysisId, command)` serializes commits, retains request ID on retry and coalesces intermediate gestures without dropping the final action.

- [ ] Write queue tests asserting retries preserve ID, conflicts refresh revision without blindly replaying an obsolete drag, and a newer analysis response cannot replace another tab. Component/browser tests open A/B/A in one workspace plus A for a second user; selections remain independent. New browser tabs start independently; explicit reattach uses the existing analysis. Repeated React mount/unmount leaves one live lease/poll loop.
- [ ] Run `npm --prefix frontend test -- commandQueue` and `npm --prefix frontend run test:e2e -- workspaces.spec.ts` to fail. Implement the app, exact file-picker pagination/search, explicit replace/close and empty/error states. Persist only owner-safe workspace identifiers as appropriate; do not use a single globally shared “current analysis” cookie.
- [ ] Handle restart/expired IDs with a clear recovery screen and reopen action. A failed file open leaves existing analyses available. Stop polling and release view leases on cleanup; do not treat a browser unload as guaranteed delivery.
- [ ] Run `npm --prefix frontend run generate:api`, `npm --prefix frontend run typecheck`, unit/browser tests to PASS. Commit as `feat: add multi-analysis React workspace`.

## Task 10: Implement the linked Explore screen

**Files:** Create `frontend/src/explore/{ExploreScreen.tsx,SignalSidebar.tsx,MassDraftEditor.tsx,FrameControls.tsx,DepthSelection.ts,selection.test.ts}`, `frontend/src/plots/{PlotPanel.tsx,ExploreRenderer.ts,selectedRenderer.ts}`, `frontend/e2e/explore.spec.ts`. The selected adapter wraps the Task 7 winner; never import both renderers into the production app for convenience.

**Interfaces:** `ExploreRenderer.mount(element, data, callbacks) -> {update(data), resize(), destroy()}`; callbacks emit data-space selections to shared pixel/frame conversion functions and explicit mass drafts. Parent React state owns maximize/restore, zoom, keyboard focus and draft intervals; canonical applied state comes from the server. Initial panels are ion/front/spectrum/profile with an SIMS/SE toggle.

- [ ] Write selection assertions from the baseline: ROI bounds `[2,6,8,4]` for shape `(1301,128,128)` and FOV 20 produce `(13,37,26,50)`; display-coordinate roundtrip preserves pixel bounds. Include reversed axes, first/last frame, narrow mass intervals and intervals between sampled masses. Synthetic chart values must not trigger integration until Apply.
- [ ] Write browser assertions for ROI replacement/edit/reset, frame click/window drag/edge resize/Shift-move/all-depth reset, spectrum edges and exact entries, stored/custom comparisons, loaded frames, fixed color range, log/relative toggles, maximization/Escape/resize and preserved zoom. Labels containing HTML/script-like text render literally.
- [ ] Run `npm --prefix frontend test -- selection` and `npm --prefix frontend run test:e2e -- explore.spec.ts` to fail. Implement controls and renderer adapter, using stable accessible labels and renderer-neutral browser selectors. Apply custom windows via Task 5 jobs; show progress/cancel/error and last valid plots during computation. Discard stale generation/content-version responses.
- [ ] Add CSV/settings download controls with exact numeric scope and a visible Explore-only indication. Do not advertise unavailable calibration/identify/3D/save dialogs. Run unit, typecheck and Explore browser tests to PASS against synthetic data and the representative acquisition. Commit as `feat: deliver linked Explore interactions`.

## Task 11: Produce a self-contained package and one launcher

**Files:** Create `src/tofscope/cli.py`, `scripts/{build_frontend,check_distribution}.py`, `tests/test_cli.py`, `tests/test_distribution.py`, `Dockerfile`, `docs/deployment.md`, `tofscope.example.toml`; modify `pyproject.toml`, `.gitignore`, API static mounting and frontend build scripts.

**Interfaces:** Entry point `tofscope = tofscope.cli:main`. Commands `tofscope`, `tofscope serve --no-browser`, `tofscope doctor`. CLI overrides > environment > TOML > defaults. Preserve `TOFSCOPE_DATA_ROOT`, `TOFSCOPE_ALLOW_WRITES`, `TOFSCOPE_ALLOW_UNVERIFIED_NATIVE`; explicitly document `TOF_FILE` as optional initial-open configuration without allowing out-of-root access. Pilot write routes remain absent even if policy flags are set.

- [ ] Write CLI tests for empty/missing/unreadable roots, malformed booleans, occupied ports, config precedence, no-browser service mode and browser launch only after readiness. Doctor checks root/runtime/lock directories and reports mode, limits and package/asset version without secrets. Mock browser opening; do not launch real browsers in unit tests.
- [ ] Run CLI tests to fail. Implement graceful shutdown, local bootstrap, lifecycle cleanup and static routing with JSON API 404s. Generate hashed assets plus a build manifest from the selected renderer; disable or locally host API documentation assets. Include every script/font/worker/reference file required at runtime.
- [ ] `build_frontend.py` runs the locked frontend build and copies verified assets into `src/tofscope/static/`; release prep runs it before `uv build`. Include prebuilt static files and manifests in both wheel and sdist. Validate asset hashes at build/test time and fail on missing/stale source-build inputs; an sdist build must consume bundled assets without invoking npm.
- [ ] Run `npm --prefix frontend ci`, `uv run python scripts/build_frontend.py`, `uv build`. `check_distribution.py --artifacts dist --output DIR` installs the wheel and independently builds/installs the sdist into temporary environments outside the checkout, removes Node/npm from runtime PATH, clears PYTHONPATH and launches the installed application. Assert package resources, health, initial plots, custom integration and exports work, and block browser network requests except the app origin. Use synthetic acquisitions; dependency downloads during installation need not be offline.
- [ ] Build/run the optional container from the tested wheel as a non-root user with read-only acquisitions and a writable runtime mount; one externally exposed port and one API process. Document localhost, proxy identity/HTTPS, configuration, memory overhead, restart semantics, pinned upgrade/rollback and actual NFS qualification procedure. Run CLI/distribution tests to PASS. Commit as `build: ship Explore assets with the Python application`.

## Task 12: Qualify concurrent use, races and resource exhaustion

**Files:** Create `frontend/e2e/{concurrency,lifecycle,offline}.spec.ts`, `scripts/qualify_pilot.py`, `tests/test_dataset_invalidation.py`, `docs/validation/pilot-qualification.md`.

**Interfaces:** `qualify_pilot.py --base-url URL --data-root PATH --output DIR` records owner/analysis/job counts, managed bytes, RSS, health/interaction latency, queue order and payload sizes using sanitized diagnostics. Use authenticated test credentials from local fixtures, never production user impersonation.

- [ ] Write missing tests before fixes: two users with A/B/A each, distinct selections/downloads; simultaneous Apply then new recipe; explicit replacement during reconstruction; a long queued backlog with a second user receiving service; disconnect/reconnect and close with pending results; shared cache survives another analysis closing. Exercise tiny injected budgets rather than intentionally exhausting machine RAM.
- [ ] Add external dataset replacement on disposable copies: identity changes mark all affected analyses stale, caches invalidate, and new reads/exports refuse mixed generations. Prototype does not write during this test. Canonical aliases must invalidate together. A failed reload retains the previous metadata but clearly marks it unusable/stale.
- [ ] Run API/unit and browser concurrency tests, fix only demonstrated failures, rerun to PASS. Use fake-clock tests for long lifetimes and real browser tests for connection behavior. Test logout/relogin identity changes clear owner-specific frontend state.
- [ ] Run representative local and proxy deployments, then actual POSIX/NFS data mount with read-only access. Compare with Task 1 thresholds, record excluded/missing hardware checks explicitly, and tune default limits if measured workload requires it. No shared-deployment recommendation until isolation and resource checks pass. Commit as `test: qualify concurrent Explore workloads`.

## Task 13: Make the new app the development entry point and enforce CI

**Files:** Modify `README.md`, `docs/platform-and-deployment.md`, `docs/react-fastapi-migration.md`, `pyproject.toml`, `uv.lock`; create `.github/workflows/ci.yml`. Remove obsolete `app.py`, `workspace.py`, `web/`, `plots.py` and widget-only dependencies/harnesses after their still-required behavior has test coverage or is recorded for the completion plan.

- [ ] Update README to the installed/local/service commands, Explore scope and exact frozen-reference checkout/launch procedure. Describe the renderer decision, owner/workspace/analysis model and pending completion work. Existing roadmap plans remain historical; link these replacement plans without suggesting old widget paths remain implementation targets.
- [ ] CI runs migrated unittest suites, TypeScript checks, Vitest, synthetic Playwright tests, OpenAPI generation/drift verification, release asset build, wheel/sdist smoke tests and the container smoke test. Record external-acquisition and real-NFS checks as explicit qualification work rather than CI successes. Source-tree CI runs `generate:api` and fails on an unexpected generated diff.
- [ ] Verify in clean environments that neither Python package nor production JS requires Marimo/AnyWidget or the losing renderer. Keep all scientific/storage tests, including write validation; replace old widget assertions with equivalent services/display assertions or carry their exact cases into the completion plan. Do not silently delete coverage for deferred features.
- [ ] Run the full CI command set once on the final tree, `git diff --check`, and the immutable prototype's launch smoke independently. Record evidence and outstanding external checks. Commit as `docs: establish the packaged Explore development workflow`.

## Plan review and handoff

Coverage: A → Task 1; boundaries → 2–4; concurrent users/analyses, API/jobs → 3–6/9/12; renderer evaluation → 7; scientific presentation/exports → 8/10; packaged local/server operation → 11–13. Deferred dialogs, calibrated UI, sections, volumes and native saves have executable tasks in the completion plan; durable workspace restoration remains explicitly deferred in the design.

Review the plan and renderer evaluation scope before execution. Choose inline execution or delegated implementation/review. Inline execution is the default recommendation because storage, budgets and ownership interfaces are tightly coupled; this plan alone does not authorize publishing, enabling acquisition writes, or changing external services.
