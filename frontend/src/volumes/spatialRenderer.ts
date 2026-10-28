/** Renderer adapter: scientific coordinates and values are never normalized. */
import type { components } from "../api/generated";
import { colormaps } from "../plots/colormaps";
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
export type SpatialOptions = { log?: boolean };
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
export function buildSpatialFigure(
  d: VolumeData,
  v: SpatialView,
  options: SpatialOptions = {},
) {
  const log = options.log ?? false;
  const styles = enabledLayers(v),
    all = d.layers.filter((l) =>
      styles.some((s) => s.signal_id === l.signal_id),
    );
  const shared = volumeDisplayStats(
    all.flatMap((l) => l.values),
    0,
    log,
  );
  const page = Math.min(v.page, Math.max(0, Math.ceil(all.length / 4) - 1));
  const layers = v.mode === "tiles" ? all.slice(page * 4, page * 4 + 4) : all;
  const traces: any[] = [],
    layout: any = {
      margin: { l: 12, r: 12, t: 32, b: 12 },
      paper_bgcolor: "#101f2e",
      font: {
        family: "Inter, system-ui, sans-serif",
        color: "#b7cbd8",
        size: 11,
      },
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
    const stats = volumeDisplayStats(l.values, style.percentile, log);
    const [min, max] = [0, v.scale === "shared" ? shared.upper : stats.upper];
    const cutoff = stats.lower;
    const shownValue = (value: number) => displayIntensity(value, log);
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
      cutoff >= shownValue(localRange[1]) ||
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
      const keep = indices.filter((i) => shownValue(l.values[i]!) >= cutoff);
      traces.push({
        ...common,
        type: "scatter3d",
        mode: "markers",
        x: keep.map((i) => x[i]),
        y: keep.map((i) => y[i]),
        z: keep.map((i) => z[i]),
        customdata: keep.map((i) => l.values[i]),
        marker: {
          size: 3,
          color: keep.map((i) => shownValue(l.values[i]!)),
          colorscale: colorscale(style.colorscale),
          cmin: min,
          cmax: max > min ? max : min + 1,
          showscale: layers.length === 1,
          colorbar: {
            title: { text: log ? "log(1+I)" : "Intensity" },
            thickness: 10,
            len: 0.6,
          },
        },
      });
    } else
      traces.push({
        ...common,
        type: "volume",
        x: volumeIndices.map((i) => x[i]),
        y: volumeIndices.map((i) => y[i]),
        z: volumeIndices.map((i) => z[i]),
        value: volumeIndices.map((i) => shownValue(l.values[i]!)),
        customdata: volumeIndices.map((i) => l.values[i]),
        isomin: cutoff,
        isomax: stats.upper,
        cmin: min,
        cmax: max > min ? max : min + 1,
        colorscale: colorscale(style.colorscale),
        showscale: layers.length === 1,
        colorbar: {
          title: { text: log ? "log(1+I)" : "Intensity" },
          thickness: 10,
          len: 0.6,
        },
        surface: { count: v.quality === "Fast" ? 3 : 10 },
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
      bgcolor: "#101f2e",
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
      xaxis: {
        range: xRange,
        gridcolor: "#294354",
        zerolinecolor: "#405969",
        showbackground: false,
        title: { text: `X (${d.xy_unit})` },
      },
      yaxis: {
        range: yRange,
        gridcolor: "#294354",
        zerolinecolor: "#405969",
        showbackground: false,
        title: { text: `Y (${d.xy_unit})` },
      },
      zaxis: {
        range: zRange.slice().reverse(),
        gridcolor: "#294354",
        zerolinecolor: "#405969",
        showbackground: false,
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

// Polling replaces metadata objects, but the numerical buffers remain immutable.
function sameGeometry(a: VolumeData | null, b: VolumeData) {
  return (
    !!a &&
    a.dataset_generation === b.dataset_generation &&
    a.x === b.x &&
    a.y === b.y &&
    a.z === b.z &&
    a.extent === b.extent &&
    a.block_edges === b.block_edges &&
    a.xy_unit === b.xy_unit &&
    a.z_unit === b.z_unit &&
    a.physical_aspect === b.physical_aspect &&
    a.layers.length === b.layers.length &&
    a.layers.every((l, i) => {
      const other = b.layers[i];
      return (
        l.signal_id === other.signal_id &&
        l.label === other.label &&
        l.values === other.values
      );
    })
  );
}
function renderKey(v: SpatialView) {
  return JSON.stringify([
    v.mode,
    v.page,
    v.quality,
    v.scale,
    v.solo,
    v.frame_stretch,
    v.depth_exaggeration,
    v.mode === "overlay" || v.linked
      ? v.camera.projection
      : v.layers.map((l) => l.camera.projection),
    v.layers.map((l) => [
      l.signal_id,
      l.visible,
      l.colorscale,
      l.opacity,
      l.percentile,
    ]),
  ]);
}
const cameraKey = (c: Camera) =>
  JSON.stringify([
    c.eye.x,
    c.eye.y,
    c.eye.z,
    c.center.x,
    c.center.y,
    c.center.z,
    c.up.x,
    c.up.y,
    c.up.z,
    c.projection,
  ]);

export async function mountSpatial(
  el: HTMLElement,
  onCamera: (id: string, c: Camera) => void,
) {
  const { default: Plotly } = await import("plotly.js-dist-min");
  let disposed = false,
    programmatic = false,
    scenes = new Map<string, string>();
  let previousData: VolumeData | null = null,
    previousRender = "";
  let work = Promise.resolve();
  const appliedCameras = new Map<string, string>();
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
      if (c?.eye && c?.up && c?.center) {
        const camera: Camera = {
          eye: c.eye,
          up: c.up,
          center: c.center,
          projection: c.projection?.type ?? "perspective",
        };
        appliedCameras.set(scene, cameraKey(camera));
        onCamera(id, camera);
      }
    }
  });
  return {
    update(d: VolumeData, v: SpatialView, options: SpatialOptions = {}) {
      // Serialize renderer mutations; completed camera saves must not race a style update.
      work = work
        .catch(() => {})
        .then(async () => {
          if (disposed) return;
          const key = renderKey(v) + ":" + Boolean(options.log);
          programmatic = true;
          try {
            if (key !== previousRender || !sameGeometry(previousData, d)) {
              const f = buildSpatialFigure(d, v, options);
              await Plotly.react(el, f.traces, f.layout, {
                displayModeBar: false,
                responsive: true,
                scrollZoom: true,
              });
              if (disposed) return;
              scenes = f.scenes;
              previousData = d;
              previousRender = key;
              appliedCameras.clear();
              for (const [scene, id] of scenes) {
                const camera =
                  v.mode === "overlay" || v.linked
                    ? v.camera
                    : v.layers.find((l) => l.signal_id === id)!.camera;
                appliedCameras.set(scene, cameraKey(camera));
              }
            } else {
              const patch: Record<string, unknown> = {};
              for (const [scene, id] of scenes) {
                const camera =
                  v.mode === "overlay" || v.linked
                    ? v.camera
                    : v.layers.find((l) => l.signal_id === id)!.camera;
                const key = cameraKey(camera);
                if (appliedCameras.get(scene) !== key) {
                  patch[`${scene}.camera`] = plotCamera(camera);
                }
              }
              if (Object.keys(patch).length) {
                await Plotly.relayout(el, patch);
                for (const [scene, id] of scenes) {
                  const camera =
                    v.mode === "overlay" || v.linked
                      ? v.camera
                      : v.layers.find((l) => l.signal_id === id)!.camera;
                  appliedCameras.set(scene, cameraKey(camera));
                }
              }
            }
          } finally {
            programmatic = false;
          }
        });
      return work;
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
