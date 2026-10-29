# Spatial renderer decision — 2026-10-22

Historical decision for Task 4: select Plotly.js (superseded by the vtk-only follow-up below). Keep ECharts for original-resolution profiles.
The production API supplies scalar arrays and coordinates, never figure JSON.

## Reproducible geometry gate

`frontend/evaluation/SpatialProbe.tsx` registers the same three scalar layers
on X/Y `[0,1,2]`, Z `[0,10,30,60]`, with a missing sample. Run
`npm --prefix frontend run test:e2e -- spatial-probe.spec.ts`.
Local Chrome measured Plotly camera-update p95 21.3 ms over 30 updates;
fixture JSON was 379 bytes. These tiny-fixture measurements are not acquisition
performance evidence. Screenshot: Playwright's renderer-comparison.png artifact.

Plotly receives explicit nonuniform coordinates `[0,10,30,60]`. vtk.js's standard
VolumeMapper input is ImageData; setting its end-to-end spacing to 20 produces
`[0,20,40,60]`. The automated comparison asserts both coordinate sequences.
This candidate fails the scientific geometry gate before GPU benchmarking:
resampling onto ImageData would change the scientific representation. We do not
claim vtk.js rendering latency, missing-mask fidelity, overlay or linked-camera
qualification from this probe. Implementing a custom mapper is outside Task 4.

Sources: [vtkImageData](https://kitware.github.io/vtk-js/api/Common_DataModel_ImageData.html)
and [Plotly volume coordinates](https://plotly.com/javascript/reference/volume/).

## Selected implementation contract

The API retains null values and validity/count arrays. The Plotly adapter crops
complete finite boxes without changing XYZ coordinates, and uses finite points
for irregular masks, thin coverage, constant data or a 100th-percentile cutoff.
NaNs poison Plotly volume extrema and can blank the whole layer, so missing
samples never enter that renderer as NaN or as zero. Tests must verify the
adapter inputs, missing samples, tiled/overlay scenes and camera linking. Tiled
pages contain at most four scenes; overlay has one scene. Both share the total
500,000-voxel budget, with no resampling of calibrated Z or numerical scaling.
The percentile cutoff only chooses visible intensities; independent/shared color
ranges do not modify payload values. Transparent overlays are qualitative and
occluded layers can be inspected with Solo or tiles.

## Read-only acquisition benchmark

The confirmed local AlTiPt acquisition, stored signals nearest 27, 48 and 194 Th,
Fast quality: three 93×32×32 previews, 285,696 total voxels. Compact API JSON was
5,501,154 bytes (5.25 MiB). Presenter preparation measured 0.583 s initially and
0.302 s with cached original arrays. Retained admitted source arrays totaled
255,787,008 bytes; this is not process RSS. Source size and mtime were unchanged.

Production-adapter Chrome measurement: initial render 1,467 ms; thirty direct
camera updates p95 30 ms; thirty actual drag-to-next-frame interactions p95
102 ms (nearest-rank percentile, includes driver/frame scheduling). Chrome's
approximate JS heap readout was 713,209,373 bytes, including renderer/temporary
allocations; it is not GPU memory or a peak measurement. A bounded transport
payload does not imply small browser memory use. The historical 32 MiB encoded
payload / 200 ms interaction context was met locally; no guarantee is made for
other workloads or hardware.

Reproduce with a renderer-neutral payload from the admitted presenter and
`TOFSCOPE_VOLUME_BENCHMARK=/path/to/payload.json npm --prefix frontend run test:e2e -- volume-performance.spec.ts`.
This optional acquisition test is skipped in the fixture-only full suite.

## Scientific and application qualification

Regression coverage includes quality limits, the shared 500,000-voxel budget,
valid partial-block means (including nonfinite samples), frame origins/ROI,
unknown-depth clipping before pooling, and a pooled calibrated block whose
coordinate is 26 nm rather than 20 nm from mapping its mean frame. Profiles and
CSV continue to use original-resolution data.

Service tests cover owner checks, stale sources, resource rejection cleanup,
style changes reusing admitted source arrays, ready layers mixed with pending
signals, removed-layer pruning, strict styles and schema-4 saved ID remapping.
Browser coverage includes overlays/tiles, six-layer paging, styles, Solo,
visibility, shared scales, actual linked-camera dragging, projection/reset,
maximize/restore, a profile beside the volume, calibrated save/reopen, missing
samples as points and removal while viewing 3D.

A read-only code review identified and led to regressions for pending-signal
lookup, removed-signal rendering and Plotly's missing-value limitation. Task 3
cross-section screens/APIs were not introduced. The existing local service was
not restarted; activation requires saving analyses and confirming readiness.


## Final commands and results

- `.venv/bin/python -m unittest discover -s tests`: 207 passed.
- `npm --prefix frontend test`: 33 passed; TypeScript typecheck passed.
- `npm --prefix frontend run test:e2e`: 84 passed, one optional acquisition
  benchmark skipped. That benchmark passed separately; final focused 3D run: 4 passed.
- `uv run python scripts/build_frontend.py`: 7 verified local assets bundled.
  Plotly is lazy-loaded and bundled offline (4.84 MB before gzip, 1.46 MB gzip).
- `uv build --out-dir <artifacts>` and
  `.venv/bin/python scripts/check_distribution.py --artifacts <artifacts> --output <evidence>`:
  wheel and sdist independently installed without Node; offline browser, spatial
  preview/state restoration after restart/source removal, exact profile CSV,
  calibration/isotope restoration, optional/interrupted downloads all passed.
- `git diff --check`: passed. GitHub Actions were not monitored.

Synthetic fixture screenshots: [tiles](images/spatial-tiles.png) and
[calibrated overlay with depth profile](images/spatial-calibrated-overlay.png).

Backend restart of the user's existing port-8765 service remains subject to
saving current analyses and confirming readiness. No duplicate user service or
browser tab was launched. Isolated disposable services were used by test harnesses.

## Interaction follow-up — 2026-10-22

Manual Firefox use exposed lag that the original renderer-only Chrome probe did
not cover. Regression tests reproduced complete Plotly figure rebuilding when
polling returned equivalent metadata, on saved-camera echoes, and on explicit
camera changes. Rebuilding also recreated XYZ arrays and re-sorted percentiles.

The adapter now caches immutable geometry/style inputs, skips unchanged updates,
uses camera-only relayout for camera controls/linking, and skips redraw of a native
camera echoed through saved state. Renderer mutations are serialized. Equivalent
analysis metadata does not trigger a React update, and layer percentile statistics
are memoized independently of camera/opacity. Tests hold the actual trace coordinate
buffer identity across idle polling and camera persistence through the full app.

Fast renders three isosurfaces instead of ten. Detailed retains ten; this changes
rendering detail, not preview coordinates, validity, intensities or numerical limits.
3D exposes All frames and Frame range; entering from Explore single-frame mode
normalizes to All frames. Profile clicks and frame-arrow shortcuts no longer collapse
3D to a single slice. Internal thin-coverage fallbacks remain scientifically valid.

A new optional benchmark feeds the captured read-only real-acquisition payload
through the actual React view and API command lifecycle using the disposable fixture
service. It tests 30 drags, saved camera commands and idle polling, asserting the
volume geometry remains allocated throughout. This supplements the direct adapter
benchmark; headless Chrome results do not establish Firefox/GPU performance on all
machines. No original acquisitions are modified and the user's service is not
restarted for these frontend changes.


Final follow-up verification: 38 frontend tests and typecheck passed; the full
browser run with both acquisition benchmarks enabled passed all 89 workflows.
The new full-application benchmark rendered 285,696 preview voxels and retained
geometry across all 30 camera saves and subsequent polling. Fast's direct-adapter
initial rendering measured 773 ms, camera updates p95 23.8 ms and driver-inclusive
drags p95 103 ms. Full-app drags including saved command responses measured p95
200 ms. These are local Chrome samples; Firefox manual confirmation is still
needed. A final focused test passed the single-frame removal and existing shared
range bounds after restoring their unchanged server-compatible behavior.

Follow-up review confirmed renderer lifecycle handling. A proposed full-acquisition
range UI was backed out to preserve the existing canonical Explore/server range
rules without introducing a backend change. The 3D All frames summary reflects
the presenter's full acquisition domain; range controls still use shared bounds.

## vtk.js integration follow-up

Eligible complete overlays use vtk.js GPU volume
rendering. The admitted original preview remains unchanged. Nonuniform XY,
frame or calibrated depth coordinates are interpolated onto a uniform display
grid when necessary, and a warning is shown. This is a qualitative view:
resampling may smooth narrow peaks. Profiles,
measurements and exports use the original-resolution data. A bounded 500,000
voxel budget applies after resampling as well.

The production 3D workspace uses vtk for both overlays and tiles. Complete
signals render as volumes; incomplete, thin, constant, negative or
threshold-limited signals use vtk points at original preview coordinates, so
missing samples are never filled in. Overlays group volume signals into vtk volume actors; compositing between
groups is qualitative. The view identifies point rendering.
For extreme aspect ratios, ray sampling is capped at 1,000 steps along the
volume diagonal and the app warns that fine features may be missed. Intensity
hover is not yet available. vtk volume opacity is qualitative.
For multi-component volumes, colors are mixed in proportion to component
opacity; transparent components do not contribute color. Plasma and Purples
have distinct transfer functions and matching legends.

Tests exercise physical-depth interpolation, input preservation, coverage
admission, rounded coordinates, physical proportions, saved camera conversion,
orthographic rendering, camera persistence and save/reopen, overlay visibility,
and unchanged polling without rebuilding the canvas. A captured read-only real
acquisition preview was also used in the renderer test. Headless Chrome evidence
does not establish performance or GPU behavior for all Firefox configurations.
