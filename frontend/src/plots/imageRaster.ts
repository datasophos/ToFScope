import { colormaps } from "./colormaps";
import type { ChartData } from "./selectedRenderer";

// Only display colors are rasterized. The original values and axes stay intact.
export function imagePixels(d: ChartData) {
  const width = d.x.length,
    height = d.y!.length;
  const pixels = new Uint8ClampedArray(width * height * 4);
  const transform = (value: number) =>
    d.log ? Math.log1p(Math.max(0, value)) : value;
  const [min, max] = d.range || [0, 1];
  const lookup =
    d.palette === "magma" || d.palette === "cividis"
      ? colormaps[d.palette]
      : colormaps.viridis;
  const low = transform(min),
    span = transform(max) - low || 1;
  for (let row = 0; row < height; row++) {
    const targetRow = d.yReverse ? row : height - row - 1;
    for (let column = 0; column < width; column++) {
      const value = d.values![row][column];
      if (value === null || !Number.isFinite(value)) continue;
      const t = Math.max(0, Math.min(1, (transform(value) - low) / span));
      const offset = (targetRow * width + column) * 4;
      if (d.palette === "gray") {
        pixels[offset] =
          pixels[offset + 1] =
          pixels[offset + 2] =
            Math.round(255 * t);
      } else {
        const color = Math.round(t * 255) * 3;
        pixels[offset] = lookup[color];
        pixels[offset + 1] = lookup[color + 1];
        pixels[offset + 2] = lookup[color + 2];
      }
      pixels[offset + 3] = 255;
    }
  }
  return { width, height, pixels };
}

export function imageRaster(d: ChartData) {
  const { width, height, pixels } = imagePixels(d);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d")!;
  const image = context.createImageData(width, height);
  image.data.set(pixels);
  context.putImageData(image, 0, 0);
  return canvas;
}
