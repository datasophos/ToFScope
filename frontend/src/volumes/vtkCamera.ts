import type { Camera } from "./spatialRenderer";
type Vec = [number, number, number];
export type VtkCamera = {
  position: Vec;
  focalPoint: Vec;
  viewUp: Vec;
  projection: Camera["projection"];
};
const cameraScale = (extent: Vec) => 1.5 * Math.max(1, ...extent);
export function toVtkCamera(c: Camera, extent: Vec): VtkCamera {
  const scale = cameraScale(extent);
  const middle = extent.map((x) => x / 2) as Vec;
  const focalPoint: Vec = [
    middle[0] + scale * c.center.x,
    middle[1] + scale * c.center.y,
    middle[2] - scale * c.center.z,
  ];
  return {
    focalPoint,
    position: [
      focalPoint[0] + scale * c.eye.x,
      focalPoint[1] + scale * c.eye.y,
      focalPoint[2] - scale * c.eye.z,
    ],
    viewUp: [c.up.x, c.up.y, -c.up.z],
    projection: c.projection,
  };
}
export function fromVtkCamera(v: VtkCamera, extent: Vec): Camera {
  const scale = cameraScale(extent);
  const middle = extent.map((x) => x / 2);
  return {
    center: {
      x: (v.focalPoint[0] - middle[0]) / scale,
      y: (v.focalPoint[1] - middle[1]) / scale,
      z: (middle[2] - v.focalPoint[2]) / scale,
    },
    eye: {
      x: (v.position[0] - v.focalPoint[0]) / scale,
      y: (v.position[1] - v.focalPoint[1]) / scale,
      z: (v.focalPoint[2] - v.position[2]) / scale,
    },
    up: { x: v.viewUp[0], y: v.viewUp[1], z: -v.viewUp[2] },
    projection: v.projection,
  };
}
