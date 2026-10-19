export type Drag = { start: number[]; action: string; selection?: number[] };
export function gestureBounds(
  d: Drag,
  end: number[],
  mode: "x" | "xy",
  xRange: [number, number],
  yRange: [number, number],
): number[] {
  let b =
    mode === "xy"
      ? [
          Math.min(d.start[0], end[0]),
          Math.max(d.start[0], end[0]),
          Math.min(d.start[1], end[1]),
          Math.max(d.start[1], end[1]),
        ]
      : [Math.min(d.start[0], end[0]), Math.max(d.start[0], end[0])];
  if (d.selection && d.action !== "draw") {
    b = d.selection.slice();
    if (d.action === "move") {
      const dx = Math.max(
        xRange[0] - b[0],
        Math.min(xRange[1] - b[1], end[0] - d.start[0]),
      );
      b[0] += dx;
      b[1] += dx;
      if (mode === "xy") {
        const dy = Math.max(
          yRange[0] - b[2],
          Math.min(yRange[1] - b[3], end[1] - d.start[1]),
        );
        b[2] += dy;
        b[3] += dy;
      }
    } else if (d.action === "low") b[0] = end[0];
    else if (d.action === "high") b[1] = end[0];
    else if (d.action === "bottom") b[2] = end[1];
    else if (d.action === "top") b[3] = end[1];
  }
  return [
    Math.min(b[0], b[1]),
    Math.max(b[0], b[1]),
    ...(mode === "xy" ? [Math.min(b[2], b[3]), Math.max(b[2], b[3])] : []),
  ];
}
