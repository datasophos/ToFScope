# Profile Depth Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Implementation requires a separate user instruction; this plan is a proposed design.

**Goal:** Assign known physical depths to frames and interpolate profile depth between them.

**Architecture:** Keep acquisition frames as the analysis/navigation domain and add a separate immutable piecewise-linear coordinate calibration. A Frames/Depth profile toggle and anchor editor use forward/inverse transforms without resampling intensities.

**Tech Stack:** Python, NumPy interpolation, Plotly, AnyWidget, unittest, Playwright

**Spec:** [Roadmap design brief, section 6](../specs/2026-10-16-roadmap-design.md).

## Global Constraints

- Keep Marimo + AnyWidget + Plotly; do not introduce Panel.
- Treat frame limits as zero-based and inclusive.
- Do not change source HDF5 files except through explicit write-back.
- Preserve existing shared ROI, All depths, maximize/restore, and offline operation.
- Scientific transforms must not silently change analysis intensities.

## Dependencies and file boundaries

Independent of other plans. Create `depth_calibration.py` for the numerical model and `web/depth_editor.js` for anchor controls. If the signal recipe plan is present, add optional calibration metadata alongside its recipe; otherwise extend the existing JSON export without changing raw integrations.

## Review Focus

- Unsorted/duplicate frames and non-increasing depths must not create an ambiguous inverse transform (Task 1).
- Uncalibrated frames outside the anchors remain missing; no hidden extrapolation (Task 1).
- A nonzero loaded-frame origin must still select the correct acquisition frame (Task 2).
- Unit changes and incomplete anchor drafts must not change intensities or silently lose anchors (Task 3).
- Removing an anchor while the profile is maximized must leave a usable frame view if calibration becomes invalid (Tasks 2, 3).

### Task 1: Implement a reversible calibration model

**Files:** Create `depth_calibration.py`, `tests/test_depth_calibration.py`.

**Interfaces:** Frozen `DepthAnchor(frame: int, depth_nm: float)` and `DepthCalibration(anchors: tuple[DepthAnchor,...], acquisition_frames: int)`; `validate_anchors(...) -> tuple[DepthAnchor,...]`, `frame_to_depth(frames: np.ndarray) -> np.ndarray`, `depth_to_frame(depth_nm: np.ndarray) -> np.ndarray`, `convert_depth(value, source_unit, target_unit)`. Valid units are `nm`, `µm`, `mm` (accept `um` as input alias).

- [x] Write `test_piecewise_depth`: anchors `(0,0),(100,50),(300,250)` nm map frames `[0,50,100,200,300]` to `[0,25,50,150,250]`; inverse transformation recovers those frames. Fractional inverse frame coordinates are permitted before UI rounding.
- [x] Test fixed frame-zero/depth-zero origin, rejected negative depths, sorted input, duplicate/out-of-range/non-integer frames, non-finite values, non-increasing depths, and conversion of 1 µm to 1000 nm. Frames/depths outside the anchor span must return `NaN`.
- [x] Run `uv run python -m unittest discover -s tests -p 'test_depth_calibration.py' -v`; confirm failure, then implement validation and piecewise-linear interpolation with explicit out-of-span masking. The validator may retain one draft anchor; constructing an active `DepthCalibration` requires at least two. A single anchor is an inactive draft, not a constant-depth calibration.
- [x] Add JSON round-trip tests retaining canonical nm values, display unit and exact anchor frames. Verify unit conversion does not mutate original values.
- [x] Run the test module; require all expected coordinates and rejected inputs. Commit: `Add piecewise-linear frame-to-depth calibration.`

### Task 2: Add calibrated profile coordinates and exports

**Files:** Modify `workspace.py`, `plots.py`; create `tests/test_calibrated_profiles.py`.

**Interfaces:** Controller stores draft anchors, active `DepthCalibration|None`, and display axis (`frame`/`depth`). Profile figure metadata includes `axis_kind`, `unit`, calibrated span, and acquisition-frame customdata. Event payloads for selection still contain acquisition frames. CSV optionally adds `depth_nm` while preserving existing frame and signal columns.

- [x] Write tests showing the profile's intensity values are bit-identical with calibration on/off, including comparisons with missing frame coverage. Test loaded frames 100–300: plotting and inverse selection use absolute frames, not positions 0–200.
- [x] Test anchors inside the acquisition: calibrated view omits unmapped coordinates visibly and labels its partial span; CSV retains all selected frame rows and leaves uncalibrated depth cells empty. JSON records anchor/unit/interpolation/no-extrapolation metadata.
- [x] Run `uv run python -m unittest discover -s tests -p 'test_calibrated_profiles.py' -v`; verify failure, then pass optional calibrated X coordinates into `profile_plot`, preserving its existing frame-mode interface for callers without calibration.
- [x] Convert the frame marker and depth-window bands into display coordinates. Add conversion helpers used by pointer down/move/up; inverse-map, then round/clamp to valid inclusive acquisition frames. Disabling calibration returns to Frames without changing selected frames.
- [x] Run all numerical tests. Commit: `Display and export calibrated profile depths.`

### Task 3: Add anchor editing and linked navigation

**Files:** Create `web/depth_editor.js`, `scripts/check_depth_calibration.py`; modify `web/workspace.js`, `web/workspace.css`, `README.md`.

**Interfaces:** Events `depth_anchor_set {frame,depth,unit}`, `depth_anchor_remove {frame}`, `depth_unit {unit}`, `profile_axis {axis}`. Server validates the full candidate anchor set before replacing active calibration. A draft with fewer than two anchors deactivates calibration and returns the axis to frames.

- [x] Write a failing browser scenario: click a profile point, assign known depth, add a second and third anchor, switch units/axis, then select a depth range. Assert ion maps and 3D still receive the expected original acquisition frame limits.
- [x] Test duplicate frame rejection, unsorted table entry, removal to one anchor, All depths, partial calibration span, comparison persistence and maximize/restore. Rejected edits preserve the last valid calibration; removing an anchor is a deliberate state change.
- [x] Implement an anchor table in a compact dialog plus Add known depth at selected frame. Show Frames/Depth and units near the profile; put interpolation details in an info tooltip. Clearly identify a partial calibrated span without another permanent instruction paragraph.
- [x] Run `uv run python scripts/check_depth_calibration.py`, existing depth-window/all-depths/display checks, and numerical tests. Confirm 3D remains labeled in frames and its arbitrary stretch is unchanged; physical 3D geometry is outside this first deliverable.
- [x] Update README and commit: `Edit known-depth anchors from the profile.`

## Acceptance

Two or more known-depth anchors enable an invertible calibrated profile axis. Selection remains correct in the maps, intensities are unchanged, and CSV/JSON explain calibrated and uncalibrated frames explicitly.

## Confirmed scope and verification

The 2026-10-17 requirement fixes frame 0 at depth 0; arbitrary/negative origins
from the original proposal are excluded. One additional anchor activates depth
coordinates. Browser verification covers unsorted anchor entry, unit switching,
physical-range selection yielding original frames, export, maximized removal
back to Frames and All depths. The original layout and All depths checks passed.
Acquisition files remain read-only; physical 3D geometry remains separate.

Final review fixes: typed new-anchor and existing-row drafts now retain their
physical values through unit/axis changes; numerical values are stored in nm
until explicit Add/Update. Single finite calibrated samples show a marker. Each
regression was observed failing before the fix, and the full suite passed.
Deferred minor: the resize hover cursor still uses frame coordinates on the
calibrated axis; actual dragging uses the correct physical coordinates.
