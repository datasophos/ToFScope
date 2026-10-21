# Explore renderer decision

Select **Apache ECharts 6**, Canvas renderer, with one cached raster image in a
public custom series and a small React SVG selection overlay. Plotly.js remains an
evaluation-only dev dependency; the release entry never imports it. The adapter
accepts arrays and axes, never Python figure JSON. vtk.js remains a separate
completion-plan task for nonuniform calibrated spatial geometry.

Reproduce: `npm ci && npm run test:renderer` in frontend. Headless installed
Google Chrome on this Apple Silicon machine, same fixtures and geometry for
both candidates. Tests draw beginning on a peak, reverse a mass interval, retain
1.00000001 exact entry, zoom then resize/maximize during delayed data update,
draw a reversed 128² image ROI, and select frames 260–520 on a 1,301-frame profile.
All assertions pass in both. Overlay ownership keeps exact domain conversions
explicit and avoids private renderer axis/drag APIs. The same overlay is used by
both, making its correctness a shared responsibility, not an ECharts advantage.

| Measurement | ECharts | Plotly.js |
| --- | ---: | ---: |
| Focused minified adapter bundle (esbuild) | 527,085 B | 4,845,207 B |
| gzip | 179,984 B | 1,458,424 B |
| 1,301-point depth update + animation frame p50 | 16.7 ms | 16.8 ms |
| p95 (20 samples) | 17.5 ms | 17.5 ms |

These warm update timings include browser frame scheduling; they do not measure
network latency or large-volume GPU work. Scientific payload is identical for
both because it is renderer independent. The image probe has 16,384 original
pixels. Narrow synthetic mass peaks exercise precision independently of the
real-acquisition throughput checks recorded in pilot qualification.

Both candidates support local PNG export. Canvas export retains rendered
pixels, while CSV/settings exports retain scientific resolution and precision.
Plotly can also export SVG but heatmap pixels still form a raster; no claim of
publication-quality vector image export is made. ECharts places the cached image
on numerical axes through its public custom-series interface.
Both require our explicit selection overlay for stable pixel rounding, exact
mass bounds, and consistent draft/Apply semantics. Thus bundle cost and narrower
dependency surface favored ECharts in this initial evaluation. These fixtures
did not establish full-size image resize performance; the follow-up below records
the regression missed by that evaluation.

An unrelated application occupied Vite's default port. Evaluation now uses a
dedicated strict port 18763 with no reuse so a foreign application cannot count
as test evidence. Test selectors name our panels/overlay, not library DOM.

Initial qualification found that ECharts' default progressive custom rendering could
leave late image rows unfinished during rapid updates. A 1301×128 probe checking
actual last-row canvas pixels failed before the fix and passed with progressive
batches disabled and explicit `encode` dimensions. Image updates now commit the
whole image; CSV/scientific arrays were unaffected. This follows ECharts' public
[custom-series dimension contract](https://echarts.apache.org/handbook/en/how-to/custom-series/).

## Full-size resize follow-up, 2026-10-19

The per-pixel custom rectangles performed poorly during maximize/restore. The
1301×128 front projection created 166,528 chart objects; resize and subsequent
updates repeated that work. A realistic-size browser regression failed at
529 ms against a 200 ms event-to-paint budget. The original depth-update timing
table did not cover this workload and cannot justify a performance comparison
with the previous Marimo/Plotly application.

The adapter now converts unchanged image values into a cached RGBA canvas once,
then crops and scales it using nearest-neighbor sampling. ECharts manages one
image object. The scaled canvas is bounded by the visible plot and device pixel
ratio, including at deep zoom. Redundant resize calls with unchanged dimensions
are skipped. Numerical arrays, axes, selections, profiles and exports retain
their original values; no reader or API change is involved.

Read-only checks on `pfib_1301x128x128_AlTiPt.h5` in local headless Chrome at
1660×1100 measured three maximize/restore pairs for each image:

| Event to two animation frames | Before (range) | After (range) |
| --- | ---: | ---: |
| Ion map maximize/restore | 471–533 ms | 22–31 ms |
| Front projection maximize/restore | 443–493 ms | 29–30 ms |

These are local event-to-render observations after data load, not network or
initial acquisition-open timings. Reproduce with `scripts/check_real_browser.py`
on the real file, or `npm run test:e2e -- --grep 'full-size image'` on deterministic
128×128/1301×128 payloads. The latter also verifies canvas dimensions and no
new data requests during maximize/restore. Pixel checks cover color equality,
missing values, orientation, unsmoothed boundaries and zoom cropping. The
large-image row-completion probe still passes.
