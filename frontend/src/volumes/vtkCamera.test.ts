import { describe, it, expect } from "vitest";
import {
  toVtkCamera,
  fromVtkCamera,
  presetCamera,
  rotateCamera,
} from "./vtkCamera";
import { defaultCamera } from "./spatialRenderer";
describe("vtk camera mapping", () => {
  it("round trips saved perspective and orthographic cameras without reversing depth", () => {
    for (const projection of ["perspective", "orthographic"] as const) {
      const c = {
        ...defaultCamera,
        projection,
        center: { x: 0.3, y: -0.2, z: 0.1 },
        eye: { x: 1.2, y: -1.1, z: 0.8 },
      };
      const roundtrip = fromVtkCamera(toVtkCamera(c, [1, 2, 3]), [1, 2, 3]);
      expect(roundtrip.projection).toBe(projection);
      for (const v of ["eye", "center", "up"] as const)
        for (const a of ["x", "y", "z"] as const)
          expect(roundtrip[v][a]).toBeCloseTo(c[v][a], 10);
    }
  });
  it("keeps the camera outside highly stretched data", () => {
    const v = toVtkCamera(defaultCamera, [1, 1, 100]);
    expect(Math.abs(v.position[2] - v.focalPoint[2])).toBeGreaterThan(50);
    const restored = fromVtkCamera(v, [1, 1, 100]);
    expect(restored.eye.z).toBeCloseTo(defaultCamera.eye.z);
  });
});

describe("precise camera controls", () => {
  it("sets a top view without changing zoom, center, or projection", () => {
    const c = {
      ...defaultCamera,
      center: { x: 0.2, y: 0.1, z: -0.1 },
      projection: "orthographic" as const,
    };
    const top = presetCamera(c, "top");
    expect(top.eye.x).toBeCloseTo(0);
    expect(top.eye.y).toBeCloseTo(0);
    expect(top.eye.z).toBeCloseTo(Math.hypot(1.5, 1.5, 0.9));
    expect(top.up).toEqual({ x: 0, y: 1, z: 0 });
    expect(top.center).toEqual(c.center);
    expect(top.projection).toBe("orthographic");
  });
  it("orients each preset along its named axis with a perpendicular up vector", () => {
    for (const [name, eye] of [
      ["top", [0, 0, 1]],
      ["bottom", [0, 0, -1]],
      ["front", [0, -1, 0]],
      ["back", [0, 1, 0]],
      ["left", [-1, 0, 0]],
      ["right", [1, 0, 0]],
    ] as const) {
      const c = presetCamera(defaultCamera, name);
      const length = Math.hypot(c.eye.x, c.eye.y, c.eye.z);
      expect([c.eye.x / length, c.eye.y / length, c.eye.z / length]).toEqual(
        eye,
      );
      expect(c.eye.x * c.up.x + c.eye.y * c.up.y + c.eye.z * c.up.z).toBe(0);
    }
  });
  it("rolls the view around its sightline and reverses cleanly", () => {
    const c = { ...defaultCamera, eye: { x: 0, y: -2, z: 0 } };
    const rolled = rotateCamera(c, "roll", -90);
    expect(rolled.eye.x).toBeCloseTo(0);
    expect(rolled.eye.y).toBeCloseTo(-2);
    expect(rolled.up.x).toBeCloseTo(1);
    expect(rolled.up.z).toBeCloseTo(0);
    const restored = rotateCamera(rolled, "roll", 90);
    expect(restored.up.z).toBeCloseTo(1);
    expect(restored.center).toEqual(c.center);
  });
  it("rotates vertically without changing the viewing distance", () => {
    const c = { ...defaultCamera, eye: { x: 0, y: -2, z: 0 } };
    const rotated = rotateCamera(c, "vertical", -90);
    expect(rotated.eye.z).toBeCloseTo(2);
    expect(Math.hypot(rotated.eye.x, rotated.eye.y, rotated.eye.z)).toBeCloseTo(
      2,
    );
    expect(rotated.up.y).toBeCloseTo(1);
  });
  it("rotates around the view-up axis by a fixed angle and back", () => {
    const c = { ...defaultCamera, eye: { x: 0, y: -2, z: 0 } };
    const rotated = rotateCamera(c, "horizontal", 90);
    expect(rotated.eye.x).toBeCloseTo(2);
    expect(rotated.eye.y).toBeCloseTo(0);
    expect(rotated.eye.z).toBeCloseTo(0);
    const restored = rotateCamera(rotated, "horizontal", -90);
    expect(restored.eye.y).toBeCloseTo(-2);
    expect(restored.up.z).toBeCloseTo(1);
  });
});
