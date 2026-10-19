const roundEven = (x: number) => {
  const floor = Math.floor(x);
  return x - floor === 0.5 ? floor + (floor % 2 === 0 ? 0 : 1) : Math.round(x);
};
export type ROI = [number, number, number, number];
export function roiFromBounds(
  bounds: number[],
  shape: number[],
  fov?: number | null,
): ROI {
  const result: number[] = [];
  for (const [a, b, n] of [
    [bounds[0], bounds[1], shape[2]],
    [bounds[2], bounds[3], shape[1]],
  ]) {
    const low = Math.min(a, b),
      high = Math.max(a, b),
      s = fov ? fov / n : 1,
      offset = fov ? 0.5 : 0,
      clamp = (v: number) => Math.max(0, Math.min(n - 1, v));
    let first = clamp(Math.ceil(low / s - offset - 1e-9)),
      last = clamp(Math.floor(high / s - offset + 1e-9));
    if (first > last)
      first = last = clamp(roundEven((low + high) / 2 / s - offset));
    result.push(first, last);
  }
  return result as ROI;
}
export function roiBounds(roi: ROI, shape: number[], fov?: number | null): ROI {
  const [x0, x1, y0, y1] = roi;
  return fov
    ? [
        (x0 * fov) / shape[2],
        ((x1 + 1) * fov) / shape[2],
        (y0 * fov) / shape[1],
        ((y1 + 1) * fov) / shape[1],
      ]
    : [x0 - 0.5, x1 + 0.5, y0 - 0.5, y1 + 0.5];
}
export function frameWindow(
  bounds: number[],
  frames: [number, number],
): [number, number] {
  return [
    Math.max(frames[0], Math.min(frames[1], Math.round(Math.min(...bounds)))),
    Math.max(frames[0], Math.min(frames[1], Math.round(Math.max(...bounds)))),
  ];
}
