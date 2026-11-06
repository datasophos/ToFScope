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
