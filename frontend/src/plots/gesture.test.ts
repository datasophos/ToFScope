import { test, expect } from "vitest";
import { gestureBounds } from "./gesture";
test("moving a clipped window preserves its width", () =>
  expect(
    gestureBounds(
      { start: [2, 0], action: "move", selection: [1, 3] },
      [10, 0],
      "x",
      [0, 5],
      [0, 1],
    ),
  ).toEqual([3, 5]));
test("ROI resize can cross its opposite edge", () =>
  expect(
    gestureBounds(
      { start: [1, 0], action: "low", selection: [1, 3, 2, 4] },
      [4, 0],
      "xy",
      [0, 5],
      [0, 5],
    ),
  ).toEqual([3, 4, 2, 4]));

test("panning preserves zoom width and stops at data boundaries", async () => {
  const { panRange } = await import("./gesture");
  expect(panRange([2, 4], -1, [0, 10])).toEqual([1, 3]);
  expect(panRange([2, 4], -10, [0, 10])).toEqual([0, 2]);
  expect(panRange([2, 4], 10, [0, 10])).toEqual([8, 10]);
  expect(panRange([0, 10], 3, [0, 10])).toEqual([0, 10]);
});

test("depth bands draw, move and resize vertically with fixed full-width bounds", () => {
  expect(
    gestureBounds(
      { start: [3, 2], action: "draw" },
      [7, 6],
      "y",
      [0, 10],
      [0, 10],
    ),
  ).toEqual([0, 10, 2, 6]);
  expect(
    gestureBounds(
      { start: [3, 3], action: "move", selection: [0, 10, 2, 6] },
      [8, 9],
      "y",
      [0, 10],
      [0, 10],
    ),
  ).toEqual([0, 10, 6, 10]);
  expect(
    gestureBounds(
      { start: [3, 2], action: "bottom", selection: [0, 10, 2, 6] },
      [8, 4],
      "y",
      [0, 10],
      [0, 10],
    ),
  ).toEqual([0, 10, 4, 6]);
  expect(
    gestureBounds(
      { start: [3, 6], action: "top", selection: [0, 10, 2, 6] },
      [8, 8],
      "y",
      [0, 10],
      [0, 10],
    ),
  ).toEqual([0, 10, 2, 8]);
});
