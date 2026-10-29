import {
  layerRange,
  volumeDisplayStats,
  type VolumeData,
  type SpatialLayer,
} from "./spatialRenderer";
import { resampleDepth } from "./depthResampling";

function regular(axis: number[]) {
  if (
    axis.length < 2 ||
    axis.some((x, i) => !Number.isFinite(x) || (i > 0 && x <= axis[i - 1]))
  )
    return false;
  const step = (axis[axis.length - 1] - axis[0]) / (axis.length - 1);
  return axis.every(
    (x, i) =>
      Math.abs(x - (axis[0] + step * i)) <=
      Math.max(
        Number.EPSILON *
          Math.max(Math.abs(axis[0]), Math.abs(axis.at(-1)!), Math.abs(step)) *
          16,
        Math.abs(step) * 1e-5,
      ),
  );
}
export type VtkVolumeData = Omit<
  VolumeData,
  "layers" | "frame_centers" | "block_edges"
> & {
  layers: Array<
    Pick<VolumeData["layers"][number], "signal_id" | "label" | "values">
  >;
};
type Prepared =
  | {
      kind: "vtk";
      data: VtkVolumeData;
      resampled: boolean;
      resampledXY?: boolean;
      resampledDepth?: boolean;
    }
  | { kind: "fallback"; reason: string };
function validAxis(axis: number[]) {
  return (
    axis.length >= 2 &&
    axis.every((v, i) => Number.isFinite(v) && (i === 0 || v > axis[i - 1]))
  );
}

function uniformAxis(axis: number[]) {
  return axis.map(
    (_, i) => axis[0] + ((axis.at(-1)! - axis[0]) * i) / (axis.length - 1),
  );
}

function axisWeights(axis: number[], target: number[]) {
  let lo = 0;
  return target.map((v) => {
    while (lo < axis.length - 2 && v > axis[lo + 1]) lo++;
    return { lo, alpha: (v - axis[lo]) / (axis[lo + 1] - axis[lo]) };
  });
}

export function prepareVtkPreview(data: VolumeData): Prepared {
  if (!validAxis(data.x) || !validAxis(data.y) || !validAxis(data.z))
    return {
      kind: "fallback",
      reason: "This geometry requires point rendering.",
    };
  if (!data.layers.length)
    return {
      kind: "fallback",
      reason: "No visible signals.",
    };
  const plane = data.x.length * data.y.length;
  if (
    data.layers.some(
      (l) =>
        l.values.length !== plane * data.z.length ||
        l.coverage.length !== l.values.length ||
        l.coverage.some((v) => !Number.isFinite(v) || v < 1) ||
        l.values.some((v) => v === null || !Number.isFinite(v)),
    )
  )
    return {
      kind: "fallback",
      reason: "Missing or incomplete coverage requires point rendering.",
    };
  if (
    data.layers.some((layer) =>
      layer.values.some((value) => value !== null && value < 0),
    )
  )
    return {
      kind: "fallback",
      reason: "Negative intensities require point rendering.",
    };
  if (
    data.layers.some((layer) =>
      layer.values.every((v) => v === layer.values[0]),
    )
  )
    return {
      kind: "fallback",
      reason: "Constant signals require point rendering.",
    };
  const resampledXY = !regular(data.x) || !regular(data.y);
  const resampledDepth = !regular(data.z);
  if (!resampledXY && !resampledDepth)
    return { kind: "vtk", data, resampled: false };
  const x = resampledXY ? uniformAxis(data.x) : data.x;
  const y = resampledXY ? uniformAxis(data.y) : data.y;
  const xWeights = axisWeights(data.x, x),
    yWeights = axisWeights(data.y, y);
  const xyValues = data.layers.map((layer) => {
    if (!resampledXY) return layer.values;
    const out: number[] = [];
    for (let z = 0; z < data.z.length; z++)
      for (const yw of yWeights)
        for (const xw of xWeights) {
          const index = z * plane + yw.lo * data.x.length + xw.lo;
          const a = layer.values[index]!,
            b = layer.values[index + 1]!;
          const c = layer.values[index + data.x.length]!,
            d = layer.values[index + data.x.length + 1]!;
          out.push(
            (a + (b - a) * xw.alpha) * (1 - yw.alpha) +
              (c + (d - c) * xw.alpha) * yw.alpha,
          );
        }
    return out;
  });
  const budget = Math.floor(500000 / (plane * data.layers.length));
  const count = resampledDepth
    ? Math.min(2 * data.z.length - 1, budget)
    : data.z.length;
  if (count < 2)
    return {
      kind: "fallback",
      reason: "This preview exceeds the vtk display budget.",
    };
  const interpolated = xyValues.map((values) =>
    resampledDepth
      ? resampleDepth(data.z, values, plane, count)
      : { z: data.z, values },
  );
  const layers = data.layers.map((l, i) => ({
    signal_id: l.signal_id,
    label: l.label,
    values: interpolated[i].values,
  }));
  const {
    frame_centers: _frameCenters,
    block_edges: _blockEdges,
    ...displayData
  } = data;
  const z = interpolated[0].z;
  return {
    kind: "vtk",
    resampled: true,
    resampledXY,
    resampledDepth,
    data: {
      ...displayData,
      x,
      y,
      z,
      layers,
      shape: [count, data.y.length, data.x.length],
      total_voxels: count * plane * layers.length,
    },
  };
}

// A cutoff at the highest value produces no visible volume; preserve point fallback.
export function canRenderVtkStyles(
  data: VolumeData,
  styles: SpatialLayer[],
  log: boolean,
  display: VtkVolumeData = data,
): boolean {
  return data.layers.every((layer) => {
    const style = styles.find((s) => s.signal_id === layer.signal_id);
    if (!style) return false;
    const rendered = display.layers.find(
      (l) => l.signal_id === layer.signal_id,
    );
    if (!rendered) return false;
    const max = layerRange(rendered.values)[1];
    const displayedMax = log ? Math.log1p(Math.max(max, 0)) : max;
    return (
      volumeDisplayStats(layer.values, style.percentile, log).lower <
      displayedMax
    );
  });
}
