import { expect, test } from "vitest";
import { snapPeak } from "./snapPeak";
test("snap to nearest local maximum within seven display pixels", () => {
  expect(snapPeak(2.6, 0.1, [1, 2, 3, 4, 5], [0, 1, 9, 1, 0])).toBe(3);
  expect(snapPeak(2.2, 0.1, [1, 2, 3, 4, 5], [0, 1, 9, 1, 0])).toBe(2.2);
  expect(snapPeak(2.6, 0.1, [1, 2, 3, 4, 5], [0, 1, null, 1, 0])).toBe(2.6);
  expect(snapPeak(2.6, 0.1, [], [])).toBe(2.6);
});
