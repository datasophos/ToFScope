import type { VolumeData, SpatialView } from "./spatialRenderer";
export function vtkDisplayExtent(
  data: Pick<
    VolumeData,
    "x" | "y" | "z" | "extent" | "physical_aspect" | "z_unit"
  >,
  view: SpatialView,
): [number, number, number] {
  const span = (axis: number[]) => axis[axis.length - 1] - axis[0];
  const xy = Math.max(data.extent[0], data.extent[1], 1e-12);
  return [
    (span(data.x) || data.extent[0] || xy) / xy,
    (span(data.y) || data.extent[1] || xy) / xy,
    data.physical_aspect
      ? ((span(data.z) || xy) / xy) * view.depth_exaggeration
      : data.z_unit === "frame"
        ? view.frame_stretch
        : view.depth_exaggeration,
  ];
}

/** Cap ray steps at 1,000 across the volume diagonal to bound GPU work. */
export function vtkSampleDistance(extent: [number, number, number]): number {
  return Math.max(
    Math.min(...extent) / 200,
    Math.hypot(...extent) / 1000,
    1e-6,
  );
}
export function vtkSamplingLimited(extent: [number, number, number]): boolean {
  return (
    vtkSampleDistance(extent) >
    Math.max(Math.min(...extent) / 200, 1e-6) * (1 + 1e-9)
  );
}
