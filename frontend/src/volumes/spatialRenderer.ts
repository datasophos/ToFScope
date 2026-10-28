/** Shared 3D view types and intensity statistics. */
import type { components } from "../api/generated";
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
  colorscale: "Viridis",
  colorscale_reversed: false,
  opacity: 0.12,
  percentile: 70,
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
export function layerRange(values: (number | null)[]) {
  let min = Infinity,
    max = -Infinity;
  for (const v of values)
    if (v !== null && Number.isFinite(v)) {
      min = Math.min(min, v);
      max = Math.max(max, v);
    }
  return min === Infinity ? [0, 0] : [min, max];
}
