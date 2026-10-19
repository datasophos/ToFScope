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
