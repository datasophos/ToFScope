/** Display coordinates map to original samples; never interpolate intensities. */
type Axis = { values: number[]; boundaries: number[] };
function interpolate(value: number, from: number[], to: number[]) {
  if (!from.length || value < from[0] || value > from.at(-1)!) return undefined;
  if (from.length === 1) return to[0];
  for (let i = 1; i < from.length; i++)
    if (value <= from[i])
      return (
        to[i - 1] +
        ((value - from[i - 1]) * (to[i] - to[i - 1])) / (from[i] - from[i - 1])
      );
  return undefined;
}
export function frameToCoordinate(frame: number, axis: Axis, frames: number[]) {
  return interpolate(frame, frames, axis.values);
}
export function coordinateToFrame(value: number, axis: Axis, frames: number[]) {
  if (!axis.values.length) return undefined;
  // Gestures can land in the half-cell display footprint around endpoint samples.
  return interpolate(
    Math.max(axis.values[0], Math.min(axis.values.at(-1)!, value)),
    axis.values,
    frames,
  );
}
export function rowSpans(values: number[]): [number, number][] {
  return values.map((v, i) => [
    i
      ? (values[i - 1] + v) / 2
      : v - (values.length > 1 ? values[1] - v : 1) / 2,
    i + 1 < values.length
      ? (values[i + 1] + v) / 2
      : v + (values.length > 1 ? v - values[i - 1] : 1) / 2,
  ]);
}

export function anchorError(
  anchors: { frame: number; depth_nm: number }[],
  count: number,
) {
  const rows = anchors.some((x) => x.frame === 0)
    ? anchors.slice()
    : [{ frame: 0, depth_nm: 0 }, ...anchors];
  rows.sort((a, b) => a.frame - b.frame);
  for (let i = 0; i < rows.length; i++) {
    const a = rows[i];
    if (!Number.isInteger(a.frame) || a.frame < 0 || a.frame >= count)
      return "Choose an integer acquisition frame within the file.";
    if (!Number.isFinite(a.depth_nm)) return "Known depths must be finite.";
    if (a.frame === 0 && a.depth_nm !== 0)
      return "Frame 0 is fixed at depth 0.";
    if (
      i &&
      (a.frame === rows[i - 1].frame || a.depth_nm <= rows[i - 1].depth_nm)
    )
      return "Depth must increase with acquisition frame; anchor frames must be unique.";
  }
  return "";
}
