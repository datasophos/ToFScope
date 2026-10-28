import { describe, it, expect } from "vitest";
import { buildSpatialFigure, volumeDisplayStats } from "./spatialRenderer";
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
    expect(f.traces[0].marker.cmax).toBeCloseTo(64.83);
  });
});

it("Fast reduces surface rendering work while preserving preview coordinates and values", () => {
  const complete = {
    ...data,
    layers: [
      { ...data.layers[0], values: Array.from({ length: 12 }, (_, i) => i) },
    ],
  };
  const fast = buildSpatialFigure(complete, view).traces[0];
  const detailed = buildSpatialFigure(complete, {
    ...view,
    quality: "Detailed",
  }).traces[0];
  expect(fast.type).toBe("volume");
  expect(fast.surface.count).toBe(3);
  expect(detailed.surface.count).toBe(10);
  expect(fast.value).toEqual(detailed.value);
  expect(fast.z).toEqual(detailed.z);
  expect(fast.x).toEqual(detailed.x);
  expect(fast.y).toEqual(detailed.y);
});

it("matches prototype nonzero percentile thresholds and robust display limits", () => {
  const values = [...Array(1000).fill(0), 1, 2, 3, 1000];
  expect(volumeDisplayStats(values, 10, false).threshold).toBeCloseTo(1.3);
  const outlier = volumeDisplayStats(
    [...Array.from({ length: 1000 }, (_, i) => i + 1), 1e9],
    70,
    false,
  );
  expect(outlier.upper).toBeCloseTo(998);
  const log = volumeDisplayStats([0, 1, 3], 50, true);
  expect(log.lower).toBeCloseTo((Math.log(2) + Math.log(4)) / 2);
  expect(log.threshold).toBeCloseTo(Math.sqrt(8) - 1);
});
it("restores dark depth-down display while retaining original hover values", () => {
  const complete = {
    ...data,
    layers: [
      { ...data.layers[0], values: Array.from({ length: 12 }, (_, i) => i) },
    ],
  };
  const f = buildSpatialFigure(complete, view, { log: true });
  expect(f.traces[0].value[5]).toBeCloseTo(Math.log1p(5));
  expect(f.traces[0].customdata[5]).toBe(5);
  expect(complete.layers[0].values[5]).toBe(5);
  expect(f.layout.paper_bgcolor).toBe("#101f2e");
  expect(f.layout.scene.zaxis.range).toEqual([0.03, 0]);
});
