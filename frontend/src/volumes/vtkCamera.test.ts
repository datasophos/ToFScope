import { describe, it, expect } from "vitest";
import { toVtkCamera, fromVtkCamera } from "./vtkCamera";
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
