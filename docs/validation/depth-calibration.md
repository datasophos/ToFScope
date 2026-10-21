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

- 176 Python tests, including eight depth application/presenter tests and an API
  calibration/owner/coordinate-override test; existing numerical suites retained.
- 14 frontend unit assertions, including coordinate roundtrips, anchor validation,
  nonuniform boundaries and a single-sample footprint; TypeScript check passes.
- All 47 browser workflows pass. Calibration coverage includes graphical selection, exact and table edits, rejected
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
The manual-testing UI refinements receive a fresh CI run. Actual NFS/shared-storage behavior and commercial numerical
round trips remain unqualified. No running local service was restarted.

Final GitHub CI and browser results are recorded with the pull request.

## Manual testing feedback

Rejected edits now show a red, bordered alert beside the editor controls and
scroll into view. Numeric fields have visible outlines and white backgrounds;
the unit selector also uses a white background. Frames / Physical depth are
explicit buttons on the main Viewing depths strip, with the selected state
highlighted and physical depth disabled until a positive anchor exists.
Browser checks assert the error color, input border, select background and
main-page coordinate behavior alongside navigation and restoration.
