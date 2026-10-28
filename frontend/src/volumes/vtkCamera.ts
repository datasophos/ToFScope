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

type Vector = Camera["eye"];
type Preset = "top" | "bottom" | "front" | "back" | "left" | "right";
const cross = (a: Vector, b: Vector): Vector => ({
  x: a.y * b.z - a.z * b.y,
  y: a.z * b.x - a.x * b.z,
  z: a.x * b.y - a.y * b.x,
});
const unit = (v: Vector): Vector => {
  const length = Math.hypot(v.x, v.y, v.z);
  return { x: v.x / length, y: v.y / length, z: v.z / length };
};
export function presetCamera(c: Camera, preset: Preset): Camera {
  const distance = Math.hypot(c.eye.x, c.eye.y, c.eye.z);
  const directions: Record<Preset, Vector> = {
    top: { x: 0, y: 0, z: 1 },
    bottom: { x: 0, y: 0, z: -1 },
    front: { x: 0, y: -1, z: 0 },
    back: { x: 0, y: 1, z: 0 },
    left: { x: -1, y: 0, z: 0 },
    right: { x: 1, y: 0, z: 0 },
  };
  const d = directions[preset];
  return {
    ...c,
    eye: { x: d.x * distance, y: d.y * distance, z: d.z * distance },
    up:
      preset === "top"
        ? { x: 0, y: 1, z: 0 }
        : preset === "bottom"
          ? { x: 0, y: -1, z: 0 }
          : { x: 0, y: 0, z: 1 },
  };
}
export function rotateCamera(
  c: Camera,
  axis: "horizontal" | "vertical" | "roll",
  degrees: number,
): Camera {
  const direction = unit(c.eye);
  const right = unit(cross(c.up, direction));
  const up = unit(cross(direction, right));
  const rotationAxis =
    axis === "horizontal" ? up : axis === "vertical" ? right : direction;
  const angle = (degrees * Math.PI) / 180;
  const rotate = (v: Vector): Vector => {
    const crossProduct = cross(rotationAxis, v);
    const dot =
      rotationAxis.x * v.x + rotationAxis.y * v.y + rotationAxis.z * v.z;
    const cos = Math.cos(angle),
      sin = Math.sin(angle);
    return {
      x: v.x * cos + crossProduct.x * sin + rotationAxis.x * dot * (1 - cos),
      y: v.y * cos + crossProduct.y * sin + rotationAxis.y * dot * (1 - cos),
      z: v.z * cos + crossProduct.z * sin + rotationAxis.z * dot * (1 - cos),
    };
  };
  return { ...c, eye: rotate(c.eye), up: rotate(up) };
}
