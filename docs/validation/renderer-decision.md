# Explore renderer decision

Select **Apache ECharts 6**, Canvas renderer, with public custom-series pixel
rectangles and a small React SVG selection overlay. Plotly.js remains an
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
publication-quality vector image export is made. ECharts needs custom heatmap
rectangles on numerical axes; this is a short public renderItem implementation.
Both require our explicit selection overlay for stable pixel rounding, exact
mass bounds, and consistent draft/Apply semantics. Thus bundle cost and narrower
dependency surface favor ECharts without a measured interaction disadvantage.

An unrelated application occupied Vite's default port. Evaluation now uses a
dedicated strict port 18763 with no reuse so a foreign application cannot count
as test evidence. Test selectors name our panels/overlay, not library DOM.

Qualification found that ECharts' default progressive custom rendering could
leave late image rows unfinished during rapid updates. A 1301×128 probe checking
actual last-row canvas pixels failed before the fix and passed with progressive
batches disabled and explicit `encode` dimensions. Image updates now commit the
whole image; CSV/scientific arrays were unaffected. This follows ECharts' public
[custom-series dimension contract](https://echarts.apache.org/handbook/en/how-to/custom-series/).
