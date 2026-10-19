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
};
describe("scientific image raster", () => {
  it("preserves zero, missing values, linear colors and the full image extent", () => {
    const { width, height, pixels } = imagePixels(image);
    expect([width, height]).toEqual([2, 2]);
    expect(Array.from(pixels)).toEqual([
      25, 30, 90, 255, 49, 51, 84, 255, 0, 0, 0, 0, 245, 220, 40, 255,
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
      25, 30, 90, 255, 245, 220, 40, 255, 0, 0, 0, 0, 0, 0, 0, 0,
    ]);
  });
});
