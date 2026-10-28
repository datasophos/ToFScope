const captures = new WeakMap<Element, () => Promise<string>>();
export function registerVolumeCapture(
  element: Element,
  capture: () => Promise<string>,
) {
  captures.set(element, capture);
  return () => captures.delete(element);
}
export async function exportVolume(viewer: HTMLElement): Promise<string> {
  const scenes = viewer.matches(".vtk-volume-view")
    ? [viewer]
    : [...viewer.querySelectorAll<HTMLElement>(".vtk-volume-view")];
  if (!scenes.length) throw new Error("No 3D view is available to export.");
  const images = await Promise.all(
    scenes.map(async (scene) => {
      const capture = captures.get(scene);
      if (!capture) throw new Error("The 3D view is not ready to export.");
      const image = new Image();
      image.src = await capture();
      await image.decode();
      return image;
    }),
  );
  const bounds = viewer.getBoundingClientRect(),
    scale = window.devicePixelRatio || 1;
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bounds.width * scale);
  canvas.height = Math.round(bounds.height * scale);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("PNG export is unavailable.");
  ctx.scale(scale, scale);
  ctx.fillStyle = "#101f2e";
  ctx.fillRect(0, 0, bounds.width, bounds.height);
  const relative = (el: Element) => {
    const rect = el.getBoundingClientRect();
    return {
      x: rect.left - bounds.left,
      y: rect.top - bounds.top,
      width: rect.width,
      height: rect.height,
    };
  };
  scenes.forEach((scene, i) => {
    const viewport = scene.querySelector(".vtk-volume-viewport")!;
    const rect = relative(viewport);
    ctx.drawImage(images[i], rect.x, rect.y, rect.width, rect.height);
  });
  ctx.fillStyle = "#c2d1dc";
  ctx.font = "11px sans-serif";
  ctx.textBaseline = "top";
  viewer
    .querySelectorAll<HTMLElement>(
      ".vtk-tile-title, .vtk-volume-legend > div:first-child, .vtk-volume-ticks > span",
    )
    .forEach((el) => {
      const rect = relative(el);
      ctx.fillText(el.textContent ?? "", rect.x, rect.y, rect.width);
    });
  viewer.querySelectorAll<HTMLElement>(".vtk-volume-ramp").forEach((el) => {
    const rect = relative(el),
      gradient = ctx.createLinearGradient(0, rect.y + rect.height, 0, rect.y);
    const stops = JSON.parse(el.dataset.stops || "[]") as [
      number,
      number,
      number,
      number,
    ][];
    stops.forEach(([fraction, r, g, b]) =>
      gradient.addColorStop(fraction, `rgb(${r},${g},${b})`),
    );
    ctx.fillStyle = gradient;
    ctx.fillRect(rect.x, rect.y, rect.width, rect.height);
  });
  return canvas.toDataURL("image/png");
}
