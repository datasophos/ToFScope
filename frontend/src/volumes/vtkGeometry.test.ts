import { describe, it, expect } from "vitest";
import { vtkDisplayExtent, vtkSampleDistance } from "./vtkGeometry";
import type { VolumeData, SpatialView } from "./spatialRenderer";
describe("vtk physical proportions", () => {
  it("uses the distance between sample centers for each axis", () => {
    const data = {
      x: [0.5, 9.5],
      y: [0.5, 9.5],
      z: [0, 5],
      extent: [10, 10, 5],
      physical_aspect: true,
    } as VolumeData;
    const view = { frame_stretch: 1.2, depth_exaggeration: 1 } as SpatialView;
    expect(vtkDisplayExtent(data, view)).toEqual([0.9, 0.9, 0.5]);
  });
  it("uses depth exaggeration for calibrated depth without XY calibration", () => {
    const d = {
      x: [0, 1],
      y: [0, 1],
      z: [0, 3],
      z_unit: "µm",
      extent: [2, 2, 3],
      physical_aspect: false,
    } as VolumeData;
    const v = { frame_stretch: 2, depth_exaggeration: 7 } as SpatialView;
    expect(vtkDisplayExtent(d, v)[2]).toBe(7);
  });
  it("bounds the number of sampling steps for very thin volumes", () => {
    const e: [number, number, number] = [1, 1, 0.001];
    expect(Math.hypot(...e) / vtkSampleDistance(e)).toBeLessThanOrEqual(1000);
  });
});
