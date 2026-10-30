# ToFScope user guide

A ToF-SIMS analysis application built with React/TypeScript and FastAPI.
Original acquisitions remain read only; analyses can be saved as new HDF5 files. One
installable Python application bundles the frontend and ECharts locally; one
service and port serve everything, with no runtime Node.js or CDN requirement.

```sh
uv sync --frozen
uv run tofscope --data-root /path/to/acquisitions --output-root /path/to/saved-analyses
```

For a guided first installation on macOS with uv, see the [macOS ToFScope guide](macos-tofscope.md).

To install from a clone, run `uv tool install .` in the repository, then
`tofscope --data-root /path/to/acquisitions`. The launcher binds loopback and opens
the browser after readiness. `tofscope serve --no-browser` runs a service;
`tofscope open` opens its authenticated local UI; `tofscope doctor` checks
configuration/assets. See [deployment](deployment.md) for configuration,
proxy authentication, resource limits, container use and restart behavior.

## Signals and views

Open multiple files, including the same file repeatedly, in independent file tabs.
Each analysis owns independent named signals, ROI, frame coverage and viewing
choices. The **Signals** tray lists stored channels and raw integrations: choose
one with **Images** and show or hide additional **Profile** curves. Names and
colors stay with each signal when you switch views.

Use **Add signal** to search vendor channels, or **Create from spectrum**
to name a raw integration and draw/enter exact inclusive mass intervals. Multiple
intervals form a union. **Calculate signal** adds a result to the tray/profile;
**Images** switches the ion map and front projection explicitly. **Details**
exposes provenance, coverage, rename, duplicate, and custom **Edit signal** actions.
Edits stay separate until **Update signal** succeeds; progress, cancellation and
errors remain visible beside the signal. Failed calculations preserve old results.

**Calculate over frames** defines a signal's coverage. **Viewing depths** chooses
which available frames to show without recalculating the signal. Choose **All
frames**, **Single frame**, or **Frame range**; only the selected mode's controls
appear. Range edits take effect with **Apply**, and the status describes the
displayed image. Profiles use the full acquisition domain, with gaps outside
signal coverage. **CSV** beside the depth profile controls exports its curves;
a selected frame range limits exported rows.
ROI controls live beside the image; **Display…** contains log colors, the
SIMS colormap and the SIMS/SE image choice. Viridis is the SIMS default, with
Cividis, Magma and grayscale available; the palette is saved with the analysis.
SE images retain grayscale. Palette-matched, unfilled ROI outlines and full-width
depth bands preserve image colors. Relative scaling lives in the profile header,
and log Y beside the spectrum. Spectrum drag zooms normally and edits the active
interval while a signal editor is open. All draft intervals remain numbered on
the spectrum. Bounds display compactly while preserving exact calculation values.
Single clicks preserve zoom; double-click resets the spectrum view. Hold Cmd/Ctrl
and drag to pan any zoomed spectrum/profile horizontally; the **Pan** indicator
lights only on the hovered plot while held. Toggle **Pan** to keep it enabled, or use Ctrl/Cmd-wheel to zoom.
Images show their full extent. Maximize/Escape preserves the view; ordinary wheel
scrolls the page. The compact header holds file opening and independent file tabs.
Plots have named axes, units and tick marks. Hover over the spectrum or profile
for the current x coordinate; calibrated profiles also show the nearest frame.

## Depth calibration

**Depth calibration…** opens a temporary graphical editor beside the viewing
controls. Click an original-frame profile position or enter an exact frame and
known depth; frame 0/depth 0 is fixed. Anchors must increase strictly. Choose the display unit (nm, µm, or mm) in
the editor, then use the **Frames / Physical depth** buttons in the main
**Viewing depths** strip. Physical profiles and front
projections show only frames between anchors; later depths remain unknown.
Selection and keyboard navigation still use original acquisition frames, and
unit changes never resample intensities. Removing positive anchors restores
frame coordinates. CSV includes canonical `depth_nm`, blank for unknown depths,
even when viewing in frames. A single plane's display footprint does not imply
known thickness. Linked XZ/YZ cross-sections remain deferred.

## Saving analyses

**Save as…** creates a self-contained HDF5 copy with all committed signals,
full-resolution custom results (including hidden signals), names/colors, ROI,
frame/depth selections, calibration anchors and coordinate/unit choices, and display settings. Open it from **Saved files** to
restore the analysis after a restart or on another machine. Saving does not
change the input, including when the input is an earlier saved copy. New copies
use analysis document version 4, including isotope results and spatial view state.
Versions 1–3 remain readable with defaults for fields absent in those versions.
Older applications reject version 4 documents.

Saving defaults to the server; **Download copy** is an explicit optional action.
Large files may take a long time to transfer. A saved copy includes the acquisition,
so a 2.2-GB input needs at least that much output space plus derived results.
The acquisition folder (`--data-root`) defaults to the current working directory.
The saved copies folder (`--output-root`) defaults to that acquisition folder;
set it explicitly when saving elsewhere or using read-only acquisition storage.
In **Save as…**, use **Choose folder…** to browse or create a subfolder. Local
users can choose within the configured acquisition or saved-files folders;
hosted users stay within their private saved-files folder. The dialog shows the
full destination before saving. **Saved files** supports navigating subfolders
when reopening copies. Existing files are never overwritten. See the
[save-folder validation](validation/save-folders.md).
Use the top Open button to open another file in a new tab, then close any tab you
no longer need. Finish/discard drafts and finish/cancel calculations before saving.
Closing an unsaved analysis offers Save as, Discard or Cancel. Save as also attempts to add eligible named signals as TOFexplorer peaks and reports exclusions. Disjoint peaks carry enclosing native bounds and a midpoint that do not describe the gaps; ToFScope retains the exact recipe. The unified save workflow has not yet been verified in TOFexplorer. CSV exports visible ROI
profiles at original scale/resolution; PNG includes profile labels.

## Raw acquisition preparation

TOFWERK TOFexplorer `.h5` acquisitions can contain stored ion maps or raw events.
For raw files without ion maps, the app previews the required preparation and
asks for confirmation before integrating peak windows into a new copy. Missing
timing/channel metadata requires explicit acknowledgment of the assumptions.
New preparations compact unused HDF5 space and use channel-oriented gzip storage;
see [raw preparation](validation/raw-acquisition-preparation.md) and
[storage measurements](validation/compact-raw-preparation.md).

Floating-point fields use compact values for reading and expose the full exact
value on focus. Numeric tables and plot readouts also suppress floating-point
tails; scientific calculations and exports retain full precision. See the
[numeric display audit](validation/numeric-display.md).

See [TODO.md](../TODO.md) for the current feature status and next work.

## Atomic identification and isotope measurements

Atomic identification suggests offline isotope-ion candidates with explicit charge,
polarity, mass error and reference provenance. Use **Identify peak** beside the mass
spectrum; its plot starts with log intensity. Click a peak to search immediately,
or enter an exact m/z. Tolerance defaults to 0.3 Th; changing tolerance, its unit,
or charge and polarity refreshes candidates immediately. Candidates default to known natural abundances, shown as percentages
and ordered by abundance within the mass tolerance. Closest-mass ordering and
isotopes without tabulated natural abundance are optional. Assign an isotope to an
existing signal, apply an exact window to an assigned draft, or explicitly
calculate a new assigned comparison. The draft keeps its isotope assignment when
you rename it. Original file labels remain unchanged.

**Isotope measurements** sums selected signals at original resolution over the
current ROI and viewing frames, using their common coverage. Overlapping windows
suppress fractions. Results show percentage shares, a readable region/frame
summary, and explanations for zero intensity or missing isotope assignments.
Calculation details and provenance are expandable. Results describe selected-set
signal ratios, not quantitative composition. Input changes mark
captured measurements out of date until you explicitly Measure again. Isotope
CSV and Settings JSON retain scope, mass errors, uncertainties and provenance;
Save as/reopen also preserves isotope assignments and captured results. See
[identification validation](validation/identification.md).

## 3D visualization

**3D volume** compares existing named signals as an overlay or tiled views. The
signal table lists every ready named signal; the current image signal is shown
initially. Check the signals to display and open a signal's settings to adjust
its colormap, opacity and percentile threshold. Independent intensity
scales are the default; Shared numerical uses one range across visible signals.
Percentile thresholds use positive intensities, with a robust 99.7th-percentile
upper display limit. Log colors uses log(1+intensity); depth profiles and exports retain original numerical intensities.
Tiles show four layers per page and support linked or independent saved cameras.
3D offers All frames and Frame range; single-frame navigation remains in Explore.
Entering 3D from a single frame switches to All frames.
Drag or use arrow keys to orbit, scroll to zoom, or Shift-drag to pan; reset, orthographic projection
and maximize controls are available. Choose an axis-aligned camera view or rotate in 15° steps for precise positioning; these controls apply to all tile cameras. ROI and Viewing depths apply to every layer.

Fast previews are capped at 96×32×32; Detailed at 160×48×48. All visible layers
share a 500,000-voxel budget, including layers on other tile pages. vtk.js
renders complete signals as volumes. Sparse, incomplete, thin, constant,
negative or high-threshold selections use vtk points at the original preview
coordinates. Overlays group volume signals into vtk volume actors; their
compositing is qualitative. Nonuniform XY, frame or calibrated-depth preview coordinates are
interpolated for display and a warning is shown; profiles, measurements and
exports use original-resolution data. For extreme aspect ratios, vtk limits ray
sampling and warns that fine features may be missed. Intensity hover is not yet
available. Camera movement and unchanged polling reuse existing geometry. Preview means
use actual valid samples in partial blocks. Missing coverage remains missing;
profiles and CSV use original resolution. Physical depth clips unknown frames
before pooling, and block coordinates average calibrated samples across anchor
slope changes. At 1× depth exaggeration, known XY/depth geometry uses common µm
units; Frame stretch is a separate display ratio. Thin/constant selections use
points. Transparent overlays are qualitative; show one signal or use tiles to inspect occlusion.
Save as preserves layer styles, layout, page, scale, cameras and exaggeration.
See [spatial qualification](validation/spatial-renderer-decision.md).

## Limitations and technical background

The application still lacks full prototype feature parity. Linked cross-sections
and controlled native saves remain specified in the [completion plan](superpowers/plans/2026-10-18-react-fastapi-completion.md).
In-place acquisition writes remain unavailable. Live tabs/jobs are in memory;
reopen saved HDF5 copies to restore committed work after a restart. Shared use requires a trusted authenticated proxy;
actual NFS deployment remains unqualified.

Scientific readers were compared before implementation: direct h5py preserves
selective bounded reads and exact existing NumPy integration without unused
signal-framework lifecycle machinery. See [reader evidence](validation/reader-decision.md).
ECharts and Plotly passed the same focused interaction probes; ECharts was chosen
for the smaller bundle and public numerical-axis adapter. See
[renderer evidence](validation/renderer-decision.md) and
[pilot qualification](validation/pilot-qualification.md).

## Building and testing

Node is needed only for frontend development and builds:

```sh
npm --prefix frontend ci
npm --prefix frontend run generate:api
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run test:e2e
uv run python scripts/build_frontend.py
uv run python -m unittest discover -s tests -v
uv build
uv run python scripts/check_distribution.py --artifacts dist --output /tmp/tofscope-distribution
uv run python scripts/check_container.py
```

Prebuilt assets are included in both wheel and sdist. A source build fails for
missing/stale assets. CI checks generated API drift, scientific/service tests,
frontend behavior, offline installed-package smoke and the container.
