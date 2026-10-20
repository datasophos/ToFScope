# Explore Signal Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace the Explore sidebar and active/comparison workflow with named signals, explicit display choices, a contextual spectrum editor, and plot-local controls.

**Architecture:** An analysis owns stable signal records independently of image/profile selections. Background calculations publish versioned recipes to signal IDs; presentation produces arrays and coverage without exposing reader or renderer internals. Focused React components consume the new contract, preserving per-analysis drafts and version-matched plot updates.

**Tech Stack:** Existing Python/FastAPI/dataclasses/Pydantic/NumPy/h5py services; React/TypeScript, existing ECharts adapter and raster renderer; unittest, Vitest and Playwright.

**Spec:** `docs/superpowers/specs/2026-10-19-explore-signal-workspace-design.md`

**Execution:** Inline, selected by Josh; retain `/private/tmp/tofscope-react-fastapi` on `implement/react-fastapi-pilot`. Implemented inline; numerical, browser, package and final-review checks pass.

## Global Constraints

- The application remains one installable Python service with bundled offline frontend assets.
- Retain the scientific reader and renderer independence, read-only acquisitions, bounded resource use, owner isolation, multiple files, and independent analyses of the same acquisition.
- Keep the frozen prototype checkout intact. Do not publish or deploy externally.
- Replace the old active_recipe/comparisons snapshot and destination commands wholesale.
- Replace the old interface in generated TypeScript, exports and tests together; do not build legacy adapters for this unreleased app.
- Missing coverage is never represented as zero.
- Bounds retain full numeric precision; formatting in summaries must not round-trip back into the scientific recipe.
- Log colors, relative profiles, and spectrum log Y remain defaults.
- Ordinary wheel continues to scroll the page.
- Plot-only state changes must not launch scientific jobs or trigger unrelated data fetches.
- Do not restart the user's live service as part of design work; deployment of the new backend requires a restart and resets temporary workspaces, which must be communicated explicitly.

## Review Focus

- Duplicate names and repeated stored-channel choices must preserve distinct IDs without accidentally creating duplicate rows; Task 1 tests both paths.
- Removing or changing coverage of the image signal must leave an eligible selection and valid depth bounds, including disjoint coverage; Task 1 pins those transitions.
- A rename or display change during a calculation must survive late completion, while deletion/supersession prevents publication; Task 2 controls completion with events.
- Delayed panel responses must never display new labels over old numerical data, including when the tab switches mid-job; Tasks 4 and 5 delay and reorder actual responses.
- A hidden or failed signal must not bypass quotas or retain unbounded volumes; Tasks 1, 2 and 7 check pending/hidden admission and released reservations.

## File and interface map

- `application/models.py`: immutable `SignalSnapshot` and replacement `AnalysisSnapshot` fields.
- New `application/signals.py`: signal lookup, coverage, selection normalization, and display invariants.
- `application/commands.py`, `explore.py`, `workspaces.py`: validated commands, owner-scoped transitions and collection admission.
- `application/jobs.py`: signal-targeted scheduling and atomic result publication.
- `presentation/data.py`, `explore.py`, `exports.py`: signal-aware plots, coverage, identifying labels and export schema.
- `api/schemas.py`, `api/app.py`: new job input and replacement snapshot contract.
- `frontend/src/app/useAnalysis.ts`: revision-aware command and panel lifecycle.
- New `frontend/src/explore/useSignalEditor.ts`: local draft and submitted-job state.
- New `SignalTray.tsx`, `SignalDetails.tsx`, `SignalEditor.tsx`, `ViewingDepths.tsx`, `ROIControls.tsx`, `AnalysisSettings.tsx`: focused UI responsibilities under `frontend/src/explore/`.
- `ExploreScreen.tsx`: compose these units; retain file/tab integration.
- `plots/PlotPanel.tsx`, `SelectionOverlay.tsx`: local controls, interactive legend and explicit select/zoom modes; keep raster/renderer boundaries.
- `scripts/check_distribution.py`, `qualify_pilot.py`, `check_real_browser.py`, `check_integration_performance.py`: update qualification consumers of the replaced interfaces.

Backend contract work in Tasks 1–3 is one coordinated replacement. Do not retain adapters merely to keep old clients working between commits. Run each task's focused tests; restore the entire backend suite by Task 3 and the entire frontend suite by Task 6 before packaging.

### Task 1: Signals and independent display selections

**Files:** Modify `src/tofscope/application/{models,commands,explore,workspaces}.py`, `src/tofscope/config.py`; create `src/tofscope/application/signals.py`, `tests/test_signal_workspace.py`, `tests/test_config.py`; update `tests/test_analysis_state.py` and `tests/test_analysis_lifecycle.py`.

**Interfaces:**
- Produce `SignalSnapshot(id: str, name: str, style_index: int, recipe: SignalRecipe | None, recipe_version: int, name_revision: int, job_id: str | None)`.
- Replace snapshot `active_recipe`/`comparisons` with `signals: tuple[SignalSnapshot, ...]`, `image_signal_id: str`, `profile_signal_ids: tuple[str, ...]`, `next_style_index: int`; retain the analysis frame range as `loaded_frames` internally, labeled Analysis frame range in UI.
- Produce `get_signal(snapshot, signal_id) -> SignalSnapshot`, `image_signal(snapshot) -> SignalSnapshot`, `visible_signals(snapshot) -> tuple[SignalSnapshot, ...]`, `image_frames(snapshot) -> tuple[int, int]`, and `normalize_view(snapshot) -> AnalysisSnapshot` in `signals.py`.
- `ExploreService.apply(owner, analysis_id, CommandEnvelope) -> AnalysisSnapshot` remains the mutation entry point. Add commands `add_stored_signal(index, duplicate=False)`, `rename_signal(signal_id, name)`, `select_image_signal(signal_id)`, `set_profile_visible(signal_id, visible)`, `remove_signal(signal_id)`, `set_stored_coverage(signal_id, frames)`; retain ROI/depth/display commands and rename `set_loaded_frames` to `set_analysis_frames`.
- Replace comparison count policy with `signals_per_analysis=129`, `signals_per_user=512`, `signals_global=2048`; all include pending and hidden records. These are record quotas, not permission to exceed existing byte budgets. Names trim surrounding whitespace, require 1–128 characters.

- [x] Write service tests named `test_stored_add_deduplicates_unless_explicit_duplicate`, `test_display_selection_preserves_signal_identity`, `test_disjoint_coverage_and_image_removal`, `test_names_and_styles_survive_selection_and_removal`, `test_hidden_and_pending_signals_count_toward_limits`, `test_owner_and_same_file_analysis_isolation`.
  Assert duplicate=False reuses an ID and reveals its profile; duplicate=True creates a new ID/style. Two names may be equal. Empty/whitespace/129-character names fail. Selecting a new image preserves the old image's profile visibility. Hiding the current image is rejected. Removing the final eligible image is rejected atomically. Disjoint signals cannot become images. Frame/window selections intersect usable coverage or fall back to the first usable frame, without changing recipes. At exact quota admit once, then reject without allocating another record.
- [x] Run `.venv/bin/python -m unittest discover -s tests -p test_signal_workspace.py -v`; verify failures identify the missing signal contract.
- [x] Implement the interfaces and commands above. Seed the existing nominal-27 default as one stored signal with style 0 and version 1. Preserve monotonic style allocation and owner-scoped locks/receipts. Count records under a consistent collection lock; release cache leases for hidden/removed entries rather than pinning all volumes. Analysis range changes never rewrite recipes; reject a range with no eligible ready image signal rather than silently selecting invalid coverage.
- [x] In `tests/test_config.py`, pin defaults 129/512/2048 and reject nonpositive quota values. Run the new tests plus `test_analysis_state.py`, `test_analysis_lifecycle.py`, `test_config.py`, `test_auth.py` and `test_dataset_invalidation.py`; migrate their actual expectations to the replacement contract and retain scientific/owner assertions.
- [x] Commit: `Introduce analysis signals with independent display selections.`

### Task 2: Signal-targeted calculations and atomic publication

**Files:** Modify `src/tofscope/application/jobs.py`, `src/tofscope/api/schemas.py`, `src/tofscope/application/workspaces.py`; update `tests/test_jobs.py`; create `tests/test_signal_jobs.py`.

**Interfaces:**
- Replace `IntegrationSpec.target` with `IntegrationSpec(intervals, frames, name, signal_id: str | None = None, expected_recipe_version: int | None = None)`; omitted ID creates a signal, supplied ID updates a custom signal. Names follow Task 1 validation.
- Produce job snapshots with existing status/progress/error plus `signal_id: str`, `recipe_version: int`; `submit(owner, analysis_id, envelope, spec) -> JobSnapshot` retains request idempotency. No active/comparison target survives.
- Use signal-specific generation tokens in `AnalysisEntry`; a signal's last committed recipe/version remains available during an update. Reserve pending row identity, style and quota atomically with job acceptance.

- [x] Write event-controlled tests `test_new_signal_calculation_preserves_image_choice`, `test_failed_update_retains_committed_values`, `test_rename_and_roi_during_job_survive_commit`, `test_delete_replace_close_and_supersede_discard_late_results`, `test_retry_reuses_pending_row_and_job`, `test_failed_pending_and_hidden_records_cannot_bypass_quota`.
  Assert queued/running IDs appear in snapshots, new rows have recipe=None until success, successful new rows join profiles only, updates retain IDs/styles and increment committed recipe version once. Rename after submit wins over the submitted name. Display/ROI edits do not obsolete a job. Failure/cancel preserves old recipe/name; no partial array is published. Repeated request ID creates one job/row, and stale expected recipe versions conflict. A failed new signal is retryable using its existing ID and version 0 without adding another row.
- [x] Run `.venv/bin/python -m unittest discover -s tests -p test_signal_jobs.py -v`; confirm the missing lifecycle fails.
- [x] Implement signal-token admission/publication while retaining fair round-robin scheduling, limits, cancellation, bounded packed-event buffers, source-generation checks and sanitized errors. Keep submitted name revision for conflict-free rename publication. Retain a terminal job reference on failed rows; retries replace it. Unlink/cancel jobs and release leases on removal. Normalize the viewing selection after a successful image-signal update.
- [x] Run `test_signal_jobs.py`, migrated `test_jobs.py`, `test_bounded_events.py`, `test_array_cache.py`, `test_dataset_invalidation.py`; assert released reservations after failure/cancel/remove/close and successful equal output for interval unions.
- [x] Commit: `Publish calculations atomically to versioned signals.`

### Task 3: Signal-aware data, API and exports

**Files:** Modify `src/tofscope/presentation/{data,explore,exports}.py`, `src/tofscope/api/{app,schemas}.py`; update `tests/test_explore_data.py`, `tests/test_api.py`, `tests/test_review_regressions.py`, `tests/test_distribution.py` and remaining Python callers; regenerate `frontend/openapi.json`, `frontend/src/api/generated.ts`; update `frontend/src/api/client.ts`.

**Interfaces:**
- Replace `Curve.recipe_id` with `signal_id: str`, `style_index: int` and `label: str`; keep `values` and `coverage`. Labels identify name, source and coverage when needed to distinguish rows; duplicate names include a short stable ID suffix.
- `ExplorePresenter.curves(snapshot, stack)` iterates image first, then other visible signals in tray order, using committed recipes only. Panel content versions incorporate relevant signal IDs/recipe versions/names/display state.
- API routes retain revision envelopes, ownership and error conventions. `build_services.prepare` loads only the initial image signal. Expose the new dataclasses and job schema through existing API routes, with no reader/plot library fields.
- Settings JSON schema 4 contains `signals`, `image_signal_id`, `profile_signal_ids`, analysis/view frame bounds, ROI and display state. Export committed signals only; include no pending recipe as a successful result. CSV remains raw visible profile values with the existing selected-window scope and null gaps.

- [x] Write/extend `test_signal_data_and_exports_preserve_numerics`, `test_partial_coverage_and_image_frame_intersection`, `test_api_rejects_foreign_signal_and_legacy_target`, `test_hidden_signal_retained_in_settings_not_csv`.
  Assert stored arrays, exact ROI means and front sums equal existing fixtures; null coverage aligns to analysis range; display normalization changes no CSV values. Hidden records appear in JSON, pending uncommitted recipes do not. API rejects active/comparison job payloads and foreign signal IDs. Partial response content versions change only affected panels.
- [x] Run `.venv/bin/python -m unittest discover -s tests -p test_explore_data.py -v` and `test_api.py`; confirm the contract/presenter tests fail before implementation.
- [x] Implement the interfaces, source checks and budgeted exports. Reuse scientific read/cache keys without incorporating names, visibility or style. Correct front-axis alignment for partial image coverage while retaining the full analysis domain with missing data represented as null. Update all backend test callers without reducing assertions.
- [x] Run `.venv/bin/python -m unittest discover -s tests` to a clean pass. Run `npm run generate:api` from `frontend`; verify generated types reflect the replacement snapshots, curves and submit input. Update client aliases for `SignalSnapshot` and the new schema.
- [x] Commit: `Expose signal-aware plots and complete analysis exports.`

### Task 4: Local draft state and version-safe frontend updates

**Files:** Create `frontend/src/explore/useSignalEditor.ts`, `frontend/src/explore/signalEditorState.ts`, `frontend/src/explore/signalEditorState.test.ts`; modify `frontend/src/app/useAnalysis.ts`, `frontend/src/api/commandQueue.ts` only if its envelope typing requires it; create `frontend/e2e/signal-races.spec.ts` alongside existing race tests.

**Interfaces:**
- `SignalDraft = { signalId?: string; name: string; intervals: [string,string][]; selectedInterval: number; frames: [string,string]; baseline: string; submittedJobId?: string }` keeps exact input strings locally.
- `useSignalEditor(analysis: Analysis, refresh: () => Promise<void>)` returns draft, pending switch, job, error, `openNew()`, `openEdit(signalId)`, `openCopy(signalId)`, `patchDraft(patch)`, `requestClose()`, `keepEditing()`, `discardAndContinue()`, `submit()`, `cancel()`, and `dismissError()`. Successful completion clears only the submitted draft; terminal failure unlocks it for retry.
- `useAnalysis` additionally returns `pendingPanels: Set<string>` and panel-associated display metadata so titles/legends refer to the snapshot that produced the displayed arrays. Changed metadata cannot silently relabel an older panel. Poll authoritative jobs for the current analysis even after browser refresh; do not attempt to restore an unsaved draft from server state.

- [x] Add reducer tests asserting full-precision input preservation, duplicate seeding, dirty-switch keep/discard, job freeze/unlock, and late terminal events for a previously discarded draft leaving a newer draft unchanged. Add browser race tests delaying old panel responses across recipe update, image selection and analysis-tab switching; assert matching data labels or a visible Updating state.
- [x] Run `npm test -- signalEditorState.test.ts` and the new browser race test with a minimal current UI fixture; confirm missing state behavior fails.
- [x] Implement the interfaces and submit using a stable request ID across a network retry. Compare committed signal recipes and visible IDs when selecting panels to refresh. Rename affects labels without rereading scientific volumes. Only matching analysis/generation/revision responses update current panels; omitted panels remain pending until fetched. Preserve existing leases, stale-source handling and partial-response race protection.
- [x] Run `npm test` and browser race tests after Task 5 provides the UI cutover. Keep reduced test fixtures in test code, not production classes.
- [x] Commit: `Separate signal drafts from committed plot state.`

### Task 5: Tray, contextual spectrum editor and plot-local controls

**Files:** Create `frontend/src/explore/{SignalTray,SignalDetails,SignalEditor,ViewingDepths,ROIControls,AnalysisSettings}.tsx`; replace sidebar composition in `ExploreScreen.tsx`; modify `frontend/src/plots/{PlotPanel,SelectionOverlay}.tsx`, `frontend/src/explore/help.ts`, `frontend/src/styles.css`; retain `SignalPicker.tsx`, `CurveMarker.tsx` and `plots/curveStyle.ts`.

**Interfaces:**
- `SignalTray({analysis, send, editor})`: send uses `useAnalysis.send`, editor uses Task 4; renders Images radio group, Profile checkboxes, stable style-index markers, details/actions, pending progress and four-row scrolling body with sticky column labels.
- `SignalEditor({editor, analysis})`: exact name/interval/frame controls, Create/Edit copy, read-only submitted state, progress/cancel and inline error/dirty-switch actions. It renders beside the spectrum on desktop and above it on narrow screens; spectrum maximize includes its editor.
- `ViewingDepths({analysis, send})`, `ROIControls({analysis, send})`, `AnalysisSettings({analysis, send})`: shared viewing selection, plot-local ROI popover and advanced analysis range respectively. Use Task 1 normalized bounds.
- `PlotPanel` receives `controls?: ReactNode`, `status?: ReactNode`, `legendActions?: {onDetails(id), onVisibility(id,visible), imageSignalId}` and `selectionMode: 'select' | 'zoom'`; profile markers derive from each curve's stable style_index. `SelectionOverlay` maps draw gestures to onZoom in zoom mode and keeps edge/move selection behavior in select mode.

- [x] Write browser tests `signal-workspace.spec.ts` for stored add/dedup, custom creation without image replacement, explicit Show in images, hide/restore, rename/details, custom copy/duplicate/edit, stable colors and last-eligible removal. Add `signal-editor.spec.ts` for view-mode drag zoom, explicit editing mode, union intervals, full precision, dirty switching, successful close, failed retry, cancel and independent drafts in two tabs.
- [x] Run the tests against the pre-cutover UI to observe missing tray/editor controls. Use actual fixtures and event/response waits, not arbitrary sleeps.
- [x] Implement the component interfaces. Remove the target selector, permanent mass form, active/comparison labels and sidebar CSS. Attach ROI/log/SIMS-SE to the image, relative scaling to profile, spectrum controls/editor to the spectrum and infrequent analysis range to Analysis settings. Identify image/front signal and resolved frame bounds; show unregistered SE/native axes explicitly. Keep contextual help and focus-return behavior. Disable pending display choices, explain disabled required profile/Remove controls, and use named accessible inputs.
- [x] Run `npm run typecheck`, `npm test`, and all signal browser tests plus Task 4 race tests. Verify existing offline acquisition open/tabs, PNG legends, Ctrl/Cmd-wheel, ordinary page scrolling, Escape and keyboard navigation still work.
- [x] Commit: `Replace the sidebar with a signal tray and contextual tools.`

### Task 6: Responsive interactions and regression qualification

**Files:** Update existing `frontend/e2e/{explore,concurrency,races,help,profile-legend,selection-visibility}.spec.ts`; replace `sidebar-height.spec.ts` with `signal-layout.spec.ts`; update `renderer.spec.ts` harness consumers if the overlay prop changes. Modify production UI only for failures justified by these checks.

**Interfaces:** Consume the completed API and UI from Tasks 1–5; preserve renderer adapter `mountChart`/`ChartData` independence and imageRaster caches.

- [x] Write `signal-layout.spec.ts` assertions at 1600×900 and 600×800: four-row tray scroll, visible column labels, card labels, no document horizontal overflow, editor access in maximized spectrum, exact ROI/settings popovers remaining reachable, and focus restoration after close. Test long/duplicate names and partial frame coverage.
- [x] Run the new layout tests and adapted regressions; identify actual failures rather than preserving tests for removed sidebar concepts.
- [x] Correct layout/focus issues with scoped CSS/components. Preserve square image stages from first render and the image-left/curve-right proportions. Keep one-pixel selection outlines and transparent 12-pixel edge targets. Replace fixed Active prefixes in legends/exports with signal names and explicit image-role indication without recoloring curves.
- [x] Run `npm run typecheck`, `npm test`, `npm run test:e2e`. Keep full-size 1301×128 image maximize/restore under the existing 200-ms regression bound and assert no data fetch. Add resident-signal image switching checks asserting zero integration-job submissions and no spectrum refetch; report its measured latency without inventing a cross-machine guarantee.
- [x] Commit: `Qualify responsive signal interactions and preserve plot performance.`

### Task 7: Bundled deployment, real-data evidence and documentation

**Files:** Update `scripts/{check_distribution,qualify_pilot,check_real_browser,check_integration_performance}.py`; update `docs/validation/pilot-qualification.md`, `docs/react-fastapi-migration.md`, relevant launch docs and completion-plan context; regenerate `src/tofscope/static/` through the existing builder. Add `docs/validation/signal-workspace-qualification.json` for machine-readable results.

**Interfaces:** Keep the existing script CLI arguments where feasible; replace their old UI/API actions with the approved signal flow. The performance comparison still measures the same scientific integration, independent of its display destination. Read script `--help` before invocation to use actual artifact/output arguments.

- [x] Adapt installed-package smoke assertions to create a signal, switch it to images, show/hide profile curves and download schema-4 settings/CSV/PNG. Require actual offline browser requests and no Node runtime, as in the existing smoke. Retain explicit wheel and sdist checks and denied acquisition writes.
- [x] Run the adapted smoke against stale bundled assets to prove it detects the removed contract; do not mistake missing build prerequisites for a functional red test.
- [x] Regenerate API types if further contract changes occurred, run `.venv/bin/python -m unittest discover -s tests`, frontend typecheck/unit/browser suites and `python3 scripts/build_frontend.py`. Build fresh wheel/sdist with `.venv/bin/python -m build --outdir /private/tmp/tofscope-signal-artifacts` (use an empty task-specific artifact directory), then run `.venv/bin/python scripts/check_distribution.py --artifacts /private/tmp/tofscope-signal-artifacts --output /private/tmp/tofscope-signal-distribution`. Do not publish artifacts externally.
- [x] If the provided acquisition is readable, run updated read-only qualification and the existing frozen-prototype integration comparison; record signal switching/request counts, exact output equality, managed budget behavior, owner isolation and source inode/size/mtime. Never edit the originals. Report unavailable files, hardware, NFS or services as blocked/unverified separately from passing checks. Do not rerun expensive work after a pass unless a new change or unresolved failure justifies it.
- [x] Document the new launch/workflow and schema; mark this plan's completed steps with command/result evidence. Update future-feature context without claiming completion of calibration, identification, 3D or acquisition saves. Run `git diff --check`, inspect all changes, verify frozen checkout clean, and commit `Package and qualify the signal workspace redesign.`

## Final review and handoff

- [x] Review the complete diff against every acceptance item in the spec; resolve all issues in scope and rerun affected checks.
- [x] Obtain the required final branch review using the available reviewer workflow. If a skill authorizes a fresh reviewer, bound it to review; preserve inline implementation.
- [x] Report launch instructions, concrete passing/blocked results, remaining limits, commit IDs and plan/spec updates. Keep the user's current service running until implementation is ready; any restart must explicitly communicate the reset of temporary analyses. Do not merge, publish releases or deploy externally without authorization.

## Plan self-review

The seven tasks cover all spec sections: model and coverage (1), asynchronous
publication and quotas (1–2), numerical/API/export invariants (3), draft and data
races (4), primary UI/gestures/contextual controls (5), accessibility/layout and
performance (6), and offline packaging/real-data documentation (7). Review-focus
conditions have named tests in the owning tasks. The quota configuration test is a new file (the repository has no
`tests/test_config.py` yet). Distribution invocation uses the verified
`--artifacts` and `--output` arguments. New interfaces are defined once
and consumed by later tasks; obsolete contracts are replaced rather than adapted.
