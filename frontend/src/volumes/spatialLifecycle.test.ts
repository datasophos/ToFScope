import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  mountSpatial,
  defaultCamera,
  defaultLayer,
  type SpatialView,
  type VolumeData,
} from "./spatialRenderer";
const renderer = vi.hoisted(() => ({
  newPlot: vi.fn(async () => {}),
  react: vi.fn(async () => {}),
  relayout: vi.fn(async () => {}),
  purge: vi.fn(),
  Plots: { resize: vi.fn() },
}));
vi.mock("plotly.js-dist-min", () => ({ default: renderer }));
const view: SpatialView = {
  screen: "volume",
  layers: [defaultLayer("a")],
  mode: "overlay",
  quality: "Fast",
  scale: "independent",
  linked: true,
  camera: defaultCamera,
  solo: null,
  page: 0,
  frame_stretch: 1.2,
  depth_exaggeration: 1,
};
const data: VolumeData = {
  analysis_id: "x",
  revision: 0,
  dataset_generation: "g",
  x: [0, 1],
  y: [0, 1],
  z: [0, 1],
  frame_centers: [0, 1],
  block_edges: [
    [0, 1, 2],
    [0, 1, 2],
    [0, 1, 2],
  ],
  shape: [2, 2, 2],
  xy_unit: "pixel",
  z_unit: "frame",
  extent: [2, 2, 1],
  physical_aspect: false,
  omitted_frames: 0,
  total_voxels: 8,
  layers: [
    {
      signal_id: "a",
      label: "A",
      frames: [0, 1],
      values: [0, 1, 2, 3, 4, 5, 6, 7],
      coverage: Array(8).fill(1),
      valid_counts: Array(8).fill(1),
    },
  ],
};
const element = () => ({ on: vi.fn() }) as unknown as HTMLElement;
describe("volume renderer lifecycle", () => {
  beforeEach(() => vi.clearAllMocks());
  it("does no renderer work when polling returns equivalent metadata", async () => {
    const h = await mountSpatial(element(), () => {});
    await h.update(data, view);
    await h.update(
      { ...data, revision: 1, layers: data.layers.map((l) => ({ ...l })) },
      JSON.parse(JSON.stringify(view)),
    );
    expect(renderer.react).toHaveBeenCalledTimes(1);
    expect(renderer.relayout).not.toHaveBeenCalled();
    h.destroy();
  });
  it("moves cameras without rebuilding volume geometry", async () => {
    const h = await mountSpatial(element(), () => {});
    await h.update(data, view);
    const camera = { ...defaultCamera, eye: { x: 2, y: 1, z: 1 } };
    await h.update(data, { ...view, camera });
    expect(renderer.react).toHaveBeenCalledTimes(1);
    expect(renderer.relayout).toHaveBeenCalledTimes(1);
    h.destroy();
  });
  it("does not redraw an echoed native camera movement", async () => {
    const el = element(),
      changed = vi.fn(),
      h = await mountSpatial(el, changed);
    await h.update(data, view);
    const callback = ((el as any).on as any).mock.calls[0][1];
    const camera = { ...defaultCamera, eye: { x: 2, y: 1, z: 1 } };
    callback({
      "scene.camera": { ...camera, projection: { type: "perspective" } },
    });
    await h.update(data, { ...view, camera });
    expect(changed).toHaveBeenCalledOnce();
    expect(renderer.react).toHaveBeenCalledTimes(1);
    expect(renderer.relayout).not.toHaveBeenCalled();
    h.destroy();
  });
  it("rebuilds when numerical data or styles change", async () => {
    const h = await mountSpatial(element(), () => {});
    await h.update(data, view);
    await h.update(
      {
        ...data,
        layers: [{ ...data.layers[0], values: [1, 2, 3, 4, 5, 6, 7, 8] }],
      },
      view,
    );
    expect(renderer.react).toHaveBeenCalledTimes(2);
    h.destroy();
  });
});
