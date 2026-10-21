/** Snap in the current displayed X geometry; exact input remains available. */
export function snapPeak(
  mz: number,
  unitsPerPixel: number,
  masses: number[],
  values: (number | null)[],
): number {
  let selected = mz,
    distance = Infinity;
  for (let i = 1; i < masses.length - 1; i++) {
    const v = values[i],
      left = values[i - 1],
      right = values[i + 1];
    if (v == null || left == null || right == null || !Number.isFinite(v))
      continue;
    const d = Math.abs(masses[i] - mz);
    if (v > left && v >= right && d <= 7 * unitsPerPixel && d < distance) {
      selected = masses[i];
      distance = d;
    }
  }
  return selected;
}
