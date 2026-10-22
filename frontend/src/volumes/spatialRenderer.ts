/** Renderer adapter: scientific coordinates and values are never normalized. */
import type { components } from "../api/generated";
import { colormaps } from "../plots/colormaps";
export type VolumeData = components["schemas"]["VolumeData"];
export type SpatialView = components["schemas"]["SpatialView"];
export type SpatialLayer = components["schemas"]["SpatialLayer"];
export type Camera = components["schemas"]["Camera"];
export const defaultCamera: Camera = {
  eye: { x: 1.25, y: 1.25, z: 1.25 },
  center: { x: 0, y: 0, z: 0 },
  up: { x: 0, y: 0, z: 1 },
  projection: "perspective",
};
export const defaultLayer = (signal_id: string): SpatialLayer => ({
  signal_id,
  visible: true,
  colorscale: "Viridis",
  opacity: 0.12,
  percentile: 70,
  camera: defaultCamera,
});
export const enabledLayers = (v: SpatialView) =>
  v.layers.filter((l) => l.visible && (!v.solo || l.signal_id === v.solo));
export function percentile(values: number[], p: number) {
  const a = values.slice().sort((x, y) => x - y);
  if (!a.length) return 0;
  const i = ((a.length - 1) * p) / 100,
    lo = Math.floor(i);
  return a[lo] + (a[Math.ceil(i)] - a[lo]) * (i - lo);
}
function colorscale(name: string) {
  const table = colormaps[name.toLowerCase() as keyof typeof colormaps];
  return table
    ? Array.from({ length: 256 }, (_, i) => [
        i / 255,
        `rgb(${table[i * 3]},${table[i * 3 + 1]},${table[i * 3 + 2]})`,
      ])
    : name;
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
const plotCamera = (c: Camera) => ({
  ...c,
  projection: { type: c.projection },
});
export function buildSpatialFigure(d: VolumeData, v: SpatialView) {
  const styles = enabledLayers(v),
    all = d.layers.filter((l) =>
      styles.some((s) => s.signal_id === l.signal_id),
    );
  let lo = Infinity,
    hi = -Infinity;
  for (const l of all) {
    const r = layerRange(l.values);
    lo = Math.min(lo, r[0]);
    hi = Math.max(hi, r[1]);
  }
  const page = Math.min(v.page, Math.max(0, Math.ceil(all.length / 4) - 1));
  const layers = v.mode === "tiles" ? all.slice(page * 4, page * 4 + 4) : all;
  const traces: any[] = [],
    layout: any = {
      margin: { l: 0, r: 0, t: 35, b: 0 },
      paper_bgcolor: "rgba(0,0,0,0)",
      showlegend: false,
      uirevision: "spatial",
      annotations: [],
    };
  const scenes = new Map<string, string>();
  layers.forEach((l, index) => {
    const style = styles.find((s) => s.signal_id === l.signal_id)!;
    const scene =
      v.mode === "overlay"
        ? "scene"
        : index === 0
          ? "scene"
          : `scene${index + 1}`;
    scenes.set(scene, l.signal_id);
    const finite = l.values.filter(
      (x): x is number => x !== null && Number.isFinite(x),
    );
    if (!finite.length) return;
    const localRange = layerRange(l.values);
    const [min, max] = v.scale === "shared" ? [lo, hi] : localRange;
    const cutoff = percentile(finite, style.percentile);
    const x: number[] = [],
      y: number[] = [],
      z: number[] = [],
      indices: number[] = [];
    d.z.forEach((zz, iz) =>
      d.y.forEach((yy, iy) =>
        d.x.forEach((xx, ix) => {
          x.push(xx);
          y.push(yy);
          z.push(zz);
          const i = (iz * d.y.length + iy) * d.x.length + ix;
          if (l.values[i] !== null) indices.push(i);
        }),
      ),
    );
    // Plotly's volume extrema cannot contain NaN. Crop complete finite boxes
    // without changing coordinates; irregular masks use exact finite points.
    const lower = [Infinity, Infinity, Infinity],
      upper = [-Infinity, -Infinity, -Infinity];
    for (const i of indices)
      [x, y, z].forEach((a, k) => {
        lower[k] = Math.min(lower[k], a[i]);
        upper[k] = Math.max(upper[k], a[i]);
      });
    const volumeIndices: number[] = [];
    for (let i = 0; i < x.length; i++)
      if ([x, y, z].every((a, k) => a[i] >= lower[k] && a[i] <= upper[k]))
        volumeIndices.push(i);
    const irregular = volumeIndices.some((i) => l.values[i] === null);
    const thin =
      cutoff >= localRange[1] ||
      irregular ||
      [x, y, z].some((a) => new Set(indices.map((i) => a[i])).size < 2) ||
      layerRange(l.values)[0] === layerRange(l.values)[1];
    const common = {
      uid: l.signal_id,
      name: l.label,
      scene,
      opacity: style.opacity,
      hovertemplate: `${l.label.replace(/[<>&]/g, "")}<br>X %{x}<br>Y %{y}<br>Z %{z}<br>Intensity %{customdata}<extra></extra>`,
    };
    if (thin) {
      const keep = indices.filter((i) => l.values[i]! >= cutoff);
      traces.push({
        ...common,
        type: "scatter3d",
        mode: "markers",
        x: keep.map((i) => x[i]),
        y: keep.map((i) => y[i]),
        z: keep.map((i) => z[i]),
        customdata: keep.map((i) => l.values[i]),
        marker: {
          size: 4,
          color: keep.map((i) => l.values[i]),
          colorscale: colorscale(style.colorscale),
          cmin: min,
          cmax: max > min ? max : min + 1,
          showscale: false,
        },
      });
    } else
      traces.push({
        ...common,
        type: "volume",
        x: volumeIndices.map((i) => x[i]),
        y: volumeIndices.map((i) => y[i]),
        z: volumeIndices.map((i) => z[i]),
        value: volumeIndices.map((i) => l.values[i]),
        customdata: volumeIndices.map((i) => l.values[i]),
        isomin: cutoff,
        isomax:
          localRange[1] > cutoff
            ? localRange[1]
            : cutoff + Math.max(Math.abs(localRange[1]) * 1e-6, 1e-6),
        cmin: min,
        cmax: max > min ? max : min + 1,
        colorscale: colorscale(style.colorscale),
        showscale: false,
        surface: { count: 10 },
        caps: { x: { show: false }, y: { show: false }, z: { show: false } },
      });
    const row = Math.floor(index / 2),
      col = index % 2;
    const domain =
      v.mode === "tiles"
        ? {
            x: layers.length === 1 ? [0, 1] : [col * 0.5, col * 0.5 + 0.49],
            y:
              layers.length <= 2
                ? [0, 1]
                : [row === 0 ? 0.51 : 0, row === 0 ? 1 : 0.49],
          }
        : { x: [0, 1], y: [0, 1] };
    const xymax = Math.max(d.extent[0], d.extent[1], 1e-12);
    const exaggeration =
      d.z_unit !== "frame" ? v.depth_exaggeration : v.frame_stretch;
    const bounds = (axis: number[], extent: number, physical: boolean) => {
      const first = axis[0],
        last = axis.at(-1)!;
      return physical
        ? [(first * extent) / (last - first), (last * extent) / (last - first)]
        : [first - 0.5, last - 0.5];
    };
    const xRange = bounds(d.block_edges[2], d.extent[0], d.xy_unit === "µm");
    const yRange = bounds(d.block_edges[1], d.extent[1], d.xy_unit === "µm");
    const zRange =
      d.z_unit === "frame"
        ? [d.block_edges[0][0] - 0.5, d.block_edges[0].at(-1)! - 0.5]
        : [d.z[0], d.z.at(-1) === d.z[0] ? d.z[0] + 1e-12 : d.z.at(-1)!];
    layout[scene] = {
      domain,
      camera: plotCamera(
        v.mode === "overlay" || v.linked ? v.camera : style.camera,
      ),
      dragmode: "orbit",
      aspectmode: "manual",
      aspectratio: {
        x: d.extent[0] / xymax,
        y: d.extent[1] / xymax,
        z: d.physical_aspect
          ? (Math.max(d.extent[2], 1e-12) / xymax) * exaggeration
          : exaggeration,
      },
      xaxis: { range: xRange, title: { text: `X (${d.xy_unit})` } },
      yaxis: { range: yRange, title: { text: `Y (${d.xy_unit})` } },
      zaxis: {
        range: zRange,
        title: {
          text:
            d.z_unit === "frame" ? "Acquisition frame" : `Depth (${d.z_unit})`,
        },
      },
    };
    if (v.mode === "tiles")
      layout.annotations.push({
        text: l.label.replace(/[<>&]/g, ""),
        xref: "paper",
        yref: "paper",
        x: (domain.x[0] + domain.x[1]) / 2,
        y: domain.y[1],
        showarrow: false,
      });
  });
  return { traces, layout, scenes, page };
}

export async function mountSpatial(
  el: HTMLElement,
  onCamera: (id: string, c: Camera) => void,
) {
  const { default: Plotly } = await import("plotly.js-dist-min");
  let disposed = false,
    programmatic = false,
    scenes = new Map<string, string>();
  await Plotly.newPlot(
    el,
    [],
    { margin: { l: 0, r: 0, t: 0, b: 0 } },
    { responsive: true, displayModeBar: false },
  );
  (el as any).on("plotly_relayout", (event: Record<string, any>) => {
    if (programmatic || disposed) return;
    for (const [scene, id] of scenes) {
      const c = event[`${scene}.camera`];
      if (c?.eye && c?.up && c?.center)
        onCamera(id, {
          eye: c.eye,
          up: c.up,
          center: c.center,
          projection: c.projection?.type ?? "perspective",
        });
    }
  });
  return {
    async update(d: VolumeData, v: SpatialView) {
      if (disposed) return;
      const f = buildSpatialFigure(d, v);
      scenes = f.scenes;
      programmatic = true;
      try {
        await Plotly.react(el, f.traces, f.layout, {
          displayModeBar: false,
          responsive: true,
          scrollZoom: true,
        });
      } finally {
        programmatic = false;
      }
    },
    resize() {
      if (!disposed) void Plotly.Plots.resize(el);
    },
    destroy() {
      disposed = true;
      Plotly.purge(el);
    },
  };
}
