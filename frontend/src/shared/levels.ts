export function moveWindow(
  window: [number, number],
  delta: number,
  domain: [number, number],
): [number, number] {
  const shift = Math.max(
    domain[0] - window[0],
    Math.min(domain[1] - window[1], delta),
  );
  return [window[0] + shift, window[1] + shift];
}

export function layerRange(values: (number | null)[]) {
  let min = Infinity,
    max = -Infinity;
  for (const value of values)
    if (value !== null && Number.isFinite(value)) {
      min = Math.min(min, value);
      max = Math.max(max, value);
    }
  return min === Infinity ? [0, 0] : [min, max];
}

export function histogram(
  values: (number | null)[],
  min: number,
  max: number,
  bins = 64,
) {
  const counts = Array<number>(bins).fill(0);
  if (!(max > min)) return counts;
  for (const value of values) {
    if (value === null || !Number.isFinite(value)) continue;
    const i = Math.max(
      0,
      Math.min(bins - 1, Math.floor(((value - min) / (max - min)) * bins)),
    );
    counts[i]++;
  }
  return counts;
}
