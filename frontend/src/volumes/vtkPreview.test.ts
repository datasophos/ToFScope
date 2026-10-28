import { describe, expect, it } from "vitest";
import { prepareVtkPreview } from "./vtkPreview";
import type { VolumeData } from "./spatialRenderer";

const data: VolumeData = {
  analysis_id: "a",
  revision: 0,
  dataset_generation: "g",
  x: [0, 1],
  y: [0, 1],
  z: [0, 10, 30],
  frame_centers: [0, 1, 2],
  block_edges: [
    [0, 1, 2, 3],
    [0, 1, 2],
    [0, 1, 2],
  ],
  shape: [3, 2, 2],
  xy_unit: "µm",
  z_unit: "µm",
  extent: [2, 2, 30],
  physical_aspect: true,
  omitted_frames: 0,
  total_voxels: 12,
  layers: [
    {
      signal_id: "s",
      label: "s",
      frames: [0, 2],
      values: [0, 0, 0, 0, 10, 10, 10, 10, 30, 30, 30, 30],
      coverage: Array(12).fill(1),
      valid_counts: Array(12).fill(1),
    },
  ],
};
describe("vtk preview preparation", () => {
  it("admits the 1301-frame, 128-by-128 detailed preview with partial edge blocks", () => {
    const xy = Array.from({ length: 43 }, (_, i) =>
      i === 42 ? 126.5 : 3 * i + 1,
    );
    const z = Array.from({ length: 145 }, (_, i) =>
      i === 144 ? 1298 : 9 * i + 4,
    );
    const values = z.flatMap((depth) =>
      xy.flatMap((y) => xy.map((x) => depth + y + x)),
    );
    const source: VolumeData = {
      ...data,
      x: xy,
      y: xy,
      z,
      z_unit: "frame",
      shape: [145, 43, 43],
      layers: [
        { ...data.layers[0], values, coverage: Array(values.length).fill(1) },
      ],
    };
    const result = prepareVtkPreview(source);
    expect(result.kind).toBe("vtk");
    if (result.kind !== "vtk") return;
    expect(result.resampledXY).toBe(true);
    expect(result.resampledDepth).toBe(true);
    expect(result.data.total_voxels).toBeLessThanOrEqual(500000);
    expect(result.data.layers[0].values.at(-1)).toBe(1551);
  });
  it("interpolates uneven XY block centers and frame centers without changing source", () => {
    const axis = [0, 2, 3];
    const values = axis.flatMap((z) =>
      axis.flatMap((y) => axis.map((x) => x + 2 * y + 3 * z)),
    );
    const source: VolumeData = {
      ...data,
      x: axis,
      y: axis,
      z: axis,
      z_unit: "frame",
      shape: [3, 3, 3],
      layers: [{ ...data.layers[0], values, coverage: Array(27).fill(1) }],
    };
    const result = prepareVtkPreview(source);
    expect(result.kind).toBe("vtk");
    if (result.kind !== "vtk") return;
    expect(result.resampled).toBe(true);
    expect(result.data.x).toEqual([0, 1.5, 3]);
    expect(result.data.y).toEqual([0, 1.5, 3]);
    expect(result.data.z).toEqual([0, 0.75, 1.5, 2.25, 3]);
    expect(result.data.layers[0].values[2 * 9 + 1 * 3 + 1]).toBeCloseTo(9);
    expect(result.data.layers[0].values.at(-1)).toBe(18);
    expect(source.layers[0].values).toEqual(values);
  });
  it("resamples nonuniform depth in physical coordinates without changing source", () => {
    const result = prepareVtkPreview(data);
    expect(result.kind).toBe("vtk");
    if (result.kind !== "vtk") return;
    expect(result.resampled).toBe(true);
    expect("coverage" in result.data.layers[0]).toBe(false);
    expect("frame_centers" in result.data).toBe(false);
    expect(result.data.z).toEqual([0, 7.5, 15, 22.5, 30]);
    expect(result.data.layers[0].values.filter((_, i) => i % 4 === 0)).toEqual([
      0, 7.5, 15, 22.5, 30,
    ]);
    expect(data.z).toEqual([0, 10, 30]);
    expect(data.layers[0].values[4]).toBe(10);
  });
  it("detects nonuniform spacing even at very small physical depths", () => {
    const result = prepareVtkPreview({ ...data, z: [0, 1e-9, 3e-9] });
    expect(result.kind).toBe("vtk");
    if (result.kind === "vtk") expect(result.resampled).toBe(true);
  });
  it("retains uniform previews without changing values", () => {
    const result = prepareVtkPreview({ ...data, z: [0, 10, 20] });
    expect(result.kind).toBe("vtk");
    if (result.kind === "vtk") expect(result.resampled).toBe(false);
  });
  it("falls back for negative-valued signals", () => {
    const layer = {
      ...data.layers[0],
      values: [-1, ...data.layers[0].values.slice(1)],
    };
    expect(prepareVtkPreview({ ...data, layers: [layer] }).kind).toBe(
      "fallback",
    );
  });
  it("falls back for a constant layer so it remains visible", () => {
    const layer = { ...data.layers[0], values: Array(12).fill(5) };
    expect(prepareVtkPreview({ ...data, layers: [layer] }).kind).toBe(
      "fallback",
    );
  });
  it("falls back when pooled voxels have partial coverage", () => {
    const layer = {
      ...data.layers[0],
      coverage: [0.5, ...data.layers[0].coverage.slice(1)],
    };
    expect(prepareVtkPreview({ ...data, layers: [layer] }).kind).toBe(
      "fallback",
    );
  });
  it("uses points for missing data and admits multiple complete layers", () => {
    expect(
      prepareVtkPreview({
        ...data,
        layers: [
          {
            ...data.layers[0],
            values: [null, ...data.layers[0].values.slice(1)],
          },
        ],
      }).kind,
    ).toBe("fallback");
    expect(
      prepareVtkPreview({
        ...data,
        layers: Array.from({ length: 4 }, (_, i) => ({
          ...data.layers[0],
          signal_id: String(i),
        })),
      }).kind,
    ).toBe("vtk");
  });
});
