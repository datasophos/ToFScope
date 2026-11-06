/** Shared 3D view types and intensity statistics. */
import type { components } from "../api/generated";
import { layerRange } from "../shared/levels";
export { histogram, layerRange } from "../shared/levels";
export type VolumeData = components["schemas"]["VolumeData"];
export type SpatialView = components["schemas"]["SpatialView"];
export type SpatialLayer = components["schemas"]["SpatialLayer"];
export type Camera = components["schemas"]["Camera"];
export const defaultCamera: Camera = {
  eye: { x: 1.5, y: 1.5, z: 0.9 },
  center: { x: 0, y: 0, z: 0 },
  up: { x: 0, y: 0, z: 1 },
  projection: "perspective",
};
export const defaultLayer = (signal_id: string): SpatialLayer => ({
  signal_id,
  visible: true,
  colorscale: signal_id === "@se" ? "Gray" : "Viridis",
  colorscale_reversed: false,
  opacity: 0.12,
  percentile: 70,
  levels: null,
  camera: defaultCamera,
});
export const enabledLayers = (v: SpatialView) =>
  v.layers.filter((l) => l.visible && (!v.solo || l.signal_id === v.solo));
function sortedPercentile(a: number[], p: number) {
  if (!a.length) return 0;
  const i = ((a.length - 1) * p) / 100,
    lo = Math.floor(i);
  return a[lo] + (a[Math.ceil(i)] - a[lo]) * (i - lo);
}
export function percentile(values: number[], p: number) {
  return sortedPercentile(
    values.slice().sort((a, b) => a - b),
    p,
  );
}
const displayIntensity = (v: number, log: boolean) =>
  log ? Math.log1p(Math.max(v, 0)) : v;
export function volumeDisplayStats(
  values: (number | null)[],
  p: number,
  log = false,
) {
  const finite = values.filter(
    (v): v is number => v !== null && Number.isFinite(v),
  );
  const positive = finite.filter((v) => v > 0);
  const sorted = (positive.length ? positive : finite)
    .map((v) => displayIntensity(v, log))
    .sort((a, b) => a - b);
  const lower = sortedPercentile(sorted, p),
    high = sortedPercentile(sorted, 99.7);
  return {
    range: finite.length ? layerRange(values) : null,
    lower,
    upper: Math.max(high, lower + Math.max(Math.abs(lower) * 0.01, 1e-6)),
    threshold: log ? Math.expm1(lower) : lower,
  };
}
export function levelStats(
  values: (number | null)[],
  style: SpatialLayer,
  log = false,
) {
  const fallback = volumeDisplayStats(values, style.percentile, log);
  if (!style.levels) return fallback;
  const [lo, hi] = style.levels;
  const lower = displayIntensity(lo, log),
    upper = displayIntensity(hi, log);
  return {
    ...fallback,
    lower,
    upper: Math.max(upper, lower + 1e-6),
    threshold: lo,
  };
}
