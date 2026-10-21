# ToFScope Explore

A ToF-SIMS analysis application built with React/TypeScript and FastAPI.
Original acquisitions remain read only; analyses can be saved as new HDF5 files. One
installable Python application bundles the frontend and ECharts locally; one
service and port serve everything, with no runtime Node.js or CDN requirement.

```sh
uv sync --frozen
uv run tofscope --data-root /path/to/acquisitions --output-root /path/to/saved-analyses
```

For an installed wheel: `pip install dist/tofscope-0.2.0-py3-none-any.whl`, then
`tofscope --data-root /path/to/acquisitions`. The launcher binds loopback and opens
the browser after readiness. `tofscope serve --no-browser` runs a service;
`tofscope open` opens its authenticated local UI; `tofscope doctor` checks
configuration/assets. See [deployment](docs/deployment.md) for configuration,
proxy authentication, resource limits, container use and restart behavior.

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
known thickness. Sections and 3D remain future work.

**Save as…** creates a self-contained HDF5 copy with all committed signals,
full-resolution custom results (including hidden signals), names/colors, ROI,
frame/depth selections, calibration anchors and coordinate/unit choices, and display settings. Open it from **Saved files** to
restore the analysis after a restart or on another machine. Saving does not
change the input, including when the input is an earlier saved copy. New copies
use analysis document version 2; version 1 copies open in frame coordinates with
no positive anchors. Older application versions reject version 2 documents.

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
[save-folder validation](docs/validation/save-folders.md).
Finish/discard drafts and finish/cancel calculations before saving. Closing an
unsaved analysis offers Save as, Discard or Cancel. CSV exports visible ROI
profiles at original scale/resolution; PNG includes profile labels.

TOFWERK TOFexplorer `.h5` acquisitions can contain stored ion maps or raw events.
For raw files without ion maps, the app previews the required preparation and
asks for confirmation before integrating peak windows into a new copy. Missing
timing/channel metadata requires explicit acknowledgment of the assumptions.
New preparations compact unused HDF5 space and use channel-oriented gzip storage;
see [raw preparation](docs/validation/raw-acquisition-preparation.md) and
[storage measurements](docs/validation/compact-raw-preparation.md).

Floating-point fields use compact values for reading and expose the full exact
value on focus. Numeric tables and plot readouts also suppress floating-point
tails; scientific calculations and exports retain full precision. See the
[numeric display audit](docs/validation/numeric-display.md).

See [TODO.md](TODO.md) for the current feature status and next work.

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
[identification validation](docs/validation/identification.md).

The application still lacks full prototype feature parity. Sections, volume
tools and controlled native saves are specified in the [completion plan](docs/superpowers/plans/2026-10-18-react-fastapi-completion.md).
In-place acquisition writes remain unavailable. Live tabs/jobs are in memory;
reopen saved HDF5 copies to restore committed work after a restart. Shared use requires a trusted authenticated proxy;
actual NFS deployment remains unqualified.

Scientific readers were compared before implementation: direct h5py preserves
selective bounded reads and exact existing NumPy integration without unused
signal-framework lifecycle machinery. See [reader evidence](docs/validation/reader-decision.md).
ECharts and Plotly passed the same focused interaction probes; ECharts was chosen
for the smaller bundle and public numerical-axis adapter. See
[renderer evidence](docs/validation/renderer-decision.md) and
[pilot qualification](docs/validation/pilot-qualification.md).

Build/verify from source (Node is needed only for frontend development/builds):

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

The complete Marimo prototype is frozen at
`37ecacf24c32388cd7f84bc11fa509989cc44775` in a separate checkout, with its own
locked environment. Recreate without changing this application:

```sh
git worktree add --detach /path/to/tofscope-prototype 37ecacf24c32388cd7f84bc11fa509989cc44775
cd /path/to/tofscope-prototype
uv sync --frozen
uv run marimo run app.py --headless --host 127.0.0.1 --port 27991
```

Set `TOFSCOPE_DATA_ROOT` and `TOF_FILE` there to inspect an acquisition. Keep
original acquisitions read only; prototype write flags should remain disabled.
The [baseline](docs/validation/prototype-baseline.md) records its test evidence.
Old widget assertions are preserved under `docs/validation/prototype-tests/`;
[coverage mapping](docs/validation/coverage-map.md) assigns them to replacement
checks or explicit completion-plan features. No legacy runtime or compatibility
adapter is shipped. The [migration design](docs/react-fastapi-migration.md) and
[pilot plan](docs/superpowers/plans/2026-10-18-react-fastapi-pilot.md) describe the
boundaries and decisions.

Color maps use canonical 256-color tables. Older blue–yellow selections migrate to Viridis.
