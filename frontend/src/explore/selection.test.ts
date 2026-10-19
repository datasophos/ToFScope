import { test, expect } from "vitest";
import { roiFromBounds, roiBounds, frameWindow } from "./selection";
test("ROI rounds original pixel centers and reverses axes", () => {
  expect(roiFromBounds([2, 6, 8, 4], [1301, 128, 128, 1], 20)).toEqual([
    13, 37, 26, 50,
  ]);
  expect(
    roiFromBounds(
      roiBounds([10, 20, 30, 40], [1301, 128, 128, 1], 20),
      [1301, 128, 128, 1],
      20,
    ),
  ).toEqual([10, 20, 30, 40]);
});
test("inclusive frame endpoints clamp to loaded domain", () => {
  expect(frameWindow([5.8, -1], [0, 5])).toEqual([0, 5]);
});

test("ROI tie rounding matches the Python reference", () =>
  expect(roiFromBounds([0.5, 0.5, 0, 0], [1, 1, 2, 1], null)).toEqual([
    0, 0, 0, 0,
  ]));
