import {
  volumeDisplayStats,
  type SpatialLayer,
  type VolumeData,
} from "./spatialRenderer";

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
  const cutoff = volumeDisplayStats(layer.values, style.percentile, log).lower;
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
