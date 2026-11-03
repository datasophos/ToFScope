export function seIntensityRange(
  range: [number, number],
  brightness: number,
  contrast: number,
): [number, number] {
  const width = Math.max(range[1] - range[0], 1e-9);
  const safeWidth = range[1] > range[0] ? width : 1;
  const center = range[0] + safeWidth / 2 - brightness * safeWidth;
  return [
    center - safeWidth / (2 * contrast),
    center + safeWidth / (2 * contrast),
  ];
}
