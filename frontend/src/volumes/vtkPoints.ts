import {
  levelStats,
  type SpatialLayer,
  type VolumeData,
} from "./spatialRenderer";
import { vtkColorStops } from "./vtkColors";

export function pointColors(
  values: number[],
  lower: number,
  upper: number,
  scale: string,
  reversed: boolean,
) {
  const stops = vtkColorStops(scale, reversed);
  const out = new Uint8Array(values.length * 4);
  values.forEach((value, i) => {
    const t = Math.max(0, Math.min(1, (value - lower) / (upper - lower)));
    let j = 1;
    while (j < stops.length - 1 && stops[j][0] < t) j++;
    const a = stops[j - 1],
      b = stops[j];
    const fraction = (t - a[0]) / (b[0] - a[0]);
    for (let c = 1; c <= 3; c++)
      out[i * 4 + c - 1] = Math.round(a[c] + (b[c] - a[c]) * fraction);
    out[i * 4 + 3] = Math.round(t * 255);
  });
  return out;
}

/** Build display-space points without interpolating across missing samples. */
export function buildVtkPoints(
  data: VolumeData,
  layer: VolumeData["layers"][number],
  style: SpatialLayer,
  log: boolean,
  extent: [number, number, number],
) {
  const positions: number[] = [],
    intensities: number[] = [];
  const cutoff = levelStats(layer.values, style, log).lower;
  const axes = [data.x, data.y, data.z];
  const coordinate = (axis: number[], i: number, length: number) =>
    axis.length < 2
      ? length / 2
      : ((axis[i] - axis[0]) / (axis.at(-1)! - axis[0])) * length;
  for (let z = 0; z < data.z.length; z++)
    for (let y = 0; y < data.y.length; y++)
      for (let x = 0; x < data.x.length; x++) {
        const i = (z * data.y.length + y) * data.x.length + x;
        const value = layer.values[i];
        if (
          value === null ||
          !Number.isFinite(value) ||
          !(layer.coverage[i] > 0)
        )
          continue;
        const shown = log ? Math.log1p(Math.max(value, 0)) : value;
        if (shown < cutoff) continue;
        positions.push(
          coordinate(axes[0], x, extent[0]),
          coordinate(axes[1], y, extent[1]),
          coordinate(axes[2], z, extent[2]),
        );
        intensities.push(shown);
      }
  return { positions, intensities };
}
