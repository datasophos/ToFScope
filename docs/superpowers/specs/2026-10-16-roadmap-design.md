# ToFScope roadmap design brief

Status: execution approved; confirmed requirements dated 2026-10-17 in the roadmap index override earlier proposals.
Source requirements: [TODO.md](../../../TODO.md). Inspect the current working tree, including the full-window UI changes after commit `54057cb`, before executing.

## Current architecture and evidence

- `explorer.py`: read-only HDF5 access, contiguous raw-event integration, channel caching, ROI conversion and volume previews.
- `workspace.py`: AnyWidget controller, active channel, stored/custom comparison descriptors, figure construction and CSV/JSON exports.
- `plots.py`: Plotly figures; one 3D signal with block-mean previews and arbitrary Z stretch.
- `web/workspace.js` and `.css`: tabbed workspace, spectrum/depth gestures, image toggle, shared ROI, maximize/restore and tooltips.
- `app.py`: Marimo entry point; `TOF_FILE` selects the initial acquisition.
- Existing validation uses `unittest` and Playwright with installed Chrome. Keep those tools.
- Read-only inspection of the supplied AlTiPt file found `PeakData/PeakData` shape/maxshape `(1301,128,128,217)` and fixed contiguous `PeakTable` shape/maxshape `(217,)`. Neither can grow in place with a simple resize. The raw event array has 1302 writes; only the 1301 stored acquisition frames are supported.

## Global constraints

- Keep Marimo + AnyWidget + Plotly; do not introduce Panel.
- Treat frame limits as zero-based and inclusive.
- Do not change source HDF5 files except through explicit write-back.
- Preserve existing shared ROI, All depths, maximize/restore, and offline operation.
- Scientific transforms must not silently change analysis intensities.

## 1. Multi-peak 3D mapping

Users choose active and comparison signals as independently enabled 3D layers. Offer tiled views and an overlay, with per-layer colormap, threshold, opacity and visibility. Start with Plotly; prove multiple-volume performance on the actual client browser before choosing a new renderer. Tiles may use linked or independent cameras; overlays always share coordinates.

Layer coordinates use acquisition frame numbers and pixel/FOV geometry, never array offsets. Partial frame coverage stays missing. Use one common block grid and validity-aware means so corresponding voxels agree geometrically. Relative profile scaling does not affect 3D. Independent intensity scales are the default; a shared numerical scale is an explicit option for comparable intensity units. Discrete one-color ramps may be easier to distinguish in overlays, but users can choose sequential ramps.

Tiled mode shows at most four scenes per page, with paging and persistent layer/camera state; this bounds browser WebGL context use without capping the number of configured layers. Overlay mode uses one scene. Use a configurable total preview budget (initial proposal: 500,000 voxels across visible layers) rather than retaining full-resolution browser data or imposing a fixed layer-count cap. The UI reports actual preview resolution. Occlusion means a transparent overlay is qualitative; tiled views remain available.

## 2. On-server file browser

Introduce immutable server settings with a data root on a POSIX filesystem (including an NFS mount), initial acquisition and write permission. Environment variables: `TOFSCOPE_DATA_ROOT`, existing `TOF_FILE`, and `TOFSCOPE_ALLOW_WRITES` (default false). When `TOFSCOPE_DATA_ROOT` is absent, the local demo root is `DEFAULT_FILE.parent` and the default initial file is `DEFAULT_FILE` if it exists. When a root is explicitly configured and `TOF_FILE` is absent, start unloaded in the browser. An explicit `TOF_FILE` must resolve inside the root or fail with a configuration error. Deployment instructions require explicitly setting the root.

The browser sends root-relative paths. Resolve and enforce the configured root for every listing, opening and future write operation, including legacy text-path events. Allow symlinks only when their resolved target stays under the root. Hide temporary/backup/internal files. The configured root is managed by a trusted server administrator; a root writable by hostile local processes needs additional filesystem isolation.

List one directory at a time, paginated, with breadcrumbs and name filtering; open HDF5 only after selection. An empty root or an omitted initial acquisition opens a usable empty browser state. Display permission and malformed-file failures without replacing the current dataset. This feature does not by itself introduce remote authentication or a multi-user hosting service.

## 3. HDF5 write-back

Two levels must be distinguished:

1. First deliverable: save recipe, full-XY integrated volume for its explicit frame coverage, provenance, and optional calibration into `/ToFScope/Integrations/<uuid>` in the same acquisition file. ToFScope discovers these records on reopening. Existing vendor groups remain unchanged.
2. Required acceptance milestone: export into native `PeakData` after proving exact vendor/reader schema requirements. Commercial ToF-Explorer must discover the saved channels; a namespaced extension alone does not meet the requirement. Existing readers and commercial software are not assumed to discover the namespaced extension. A disjoint recipe cannot be honestly represented by one lower/upper bound spanning its gaps.

Default mutation strategy: acquire a per-file inter-process lock, check source identity, make a backup and sibling temporary copy, modify and verify the temporary file, recheck identity, and replace the original path with `os.replace` on the same filesystem. This is copy-and-replace at the original path, not an in-place HDF5 transaction. It preserves the original on ordinary pre-replacement failures, at the cost of disk space and time. Validate actual filesystem replacement/locking behavior before enabling it on a network or cloud-synchronized volume; no crash-durability claim is made beyond the tested environment.

Check free space for two source-sized copies plus the new result before starting. Preserve file permissions; document that ownership, hard links, ACLs and external links require compatibility review. Preserve relative-link location by placing the temporary file beside the acquisition. Do not modify external linked files. Fail closed on unsupported layouts. Writes are disabled until configured, and require an explicit Save action with an exact target/recipe summary.

Record source identity when a volume is loaded/reconstructed, not only when Save is clicked; reject saving stale prepared data. Coordinate server reads with the same file lock during replacement, invalidate caches, and mark other open sessions stale. Use one process-local lock-object registry per canonical path so nested reads by a writer are reentrant rather than acquiring a second independent lock object. A lock only coordinates cooperating processes; acquisition/commercial applications must close the file before save. Never disable HDF5 locking to force a write.

## 4. Multiple disjoint integration windows

A custom signal can contain a union of mass intervals. All endpoints are inclusive, overlap/shared endpoints count each event once, and gaps contribute nothing. This is independent of comparing several signals: a composite signal may itself be one comparison or one 3D layer.

Create `signals.py` with frozen `SignalRecipe(id, label, source, stored_index, saved_id, intervals, frames)`. `source` is `stored`, `custom` or `saved`; irrelevant reference fields are null. `intervals` is a canonical tuple of finite `(lower_Th, upper_Th)` pairs; `frames` is an inclusive acquisition interval. An empty interval set cannot be applied. A saved recipe must retain the underlying derivation, not just a path to a result.

`SignalRecipe.to_dict()`/`from_dict()` define recipe schema version 3 and legacy single-interval conversion. Metadata for a saved record wraps the derivation recipe rather than overwriting it. IDs are stable UUID strings; computation cache keys exclude display labels/colors and include source-file identity, canonical intervals, source reference and frame coverage. Bridge existing integer comparison IDs through controller adapters; do not change all frontend IDs implicitly.

Add `integration.py` for canonicalization and single-pass union integration; retain `custom_peak` as a compatibility wrapper for one interval. A shared `read_signal(path, recipe)` API in `signals.py` dispatches to stored, raw or saved readers and returns a `(last-first+1, ny, nx)` array covering exactly `recipe.frames`; index zero corresponds to the first declared acquisition frame. To avoid a cycle, data-layer modules never import the signal model at runtime; the saved reader accepts a UUID, and `signals.py` imports that reader lazily.

The spectrum editor gains an explicit Add interval action and removable interval rows. Drag edits a selected interval; existing primary/comparison Apply actions remain deliberate. Export every interval, never only its bounding envelope.

## 5. Peak identification and abundance table

Initial scope: atomic isotope ions with explicit polarity and supported integer charge states (1–3). Match against a versioned offline reference dataset with exact mass, natural abundance or abundance interval, and source/version metadata. Neutral atomic masses require a documented ionic-mass convention; do not substitute rounded nominal masses or atomic weights.

Tolerance is explicit in Th or ppm. Rank candidates by absolute mass error, retain ties, and show charge and error. Suggest identities without silently relabeling stored file labels. Natural isotope abundances are reference expectations, not measured composition; enriched samples and SIMS matrix/interference effects remain relevant. Preserve CIAAW abundance intervals rather than inventing a precise midpoint.

The table shows isotope, predicted m/z, reference abundance/range, selected measured area, and observed fraction within the measured isotope set. Use the same raw normalization, frames and ROI as the explorer. Identify overlapping/isobaric windows and mark their contributions ambiguous rather than reporting independent quantitative abundances. Molecular/adduct libraries, unconstrained formula search and automated concentration fitting are later extensions.

## 6. Known-depth calibration

Users assign physical depths to acquisition frames in an editable anchor table, or add an anchor at a clicked profile location. Require two distinct frames to activate calibration; keep zero/one anchors as an inactive draft. Sort by frame, reject duplicate frames/non-finite values, require depths to increase with frame, and support nm, µm and mm with canonical internal nm. Frame 0 is always anchored to depth 0 and cannot be removed or changed. Additional anchors must have positive increasing depths.

Use piecewise-linear interpolation between anchors. Outside the calibrated span return missing depth, with no extrapolation or clamping. A Frames/Depth toggle makes the known span explicit. Selecting in depth coordinates maps back to acquisition frames, preserving original sample intensities and inclusive frame selection. Removing anchors updates or disables the calibrated view without deleting data.

First deliverable affects the profile axis, CSV depth column, and saved recipe/anchor metadata. Image navigation continues to use frames. Physically calibrated 3D geometry is a separate follow-on that must address nonuniform layer spacing and common X/Y/Z units; merely changing a Z label is not sufficient.

## Proposed sequencing and decisions to review

Recommended order: disjoint-window signal model → file browser/config → depth calibration → identification/table → multi-peak 3D → write-back. Browser and depth work can proceed independently after their interfaces are agreed. Write-back depends on the signal model and server configuration; it accepts optional calibration if available.

Review before implementation: whether native commercial-software visibility is required for write-back; atomic-only identification scope; lack of depth extrapolation; initial 3D voxel budget; actual server storage/locking environment. These are proposed choices, not already-confirmed client requirements.

## Primary references checked during planning

- [h5py datasets: resizing and maximum shape](https://docs.h5py.org/en/stable/high/dataset.html#resizable-datasets).
- [h5py file objects and modes](https://docs.h5py.org/en/stable/high/file.html).
- [filelock inter-process locking](https://py-filelock.readthedocs.io/en/latest/).
- [NIST atomic weights and isotope masses](https://www.nist.gov/pml/atomic-weights-and-isotopic-compositions-relative-atomic-masses).
- [CIAAW isotopic abundances](https://ciaaw.org/isotopic-abundances.htm).

Reference pages establish data/API sources; they do not establish ToF-Explorer write compatibility or a sample's chemical identity.
