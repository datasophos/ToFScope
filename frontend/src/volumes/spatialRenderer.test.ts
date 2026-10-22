import { describe, it, expect } from "vitest";
import { buildSpatialFigure } from "./spatialRenderer";
import type { VolumeData, SpatialView } from "./spatialRenderer";
const camera = {
  eye: { x: 1.25, y: 1.25, z: 1.25 },
  up: { x: 0, y: 0, z: 1 },
  center: { x: 0, y: 0, z: 0 },
  projection: "perspective" as const,
};
const view: SpatialView = {
  screen: "volume",
  layers: [
    {
      signal_id: "a",
      visible: true,
      colorscale: "Reds",
      opacity: 0.3,
      percentile: 0,
      camera,
    },
  ],
  mode: "overlay",
  quality: "Fast",
  scale: "independent",
  linked: true,
  camera,
  solo: null,
  page: 0,
  frame_stretch: 1.2,
  depth_exaggeration: 1,
};
const data: VolumeData = {
  analysis_id: "x",
  revision: 0,
  dataset_generation: "g",
  x: [5, 15],
  y: [5, 15],
  z: [0, 0.01, 0.03],
  frame_centers: [0, 1, 2],
  block_edges: [
    [0, 1, 2, 3],
    [0, 1, 2],
    [0, 1, 2],
  ],
  shape: [3, 2, 2],
  xy_unit: "µm",
  z_unit: "µm",
  extent: [20, 20, 0.03],
  physical_aspect: true,
  omitted_frames: 0,
  total_voxels: 12,
  layers: [
    {
      signal_id: "a",
      label: "A",
      frames: [0, 2],
      values: [null, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
      coverage: Array(12).fill(1),
      valid_counts: Array(12).fill(1),
    },
  ],
};
describe("spatial scientific adapter", () => {
  it("preserves nonuniform coordinates and missing intensities", () => {
    const f = buildSpatialFigure(data, view);
    const t = f.traces[0];
    expect(t.type).toBe("scatter3d");
    expect([...new Set(t.z)]).toEqual([0, 0.01, 0.03]);
    expect(t.marker.color).toEqual(data.layers[0].values.slice(1));
    expect(f.layout.scene.aspectratio.z).toBeCloseTo(0.03 / 20);
  });
  it("falls back for one finite covered plane and constant zero", () => {
    const d = {
      ...data,
      layers: [
        {
          ...data.layers[0],
          values: [null, null, null, null, 0, 0, 0, 0, null, null, null, null],
        },
      ],
    };
    const f = buildSpatialFigure(d, view);
    expect(f.traces[0].type).toBe("scatter3d");
    expect(f.traces[0].marker.color).toEqual([0, 0, 0, 0]);
    expect(f.traces[0].z).toEqual([0.01, 0.01, 0.01, 0.01]);
  });
  it("shares numerical scale over all pages, bounds scenes to four, retains IDs", () => {
    const layers = Array.from({ length: 6 }, (_, i) => ({
      ...data.layers[0],
      signal_id: String(i),
      values: data.layers[0].values.map((x) =>
        x === null ? null : x * (i + 1),
      ),
    }));
    const styles = layers.map((l) => ({
      ...view.layers![0],
      signal_id: l.signal_id,
    }));
    const f = buildSpatialFigure(
      { ...data, layers },
      { ...view, layers: styles, mode: "tiles", scale: "shared", page: 1 },
    );
    expect(f.traces).toHaveLength(2);
    expect(f.traces.map((t) => t.uid)).toEqual(["4", "5"]);
    expect(f.traces[0].marker.cmax).toBe(66);
  });
});
