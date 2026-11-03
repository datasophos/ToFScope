export function startRotation(
  rotate: (degrees: number) => void,
  request: (callback: FrameRequestCallback) => number = requestAnimationFrame,
  cancel: (id: number) => void = cancelAnimationFrame,
): () => void {
  let previous: number | undefined;
  let id: number;
  let stopped = false;
  const frame: FrameRequestCallback = (now) => {
    if (stopped) return;
    if (previous !== undefined)
      rotate(Math.min(Math.max(now - previous, 0), 100) * 0.03);
    previous = now;
    id = request(frame);
  };
  id = request(frame);
  return () => {
    stopped = true;
    cancel(id);
  };
}
