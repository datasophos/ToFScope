# ToFScope prototype

A local **Marimo + Plotly** explorer for ToF-Explorer / Tofwerk HDF5 data.
No Panel or Anaconda dependencies. The source HDF5 file is opened read-only.

## Run

From this directory:

```sh
uv run --no-dev --locked marimo run app.py --host 127.0.0.1 --port 2718
```

Open <http://127.0.0.1:2718>. The supplied AlTiPt example is selected by
default. **Open file** browses the server data directory with breadcrumbs,
filtering and paginated results; select a file and press **Open dataset**.
Files remain on the computer running Python. Keep the server bound to localhost.

For deployment, explicitly configure a POSIX data root (including an NFS mount):

```sh
TOFSCOPE_DATA_ROOT=/mnt/acquisitions uv run --no-dev --locked marimo run app.py --host 127.0.0.1 --port 2718
```

An explicit root starts with no acquisition loaded. Optionally set `TOF_FILE`
to an absolute path inside that root, or a path relative to it. With neither
setting, the demo root is the supplied example's directory. An empty root
remains usable; a failed open preserves the current analysis. The picker
lists `.h5`/`.hdf5` files without reading acquisition arrays. Paths in browser
state and exported recipes are root-relative. Symlinks must resolve inside the
root. The root and its directory structure must be controlled by a trusted
server administrator; this is not a sandbox against hostile local filesystem
mutations. Authentication and remote multi-user hosting are outside this feature.

`TOFSCOPE_ALLOW_WRITES` accepts only `true` or `false` and defaults to `false`.
This setting reserves server write policy for the write-back feature; the current
explorer continues to open acquisitions read-only. NFS locking and replacement
behavior must be verified on the deployment mount before enabling write-back.

To inspect or modify the reactive notebook:

```sh
uv run --no-dev --locked marimo edit app.py
```

## Try it

The published app fills the browser window with a single tabbed workspace and
a persistent signal sidebar. Marimo edit mode keeps its normal notebook layout.

1. Click the ion-channel picker and type a mass (for example `27` or `193.95`)
   or a stored label (`Pt`). Search results show exact masses and integration
   limits, with at most eight results visible. Use Arrow keys and Enter to
   select, or Escape to cancel. Recent channels appear as one-click shortcuts.
   The comparison picker adds stored channels to a persistent list. Add as many
   comparison windows as needed; each row has its own remove button and color.
   The same colors identify depth-profile curves and spectrum bands.
   Searches use file labels rather than inferring ion identities for nominal bins.
2. **Explore** shows images on the left and the mass spectrum above the depth
   profile on the right. The four plot frames share an even grid; hover or focus
   a small **i** icon for interaction help. Each display has a **⤢** maximize button.
   Use **Restore layout** or **Escape** to return with its selections and zoom intact.
   Toggle **SIMS images** / **FIB SE image** above the images.
   SIMS opens with a top projection summed over loaded depth, and a front XZ
   projection summed over the ROI’s Y rows. Click the depth profile to pick a frame. Drag across
   it to select a persistent shaded depth window, such as frames 200–400. Drag
   its edges to resize, or Shift-drag inside it to move the interval. The window
   **sums the ion maps** and shows the **mean SE image** over the inclusive frame
   interval. Plot titles state the aggregation and frame count. The window also
   crops cross-sections, 3D and exports, and fills the integration frame fields.
   The full loaded profile remains visible for context. Clicking a frame exits
   window mode and restores single-frame maps. **All depths**, beside the frame
   controls, clears either a single-frame selection or a depth window and restores
   the top projection over all loaded depths. The depth profile also offers this
   reset while a selection is active, including when maximized.
   Use the frame number or previous/next buttons for exact single-frame steps.
3. Draw a rectangle on the ion map to define a spatial ROI. Click its gold
   outline to reveal edit handles, then drag to move or resize it. The depth profile, cross-sections and 3D crop
   share that region. **Reset to full field** clears it; exact pixel limits are
   available in the sidebar.
4. Use the embedded spectrum, or open **Mass spectrum** for a larger view. Drag horizontally to select a mass interval, including
   when starting directly on a peak. Drag a gold edge to resize it; Shift-drag
   inside the band to move it. If you switch to Plotly's zoom/pan tools, use
   **Draw window** to return to interval selection. The exact limits appear in
   the sidebar. The interval is a
   **draft** until you press **Apply custom window**; browsing does not trigger
   raw reconstruction. **Zoom to window** helps adjust narrow intervals.
   **Mass windows** lists draft intervals. Select a row to edit it, use **Add
   interval** for another row, or × to remove one. Dragging or entering limits
   changes only the selected row. Apply combines all rows into one signal: gaps
   are excluded, and overlapping intervals/shared endpoints count each event
   once. Removing all rows disables Apply without changing the active signal;
   Add interval or drawing on the spectrum starts a new draft.
5. Set the first/last integration frames and Apply. Start with a small interval
   for a quick trial. Reconstruction reads one raw frame at a time and reports
   progress. **Restore stored channel** returns to the original integrated data.
   To keep the image signal and add a comparison instead, choose **Add window to
   comparisons**. Each custom comparison retains its own mass bounds and frame
   coverage. Frames outside that coverage are missing, not zero. ROI changes
   recompute every comparison; relative scaling normalizes each curve separately.
6. Use **Cross-sections** for XZ/YZ views or **3D volume** to rotate the selected
   signal. The compact selection strip and expandable **Data & preview details** show the stored/applied source,
   exact mass limits, depth layers, spatial ROI and preview resolution. Each 3D
   voxel contains the active mass-window intensity at one X/Y/depth position;
   the integrated top projection sums those layers. Comparison channels
   affect comparison curves and spectrum bands; relative-profile scaling affects
   the profile chart only. Neither changes the active image or 3D signal. Pending mass
   or reconstruction-frame edits are called out separately until Apply.
   Context links jump to the spectrum or slice/profile view to edit the source
   selection. Opacity, threshold and display stretch change rendering only.
7. Download the full-resolution ROI mean depth profiles (active signal plus all
   comparisons) with **Profile CSV**, or
   save the active analysis recipe and comparison definitions with **Settings JSON**.
   Schema 3 records every mass interval, source channel, inclusive frame coverage
   and a stable recipe UUID. Composite recipes do not substitute one bounding
   interval for their separated windows. Older raw single-window recipes can be
   converted by `SignalRecipe.from_dict`; legacy stored recipes need a channel
   index to preserve vendor-derived values.
   CSV cells outside a comparison’s frame coverage are empty.

Plot interactions update shared Python state through an AnyWidget bridge.
Plotly's JavaScript bundle comes from the installed package; no CDN is required.
Only visible plots in the active tab render. Frame changes update slices and markers
without rebuilding the 3D volume. The frontend lives in `web/`; `workspace.py`
handles its events and `explorer.py` contains reusable file/analysis functions.

## Scientific and performance scope

Comparison count has no fixed cap. Custom comparisons retain their reconstructed
volumes in memory so spatial ROI changes remain exact; narrow the frame range
when trying many custom windows on a large acquisition.


- `explorer.py` is a reusable data layer independent of Marimo. It reads the
  Tofwerk schema directly with h5py to bound access to individual peak channels
  and raw depth slices; it does not yet use the higher-level eXSpy signal API.
- Stored channels are already integrated. Editing a true mass window therefore
  reconstructs a new channel from `FullSpectra/EventList`, using calibrated
  `MassAxis`, the TDC clock ratio, and waveform / active-channel normalization.
  Both mass-window endpoints are inclusive; entered bounds retain their numeric
  precision when rendered, applied, and exported. Missing calibration metadata
  produces an error rather than a guessed normalization.
- A four-frame nominal-27 reconstruction of the supplied example differed
  from the vendor-stored total by approximately **0.005%**, with at most **0.25**
  intensity units per pixel (one event divided by normalization 4). The cause
  has not been established. Treat reconstructed channels as independently
  derived results, not bit-identical reproductions of vendor processing.
- Frames are zero-based and inclusive. The example contains 1,302 raw writes
  but 1,301 stored frames. The prototype uses only the stored frame domain;
  it does not infer the correspondence of the extra raw write.
- SE images are paired by index, shown in native pixels. Spatial registration
  and timing alignment have not been established. Window mode averages them
  without registration. The final SE image is shorter; each mean-image pixel is
  divided by its actual coverage count so missing rows do not bias it downward.
- X/Y units derive from `FIBParams.ViewField` (millimeters converted to µm).
  Z remains acquisition frames. **Z stretch is a display setting**, not a
  calibrated sputter depth or a physical aspect ratio.
- Profiles and slices use original-resolution data. The 3D preview uses block
  means (including partial edge blocks), at most 96 × 32 × 32 voxels in Fast mode
  or 160 × 48 × 48 in Detailed mode. Thin features contribute to block means,
  although their displayed contrast and geometry can change with downsampling.
- Logarithmic colors apply `log(1 + intensity)` only to displays. Ion maps
  keep a fixed color range across frames, estimated from the channel.
- CSV exports contain unscaled ROI mean intensity over the selected depth
  window, or the loaded frame range when no window is selected. The optional
  relative profile display does not change the values. JSON recipes include
  the selected and loaded frame ranges and are downloadable;
  re-import is not implemented yet.
- The example's 217-channel array expands to 17.2 GiB. The app loads channels
  individually (81.3 MiB each), caches up to three stored channels, and retains
  the active custom channel and each custom comparison. Full custom reintegration can take a minute or
  longer. Progress appears while that calculation is running.
- This is a prototype for files that contain `PeakData/PeakData`, a peak table,
  mass axis and sum spectrum. Raw-only files, physical depth calibration,
  background subtraction, mass recalibration, multi-ion 3D overlays,
  segmentation and quantitative composition are outside its current scope.

## Known-depth calibration

Use **Depth…** on the profile to edit known depths. Frame 0 is fixed at depth 0;
add positive-depth anchors at acquisition frames. The selected frame pre-fills
the anchor entry. Switch **Profile coordinates** to physical depth and choose
nm, µm or mm. Between anchors the profile uses piecewise-linear interpolation;
later depths stay unknown. Dragging still selects original acquisition frames,
without resampling or changing intensities. CSV adds `depth_nm`, leaving unknown
values blank; JSON retains canonical nm anchors and the interpolation policy.
Removing all positive-depth anchors restores frame coordinates. Cross-sections
and 3D still use acquisition frames and the existing arbitrary display stretch.

## Atomic ions and isotope measurements

Use **Identify…** on the spectrum to search an explicit m/z tolerance in Th or
ppm, polarity, and charges 1–3. The helper uses the offline NIST/CIAAW catalog;
reference version and mass convention are in [data/reference/README.md](data/reference/README.md).
Select a candidate and **Annotate signal** to record an interpretation alongside
the original label. **Apply window** and **Add as comparison** are separate
analysis actions with editable exact integration limits.

The **Isotopes** tab explicitly measures selected active/comparison signals in
the current ROI and depth window. It shows original intensity sums, observed
fractions within that selected set, natural reference abundances/ranges and
coverage/status. Ratios use common covered frames. Overlapping windows suppress
fractions; unknown reference abundances remain unknown. These are signal ratios,
not a quantitative composition fit. **Isotope CSV** and Settings JSON preserve
measurement scope and annotations; measurements do not automatically rerun when
you change the ROI or depth window. Molecular ions/adducts are outside this pass.

## Verify

```sh
uv run python -m unittest discover -s tests -v
uv run marimo check app.py
uv run python scripts/check_browser.py
uv run python scripts/check_spectrum.py
uv run python scripts/check_depth_window.py
uv run python scripts/check_peak_picker.py
uv run python scripts/check_volume_context.py
uv run python scripts/check_comparisons_layout.py
uv run python scripts/check_display_layout.py
uv run python scripts/check_all_depths.py
uv run python scripts/check_roi_replacement.py
uv run python scripts/check_viewport.py
uv run python scripts/check_window_sets.py
uv run python scripts/check_interval_selection_race.py
uv run python scripts/check_file_browser.py
uv run python scripts/check_depth_calibration.py
uv run python scripts/check_peak_helper.py
```

The numerical tests cover empty pixels, inclusive mass-window endpoints,
out-of-range events, invalid bounds, pooling of thin features and partial
blocks, conversion of drawn coordinates to pixel regions, comparison frame
alignment and ROI updates, independent normalization, and exact XZ projections. Browser checks
use installed Google Chrome and the real example to exercise profile clicks
and drags, ROI drawing/editing, mass-window drawing, tabs, integration, multiple
comparison windows, the SIMS/SE toggle, and exports.
