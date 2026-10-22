# Complete React/FastAPI Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for inline execution, or superpowers:subagent-driven-development if the user chooses delegation. Implement task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the replacement's calibrated, identification, isotope, section, volume and controlled-save workflows after the packaged Explore milestone.

**Architecture:** Extend the analysis services, renderer-neutral display payloads and React UI from the pilot. Keep scientific calculations in the reused Python modules, owner checks on all API objects, and dataset-generation coordination across analyses. Evaluate spatial rendering separately from the selected Explore renderer.

**Tech Stack:** The pilot's Python/FastAPI and React/TypeScript stack; existing calibration/isotope/volume/write-validation modules; selected 2D renderer, with vtk.js or Plotly for spatial views after measurement.

**Spec:** [Replacement proposal](../../react-fastapi-migration.md); prerequisite [packaged Explore plan](2026-10-18-react-fastapi-pilot.md). Read both before execution.

## Pilot handoff context

The packaged pilot uses direct h5py behind `AcquisitionRepository`, ECharts for
Explore and renderer-neutral typed panel payloads. See the reader/renderer
reports in `docs/validation/`. The exact prototype assertions retained as text
under `docs/validation/prototype-tests/` are part of this plan's acceptance
inventory: restore the relevant cases per task, replacing widget/Plotly calls
with application/presenter assertions. In particular carry calibrated profile
sample visibility and unknown-depth CSV (Task 1), identification annotations and
uncertainty exports (Task 2), calibrated section values (Tasks 1/3), single-plane
fallback and calibrated pooling across anchor slope changes (Task 4), and
post-replacement save outcomes (Task 5). No legacy runtime belongs in the package.
The Explore redesign uses stable named signal records, image_signal_id and
profile_signal_ids instead of active/comparison slots. Read
[the signal workspace spec](../specs/2026-10-19-explore-signal-workspace-design.md)
and [implementation plan](2026-10-19-explore-signal-workspace.md) before extending
the UI/API. Identification actions should create or annotate signals and then
choose display roles; avoid reintroducing destination-specific integrations.
Schema-4 settings export the committed collection. The pilot adds configurable
signal record quotas (including hidden/pending records) alongside byte admission;
spatial/private preview preparation must use the same reservations. The response
contract now reserves transport buffers until send completion.

## Global constraints

- “Original-resolution arrays drive profiles, spatial selection and exports.”
- “Log colors and relative display scaling never change scientific values.”
- “Preserve canonical nm anchors, interpolation only between anchors, unknown later depths, and frame-based selection without resampling intensities.”
- “A successful replacement invalidates cached data and marks every affected analysis stale; reload is explicit and cannot silently change the scientific source mid-analysis.”
- “Later 3D migration retains valid partial-block means, physical geometry, coverage clipping and the shared voxel budget.”
- Preserve both experimental write opt-ins; commercial read/display validation does not establish numerical agreement or the full save workflow.
- No AnyWidget adapter, database, remote job service or prototype runtime enters the replacement package.

This plan uses the pilot's exact `AnalysisSnapshot`, `CommandEnvelope`, `ArrayCache`, `JobService`, owner checks, view leases and generation protocol. Extend command/OpenAPI tagged unions and regenerate TypeScript types in each task. Each feature must run in the installed package, not just the source tree. Shared deployment qualification can proceed separately; local feature work need not wait for NFS access.

## Review focus

1. An anchor slope change inside a pooled block must not move its displayed geometry incorrectly: Task 1/4 test calibrated block coordinates.
2. The same assigned ion with overlapping signal windows must not produce misleading fractions: Task 2 tests suppressed fractions and coverage statuses.
3. Constant/thin volumes and unknown-depth frames must remain interpretable: Task 4 tests points fallback, clipping before pooling and preserved values.
4. Close/replacement during a native save must not leave the application reporting a failed save after the file was successfully replaced: Task 5 separates durable save outcome from UI selection.
5. Changing one file while another analysis uses an alias must invalidate every dependent result: Task 5 tests aliases, cached generations and pending jobs across users.

## Task 1: Depth calibration and calibrated views

Scope: Explore profiles and front projections. Sections and 3D remain Tasks 3/4.
Depth calibration was implemented inline on the PR #1 branch and merged into
`main` through [PR #2](https://github.com/datasophos/ToFScope/pull/2).
[PR #3](https://github.com/datasophos/ToFScope/pull/3), merged on 2026-10-21,
adds explicit viewing modes, centered calibration controls, and the confirmed
heading/help overlap fix. Task 2 identification/isotopes is now implemented; Task 3 sections is next.

The separate analysis range is now removed: profiles span the full acquisition,
while signal calculation coverage and viewing selections remain distinct. The
older restricted-domain and legacy-document checks below record historical
validation. Files containing the retired analysis-range field are intentionally
unsupported; no compatibility migration is planned. Current evidence is in the
[Explore control validation](../../validation/explore-controls.md).

Resolved assumptions (2026-10-20):

- Named signals replace active/comparison slots; reuse `ExploreService.apply`
  commands and its owner/revision/generation/idempotency boundary rather than
  adding a parallel CalibrationService transport.
- The compact UI uses a temporary graphical dialog near Viewing depths, based
  on the frozen prototype's frame-coordinate profiles, exact fields, fixed
  origin, anchor table, graphical markers and explicit coverage. Manual feedback
  moves Frames / Physical depth to main Viewing depths buttons and gives fields
  visible outlines/white backgrounds, with red rejection alerts. Scientific axes
  carry names/units/ticks, and line plots show hover x coordinates. Frame ticks
  and readouts are integer-only; physical depth/mass retain precision.
- `set_depth_anchors` accepts canonical nm anchors (at most 4096);
  `set_depth_display` chooses `nm|um|mm` and `frame|depth`. Calibration belongs
  to each analysis, including same-file analyses. Display changes launch no jobs.
- `presentation/coordinates.py` provides original frame IDs, physical sample
  coordinates, unknown coverage and mean block coordinates across anchor kinks.
  Panel axes include boundaries and original acquisition-frame IDs. Front
  rasters respect nonuniform row geometry; no scientific values are resampled.
- The editor requests frame-coordinate profiles without mutating shared state.
  Navigation converts displayed coordinates through supplied sample IDs. Ion
  maps still use the full frame selection, including unknown depths.
- HDF5 document version 2 stores anchors and unit/coordinate choices; version 1
  defaults to frame coordinates with origin only. Old applications explicitly
  reject the new version. Saved numerical arrays and publication protections
  remain unchanged; original acquisitions are immutable.

- [x] Add failing application and browser assertions for validation, fixed origin,
  partial calibration, unknown exports, original-frame mapping, units without
  resampling, and removal restoring frame coordinates.
- [x] Implement command/schema state, reusable coordinate handling, graphical
  editor, calibrated profile/front payloads and CSV `depth_nm` blanks. Do not
  implement sections or 3D screens. Display cell boundaries are footprints,
  not inferred plane thickness or a claim of physical aspect ratio.
- [x] Restore archived profile/front numerical assertions through presenter tests,
  including nonzero domains, one known sample, empty physical domains, exact
  front values and mean block depth 30 nm for frames `[2,3]` under
  `(0,0),(2,20),(4,60)`.
- [x] Verify independent calibration, owner checks, source/revision boundaries,
  save/reopen and actual legacy document files; preserve unrelated panel admission.
- [x] Regenerate API/build assets, qualify wheel/sdist and update validation records.
- [x] Finish final browser regression (59 workflows) and Python regressions (179 tests).
- [x] Commit and open [stacked draft PR #2](https://github.com/datasophos/ToFScope/pull/2) targeting `implement/react-fastapi-pilot`.
- [x] Initial GitHub CI passed, including independent package and Docker qualification.
- [x] Apply manual-testing UI refinements and add browser regressions for red errors,
  input contrast and main-page coordinate buttons; merged with PR #2. Subsequent
  control/layout fixes are merged with PR #3.

Evidence: [depth calibration qualification](../../validation/depth-calibration.md).

## Task 2: Atomic identification and explicit isotope measurements

**Files:** Create `application/identification.py`, `presentation/isotopes.py`, `frontend/src/identification/{IdentifyDialog.tsx,IsotopeMeasurements.tsx}`; extend commands/schemas/exports; create `tests/test_identification_application.py`, `frontend/e2e/identification.spec.ts`. Reuse `science/isotopes.py`, `abundance.py` and resource catalog.

**Interfaces:** `IdentificationService.candidates(owner, analysis_id, mz, tolerance, unit, charges)` uses `find_candidates`; annotation is a separate command from integration. `measure(owner, analysis_id, envelope, recipe_ids) -> JobSnapshot` uses the pilot job lifecycle and `measure_isotopes(path, recipes, roi, frames)`. Measurement records include captured scope and analysis/source dependencies.

- [x] Write failing tests for clicks snapping within seven display pixels to local maxima, exact input fallback, charges/polarity and catalog provenance. Add original intensity sums, common covered frames, unknown abundance, overlapping windows suppressing fractions, and preserved results marked out-of-date after ROI/window changes without automatic recomputation.
- [x] Run `test_identification_application.py` and `identification.spec.ts` to fail. Implement separate Annotate/Apply/Add comparison actions with exact limits, graphical spectrum feedback and explicit Measure. Reuse custom integration jobs rather than recomputing in React.
- [x] Preserve isotope CSV/settings metadata and original labels; distinguish signal ratios from quantitative composition. Run existing isotope/abundance numerical suites, new tests, resource-install smoke and API type regeneration to PASS. See [identification qualification](../../validation/identification.md) for verification and the saved-document schema-3 amendment.

## Task 3: Cross-sections and shared spatial selection

**Files:** Create `presentation/sections.py`, `frontend/src/sections/SectionsScreen.tsx`, `tests/test_section_data.py`, `frontend/e2e/sections.spec.ts`; extend data routes and panel union. Reuse numerical assertions from old `cross_section`/front-projection tests.

**Interfaces:** `SectionPresenter.snapshot(owner, analysis_id, direction: Literal['XZ','YZ']) -> SectionData` uses the same axis/coverage/intensity contract as Explore. Clicks emit the existing canonical frame command; ROI/window/calibration are analysis state rather than section-local copies.

- [ ] Write failing tests comparing exact original-resolution slices/reductions with the reference, ROI/window cropping, both axis orientations, unknown-depth coverage, and click roundtrips after unit changes. Browser tests switch Explore/sections with maximize/restore and no lost selections.
- [ ] Run the two new test modules to fail, implement payloads and React section screen, then run them with calibration/Explore regressions to PASS. Verify independent client zoom and cross-analysis isolation. Commit as `feat: add linked scientific cross-sections`.

## Task 4: Select and implement multi-layer volume rendering

**Files:** Create `docs/validation/spatial-renderer-decision.md`, `frontend/evaluation/SpatialProbe.tsx`, `presentation/volumes.py`, `frontend/src/volumes/{VolumeScreen.tsx,LayerEditor.tsx,spatialRenderer.ts}`, `tests/test_volume_data.py`, `frontend/e2e/volumes.spec.ts`; extend `science/volume_layers.py` caches to use application admission and generation invalidation.

**Interfaces:** `VolumePresenter.snapshot(owner, analysis_id, layer_ids, quality) -> VolumeData` wraps `build_layer_previews(..., voxel_budget=500_000, calibration=...)`. Payload includes original numerical values, validity masks, per-axis block coordinates and physical extent; styles/cameras don't trigger reconstruction. Rendering adapters consume this contract, not Python figure JSON.

- [ ] Write failing tests preserving Fast limits 96×32×32 and Detailed 160×48×48, valid partial-block means, unknown-depth clipping before pooling, and average calibrated coordinates across slope changes. Missing data is not zero. Combined displayed layer voxels never exceed 500,000; intermediate allocations also obey resource admission.
- [ ] Compare Plotly and vtk.js against the same registered-layer fixture: tiled/overlay, clipping, linked cameras, memory/latency, and exact nonuniform Z geometry. Do not map piecewise-calibrated depths to uniformly spaced voxels silently. Select an implementation that can represent supplied geometry without scientific resampling, or retain Plotly where vtk.js cannot; document evidence before the production adapter. Trame/remote rendering remains a separate architecture change if truly required.
- [ ] Implement stable per-layer recipes, visibility, Solo, colormap, opacity, percentile threshold, tile pagination four at a time, linked/independent cameras and independent/shared numerical scales. Frame stretch and calibrated exaggeration remain distinct; 1× preserves physical proportions when X/Y are known. Thin/constant selections use points.
- [ ] Run `test_volume_data.py`, existing `test_volume_layers.py`, new browser tests and installed-package smoke; compare real-acquisition payload/interaction measurements with the reference 32 MiB/200 ms context without claiming those figures cover every workload. Commit as `feat: add calibrated multi-layer volume visualization`.

## Task 5: Controlled native saves and cross-analysis invalidation

**Files:** Create `application/saves.py`, `api/save_routes.py`, `frontend/src/saves/SaveIntegrationDialog.tsx`, `tests/test_save_application.py`, `frontend/e2e/saves.spec.ts`; extend storage write tests, repository invalidation and job schemas. Read `docs/hdf5-compatibility.md` before implementing.

**Interfaces:** `SaveService.preview(owner, analysis_id, recipe_id) -> SavePreview`; `commit(owner, analysis_id, envelope, confirmation: SaveConfirmation) -> JobSnapshot`. Define both dataclasses in `application/saves.py`: `SavePreview(token, recipe_id, source_generation, relative_path, label, required_bytes, restrictions, expires_at)` and `SaveConfirmation(token, label)`; token binds server-owned reviewed recipe, source generation and destination and expires after five minutes. Ignore arbitrary client path/array/recipe substitutions. Dataset-scoped commit invalidates all affected analyses and marks them stale. Initiating analysis may explicitly reload/select the saved record only after successful commit.

- [ ] Write failing tests for both opt-ins required, stale preview rejection, ASCII/contiguous/full-coverage native restrictions, authorization, free-space checks, cooperative lock exclusion, sibling verification failure, retained backup and rollback before replacement. Use disposable synthetic/copied acquisitions only.
- [ ] Test two owners opening the same file and aliases: successful save invalidates every cache/analysis/job using that generation; a different file is unaffected. Before replacement cancellation can abort safely; after replacement record a successful durable outcome even if the initiating view closes or reload fails. Do not attempt to roll back a committed file merely to satisfy a client revision check.
- [ ] Run `test_save_application.py` to fail. Reuse `save_to_acquisition`, native validators, verified sibling copy, backups and replacement protections; do not reimplement persistence in a route. Add review UI, write policy/experimental status and saved-integrations listing. Preserve original full-XY values independently of ROI/log/preview settings.
- [ ] Run existing storage/vendor write tests and browser save workflow on disposable copies to PASS. Actual NFS lock/replacement qualification is required on the target mount before enabling writes. Numerical commercial round-trip/full save verification remains an explicit external check; preserve both flags until independently established evidence changes policy. Commit as `feat: expose controlled native saves with dataset invalidation`.

## Task 6: Verify complete replacement and update release scope

**Files:** Modify `README.md`, `docs/deployment.md`, `docs/hdf5-compatibility.md`, CI and distribution smoke suite; create `docs/validation/replacement-parity.md`.

- [ ] Map every reference workflow/assertion to a replacement test or an explicitly justified intentional behavior change. Include dialogs/peak-helper reset, physical depth in each view, volume layers and native save outcomes. No widget-only test should disappear without its behavior being accounted for.
- [ ] Run full numerical/application/API/frontend suites; build and independently install wheel/sdist; run new feature smokes without Node/CDNs/source checkout. Requalify simultaneous users/analyses with volume and save workloads and verify byte admission includes renderer-preview preparation and temporary save storage.
- [ ] Update release scope from Explore-only to the actually verified complete features, keep experimental write limitations visible, document measured deployment capacity and restart behavior, and retain the frozen reference instructions. Commit as `test: qualify the complete replacement workspace`.

## Handoff

Complete the pilot first. These feature tasks depend on its stable service and data contracts, but do not require gradual legacy migration or parallel maintenance. Durable workspace restoration, collaborative editing, multi-host/API-worker scaling and a renderer requiring remote infrastructure need separate requirements and plans; they are not hidden prerequisites of this replacement.

## File-centered persistence context (2026-10-19)

The separately approved file-centered analysis plan replaces user-facing workspace
groups and manual reattachment. Versioned saved HDF5 copies restore Explore signals,
custom results and selections. This is new-file output only: Task 5's controlled
native saves remain deferred, with their original opt-ins and deployment evidence
requirements. Calibration now extends the document to version 2 with version 1 read support.
Future identification/3D features must extend the saved document schema and
round-trip tests; their state is not yet implemented. Never
serialize pending drafts/jobs as completed numerical results.

### Visual conventions from Explore feedback (2026-10-20)

Preserve the original rounded corners, fills, shadows, typography, control
shapes and spacing. Keep functional button outlines visible. Remove only the
decorative thin rounded rectangular outline accents on containers,
including the thin accent shadow under the active file tab. Keep the original
circular help icons, keyboard focus indicators and scientific selection/axis
markings. Do not turn border removal into an app-wide flat-style redesign.
