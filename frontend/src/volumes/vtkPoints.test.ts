import { describe, expect, it } from "vitest";
import { buildVtkPoints } from "./vtkPoints";
import { defaultLayer, type VolumeData } from "./spatialRenderer";

describe("vtk point preview", () => {
  it("keeps only finite covered samples at the original coordinates and cutoff", () => {
    const data = {
      x: [0, 2],
      y: [0, 3],
      z: [0, 4],
      extent: [2, 3, 4],
      xy_unit: "pixel",
      z_unit: "frame",
      physical_aspect: false,
      layers: [
        {
          signal_id: "a",
          values: [null, 0, 1, 2, 3, 4, 5, 6],
          coverage: [0, 1, 1, 1, 1, 1, 1, 1],
        },
      ],
    } as VolumeData;
    const result = buildVtkPoints(
      data,
      data.layers[0],
      { ...defaultLayer("a"), percentile: 100 },
      false,
      [2 / 3, 1, 1.2],
    );
    expect(result.positions).toEqual([2 / 3, 1, 1.2]);
    expect(result.intensities).toEqual([6]);
  });
  it("does not invent points for missing coverage and retains partial samples", () => {
    const data = {
      x: [1, 3],
      y: [1, 3],
      z: [2],
      extent: [4, 4, 0],
      xy_unit: "pixel",
      z_unit: "frame",
      physical_aspect: false,
      layers: [
        { signal_id: "a", values: [5, 10, null, 20], coverage: [1, 0.5, 0, 0] },
      ],
    } as VolumeData;
    const result = buildVtkPoints(
      data,
      data.layers[0],
      { ...defaultLayer("a"), percentile: 0 },
      false,
      [1, 1, 1],
    );
    expect(result.positions).toEqual([0, 0, 0.5, 1, 0, 0.5]);
    expect(result.intensities).toEqual([5, 10]);
  });
  it("keeps constant zero and negative samples in a thin linear-scale selection", () => {
    const data = {
      x: [0, 1],
      y: [0],
      z: [3],
      extent: [2, 1, 0],
      xy_unit: "pixel",
      z_unit: "frame",
      physical_aspect: false,
      layers: [{ signal_id: "a", values: [-2, 0], coverage: [1, 1] }],
    } as VolumeData;
    const result = buildVtkPoints(
      data,
      data.layers[0],
      { ...defaultLayer("a"), percentile: 0 },
      false,
      [1, 1, 1],
    );
    expect(result.positions).toEqual([0, 0.5, 0.5, 1, 0.5, 0.5]);
    expect(result.intensities).toEqual([-2, 0]);
  });
});
