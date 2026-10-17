# Disjoint Integration Windows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Implementation requires a separate user instruction; this plan is a proposed design.

**Goal:** Combine multiple mass intervals into one reproducible active signal or comparison.

**Architecture:** Introduce a shared immutable signal recipe and a union-based raw integrator. Preserve the existing single-window API while migrating the controller and spectrum editor to an interval list. This plan supplies the recipe interface used by 3D, identification and write-back.

**Tech Stack:** Python, NumPy, h5py, AnyWidget, Plotly, unittest, Playwright

**Spec:** [Roadmap design brief, section 4](../specs/2026-10-16-roadmap-design.md).

## Global Constraints

- Keep Marimo + AnyWidget + Plotly; do not introduce Panel.
- Treat frame limits as zero-based and inclusive.
- Do not change source HDF5 files except through explicit write-back.
- Preserve existing shared ROI, All depths, maximize/restore, and offline operation.
- Scientific transforms must not silently change analysis intensities.

## Dependencies and file boundaries

No other roadmap feature is required. `signals.py` owns identity/serialization/dispatch; `integration.py` owns numerical interval operations. Keep `explorer.py`'s low-level raw timing and I/O functions; do not move the complete controller into a new framework.

## Review Focus

- Overlapping intervals and shared inclusive endpoints must not double-count an event (Task 1).
- An interval containing no mass-axis bin produces zero signal, not an invalid index (Task 1).
- Applying an empty list or out-of-axis bounds leaves the current signal intact (Tasks 1, 3).
- Partial frame coverage remains missing outside the reconstructed span (Task 2).
- Dragging/editing one interval must not leave ghost shapes or change other intervals (Task 3).

### Task 1: Define recipes and exact union integration

**Files:** Create `signals.py`, `integration.py`, `tests/test_window_sets.py`; modify `explorer.py`, `tests/test_data.py`.

**Interfaces:** `SignalRecipe` has the exact fields in the design brief and `to_dict() -> dict`, `from_dict(value: dict) -> SignalRecipe`. Add `canonical_intervals(intervals: Iterable[tuple[float,float]], axis_limits: tuple[float,float]) -> tuple[tuple[float,float], ...]` and `integrate_event_windows(events, mass_axis, clock_ratio: int, normalization: float, intervals) -> np.ndarray` in `integration.py`.

- [x] Write `test_union_counts_overlap_once`: masses `[0,1,2,3,4,5]`, events at sample bins `[1,2,2,3,4]`, windows `[1,2]` and `[2,4]`, normalization 2; one pixel must yield 2.5. Add `test_gaps_stay_excluded` with windows `[1,2]`, `[4,5]` (result 2.0 for those events).
- [x] Add rejection tests for empty/non-finite/reversed/out-of-axis intervals; a valid gap between mass bins must yield zero. Test sorted canonical output, touching endpoints, recipe JSON round-trip and conversion of schema-2 `lower_Th`/`upper_Th` into one interval.
- [x] Run `uv run python -m unittest discover -s tests -p 'test_window_sets.py' -v`; verify new-feature tests fail before implementation.
- [x] Implement the interfaces. Build one boolean membership mask over the calibrated mass axis; map each event once, then use the existing ragged per-pixel accumulation. Delegate existing `integrate_events` to a one-interval union without altering normalization.
- [x] Run the new tests plus `test_data.py`; require identical existing one-window results. Commit: `Add reproducible union-based mass-window recipes.`

### Task 2: Reconstruct composite signals and preserve coverage

**Files:** Modify `signals.py`, `integration.py`, `explorer.py`, `workspace.py`; create `tests/test_signal_recipes.py`.

**Interfaces:** `integration.custom_peak_windows(path, intervals, first: int, last: int, progress=None) -> np.ndarray`; `signals.read_signal(path, recipe: SignalRecipe, progress=None) -> np.ndarray`. `explorer.custom_peak(...)` remains the existing single-interval wrapper. The raw reader owns normalization metadata; `signals.py` does not duplicate it. `read_signal` returns exactly `recipe.frames` in `(depth,y,x)` order with absolute frame origin recorded by the recipe. Keep imports between legacy wrappers and new integration functions local to the wrapper/function, so delegating from `explorer.py` does not introduce an import cycle with its timing helpers.

- [x] Write tests for a synthetic three-frame HDF5 event list: one interval matches the old reader exactly; two intervals are accumulated in one frame pass; progress reaches the requested frame count; the extra trailing raw write is excluded.
- [x] Test a recipe covering frames 10–12 against active frames 9–13: samples at 9 and 13 must remain missing in profile/export adapters, not zero. Rename/color changes must not invalidate numerical cache keys; interval changes must.
- [x] Run `uv run python -m unittest discover -s tests -p 'test_signal_recipes.py' -v`; verify failure, then implement streaming reconstruction and `read_signal` dispatch for stored/custom recipes. Reserve the saved-reader dispatch for the write-back plan and report unsupported saved references clearly until it exists.
- [x] Migrate active/comparison state to recipes through adapters. Keep integer frontend comparison IDs separate from recipe UUIDs, retain legacy scalar low/high fields only for single-interval compatibility, and export schema 3 with complete interval lists.
- [x] Run all numerical tests and existing comparison browser checks. Commit: `Support composite signals across maps profiles and exports.`

### Task 3: Add an explicit multi-interval spectrum editor

**Files:** Modify `web/workspace.js`, `web/workspace.css`, `workspace.py`, `plots.py`, `README.md`; create `scripts/check_window_sets.py`.

**Interfaces:** Events `interval_add`, `interval_select {id}`, `interval_update {id,bounds}`, `interval_remove {id}` update a draft recipe only. Existing Apply/Add comparison actions receive the complete draft recipe and frame bounds. Put interval-editor logic in `web/interval_editor.js` if the widget module would otherwise grow substantially; use its local relative import through the existing AnyWidget module loader and verify offline loading.

- [x] Write a failing browser scenario: draw interval 26.8–27.2, add a second 47.8–48.2 interval, edit/remove one, then Apply and add the composite as a comparison. Check visible interval rows and each authoritative spectrum band after every action.
- [x] Test removal of the last interval disables Apply, a rejected interval preserves the active signal, and drawn coordinates on a maximized spectrum remain correct after restore. Comparison bands must not become editable draft intervals.
- [x] Implement selected-interval drag/edge/Shift-drag behavior, Add interval and row remove controls. Render the interval list as the source of truth; prevent Plotly edit persistence from recreating deleted bands. Show a union summary rather than one misleading bounding window.
- [x] Run `uv run python scripts/check_window_sets.py`, `scripts/check_spectrum.py`, `scripts/check_comparisons_layout.py`, and `scripts/check_roi_replacement.py` with the app running; require PASS. Verify CSV intensities against independently accumulated synthetic events and JSON contains both intervals.
- [x] Update documentation and commit: `Add direct editing of disjoint integration windows.`

## Acceptance

One composite signal with two separated intervals works as the active image/3D source and as a comparison; overlap is counted once, gaps are excluded, and its full recipe survives serialization. No acquisition file is modified.

## Completion notes — 2026-10-16

Implemented on `feature/disjoint-integration-windows`. Final review found and
resolved an immediate row-selection/Apply race and float32 mass-boundary
rounding. Regression checks first reproduced each failure, then passed after
the fixes. Numeric fields now preserve entered precision through Apply/export.

Verification: all 34 unittest tests and `marimo check app.py` passed. Browser
checks passed for disjoint-window editing, immediate selection/Apply and
comparison creation, precise bounds, spectrum gestures, comparison/layout,
ROI replacement, the original integration/export workflow, and All depths.

Implementation decisions:

- Draft rows retain stable identities; Apply canonicalizes their union.
- Legacy stored recipes without a channel index require reselecting a stored
  channel, avoiding substitution of raw reconstruction for vendor counts.
- The interval editor loads from locally synced source through a Blob module,
  preserving offline operation without an asset server or CDN.
- Saved-signal reading remains deferred to the HDF5 write-back plan. Acquisition
  files remain read-only. This completes the disjoint-window item only.
