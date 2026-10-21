# Depth calibration qualification — 2026-10-20

Depth calibration is stacked on PR #1 (`5efba01` at branch creation), using the
frozen `prototype-2026-10-18` interaction and archived numerical assertions as
reference. Implementation and review were inline, without delegated agents.

## Shipped behavior

A temporary graphical editor opens from the existing Viewing depths strip.
Profiles in the editor always use original acquisition frames, including unknown
physical depths. Users select graphically or enter exact frame/depth values,
update/remove anchors, and choose nm/µm/mm. Frames / Physical depth buttons
in the main Viewing depths strip switch coordinates. The
origin is fixed, and positive anchors must increase strictly. Canonical depths
are nm. Validation rejects bad edits without changing committed calibration.

Physical profile/front views omit unknown samples, keep original frame IDs and
intensities, and expose coverage. Single samples remain visible; unknown-only
ranges display an explicit empty state. Per-row raster footprints follow
nonuniform coordinates across anchor slope changes. Footprints are display
geometry, not measured plane thickness or a claim of physical aspect ratio.
Ion maps and frame navigation retain the complete selected acquisition frames.
Unit changes affect coordinates only and do not launch integration jobs.

CSV retains original-scale ROI means and includes `depth_nm` with unknown values
blank, independently of display unit/coordinates. Saved HDF5 document version 2
stores anchors and display choices. Version 1 documents restore frame coordinates
with fixed origin only; older applications reject version 2. The existing bounded
result reader, owner isolation, immutable sources, source generation checks,
revision receipts and job/publication boundaries remain in use.

`presentation/coordinates.py`, explicit axis boundaries and acquisition-frame IDs
are reusable by later sections/3D. Those screens remain deferred. Block-coordinate
checks average calibrated samples across slope changes, including 30 nm for
frames `[2,3]` under anchors `(0,0),(2,20),(4,60)`.

## Evidence

- 179 Python tests, including eight depth application/presenter tests and an API
  calibration/owner/coordinate-override test; existing numerical suites retained.
- 22 frontend unit assertions, including coordinate roundtrips, anchor validation,
  nonuniform boundaries and a single-sample footprint; TypeScript check passes.
- The final browser regression covers 59 workflows. Calibration coverage includes graphical selection, exact and table edits, rejected
  edits, units, profile/front navigation, anchor removal, same-file tab isolation,
  partial save/reopen and single/empty calibrated domains.
- Regenerated OpenAPI/TypeScript; rebuilt bundled offline assets.
- Independently installed wheel and sdist exercise plots, integration, raw
  preparation and calibrated saved copies, restart, removal of the disposable
  original, exact restored CSV, optional and interrupted downloads. Runtime has
  no Node, CDN, Marimo, AnyWidget or RosettaSciIO dependency.
- Original fixture hashes are unchanged by saved-copy tests. Source-checkout
  planning documents and the frozen prototype are untouched.

Commands: `.venv/bin/python -m unittest discover -s tests`,
`npm --prefix frontend test`, `npm --prefix frontend run typecheck`,
`npm --prefix frontend run test:e2e`, `npm --prefix frontend run generate:api`,
`.venv/bin/python scripts/build_frontend.py`, `uv build`, and
`.venv/bin/python scripts/check_distribution.py --artifacts dist --output <temp>`.
The packaged screenshot and graphical editor were inspected locally. Browser
screenshots and distribution JSON reports are temporary validation artifacts.

## Limits

Local Docker rerun is blocked by a stopped daemon. Both initial GitHub CI runs
passed independent package and Docker qualification for this branch;
[initial CI run](https://github.com/datasophos/ToFScope/actions/runs/39512876173).
Final manual-testing refinements are verified locally; remote CI was not monitored. Actual NFS/shared-storage behavior and commercial numerical
round trips remain unqualified. Running local services were restarted only with explicit user approval.

Final GitHub CI and browser results are recorded with the pull request.

## Manual testing feedback

Rejected edits now show a red, bordered alert beside the editor controls and
scroll into view. Numeric fields have visible outlines and white backgrounds;
the unit selector also uses a white background. Frames / Physical depth are
explicit buttons on the main Viewing depths strip, with the selected state
highlighted and physical depth disabled until a positive anchor exists.
Browser checks assert the error color, input border, select background and
main-page coordinate behavior alongside navigation and restoration.

Plots now draw named axes, units and tick marks directly in the renderer, with
compact scientific tick formatting. Spectrum/profile hover shows a vertical
guide and current x coordinate, including nearest acquisition frame for physical
profiles. Shared renderer/gesture insets preserve coordinate mapping and square
image domains. Axis names are included in PNG exports; the old corner caption
is retained only as an accessible description. Browser coverage verifies hover
without changing analysis revision and confirms unit-aware frame mapping.

Frame-axis ticks and hover readouts display integer acquisition frames only;
hover rounds to the nearest valid frame and clamps at acquisition endpoints.
Physical depth and m/z retain decimal precision. Unit/browser regressions
cover fractional pointer positions without allowing fractional frame labels.

Ctrl/Cmd-wheel zoom uses a cancellable native wheel listener on each plot's
selection surface. Modifier-wheel events prevent page scrolling/browser zoom;
ordinary wheel events retain normal page scrolling. A browser regression checks
both modifier keys, wheel cancellation, stable page scroll and normal scrolling.

Single clicks in spectrum viewing mode preserve the current zoom. Pointer
movement under four screen pixels is treated as a click, preventing zero-width
zoom ranges without depending on mass/intensity scale. Drag zoom, reset,
modifier-wheel zoom and profile/calibration frame picking remain covered.

The plot toolbar exposes Pan as an explicit toggle. Pan drags translate the
current horizontal view without changing its width, clamp at the data domain,
and preserve all signal draft intervals. Switching Pan off restores normal
selection/zoom gestures. Browser coverage verifies panning during signal creation
and returning to interval editing; numerical tests cover domain clamping.
Local verification for these follow-up gesture changes runs without monitoring
GitHub, per the user's explicit preference.

SIMS colormaps use canonical 256-color Viridis, Cividis and Magma lookup tables,
plus grayscale. Viridis is the default. Older blue–yellow display settings migrate
to Viridis; saved documents without the field use the new default. Palette changes
leave scientific arrays, axes and exports unchanged; SE remains grayscale.
The ion map and front projection share palette-matched colored outlines with
transparent interiors. Front selections span the full width and resize vertically.
Image pan/zoom controls were removed, and calibrated row rendering avoids
fractional-pixel transparency. ROI changes update overlays immediately without
refetching the unchanged ion image.

The signal editor displays all draft intervals, permits choosing a band, and
formats bounds compactly while preserving their exact values for calculation.
Double-clicking the spectrum resets zoom without changing draft bounds. File tabs,
open/help controls, plot headers and signal/depth bars use the compact layout
verified at desktop and narrow widths. Local services were restarted only after
explicit user approval. Remote CI was not checked for these final refinements.


## Temporary modifier panning

Holding Cmd or Ctrl temporarily activates horizontal pan on shared spectrum and
profile plots, including the identification spectrum. The Pan button reflects
the effective tool and its tooltip documents the shortcut. Releasing the modifier
restores the previous tool; manual pan stays selected. Blur and hidden-document
events clear temporary state. Pointer events synchronize modifier state for plots
mounted while a key is already held.

A drag keeps the tool chosen at pointer-down through pointer-up, so releasing
the modifier mid-gesture cannot accidentally zoom, pick a peak or edit an interval.
Browser coverage exercises Control and Meta on the main spectrum, profile and
identification spectrum, verifies translated ranges preserve width, release
mid-drag, manual-toggle persistence and blur cleanup. Ten focused browser
workflows, 30 frontend unit tests, TypeScript and the packaged build passed.
