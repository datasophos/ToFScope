import { describe, expect, it } from "vitest";
import type { ChartData } from "./selectedRenderer";
import { imagePixels } from "./imageRaster";

const image: ChartData = {
  kind: "image",
  x: [0, 1],
  y: [0, 1],
  xRange: [-0.5, 1.5],
  yRange: [-0.5, 1.5],
  values: [
    [0, 1],
    [null, 9],
  ],
  range: [0, 9],
  yReverse: true,
  palette: "gray",
};
describe("scientific image raster", () => {
  it("preserves zero, missing values, linear colors and the full image extent", () => {
    const { width, height, pixels } = imagePixels(image);
    expect([width, height]).toEqual([2, 2]);
    expect(Array.from(pixels)).toEqual([
      0, 0, 0, 255, 28, 28, 28, 255, 0, 0, 0, 0, 255, 255, 255, 255,
    ]);
    expect(image.values).toEqual([
      [0, 1],
      [null, 9],
    ]);
  });
  it("preserves the existing log1p color transform and gray palette", () => {
    const { pixels } = imagePixels({ ...image, log: true, palette: "gray" });
    expect(Array.from(pixels)).toEqual([
      0, 0, 0, 255, 77, 77, 77, 255, 0, 0, 0, 0, 255, 255, 255, 255,
    ]);
  });
  it("flips rows for an upward y axis and leaves nonfinite values transparent", () => {
    const { pixels } = imagePixels({
      ...image,
      yReverse: false,
      values: [
        [NaN, Infinity],
        [0, 9],
      ],
    });
    expect(Array.from(pixels)).toEqual([
      0, 0, 0, 255, 255, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0,
    ]);
  });
});

it("selectable palettes preserve scientific values and missing coverage", () => {
  const original = imagePixels(image).pixels;
  for (const palette of ["viridis", "magma", "cividis"] as const) {
    const { pixels } = imagePixels({ ...image, palette });
    expect(Array.from(pixels)).not.toEqual(Array.from(original));
    expect(pixels[11]).toBe(0);
    expect(image.values).toEqual([
      [0, 1],
      [null, 9],
    ]);
  }
});

it("uses canonical interior colors rather than interpolated approximations", () => {
  for (const [palette, rgb] of [
    ["viridis", [33, 145, 140]],
    ["magma", [183, 55, 121]],
    ["cividis", [125, 124, 120]],
  ] as const) {
    const { pixels } = imagePixels({
      ...image,
      palette,
      x: [0],
      y: [0],
      values: [[128]],
      range: [0, 255],
    });
    expect(Array.from(pixels)).toEqual([...rgb, 255]);
  }
});
