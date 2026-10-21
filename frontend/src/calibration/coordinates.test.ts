import { expect, test } from "vitest";
import { frameToCoordinate, coordinateToFrame, rowSpans } from "./coordinates";
const axis = { values: [0, 20, 40, 60], boundaries: [-10, 10, 30, 50, 70] };
test("coordinate mapping returns original frames and rejects unknown depths", () => {
  expect(coordinateToFrame(30, axis, [0, 2, 3, 4])).toBe(2.5);
  expect(frameToCoordinate(3, axis, [0, 2, 3, 4])).toBe(40);
  expect(frameToCoordinate(5, axis, [0, 2, 3, 4])).toBeUndefined();
});
test("nonuniform rows retain supplied boundaries and single rows stay visible", () => {
  expect(rowSpans([0, 10, 40])).toEqual([
    [-5, 5],
    [5, 25],
    [25, 55],
  ]);
  expect(rowSpans([100])).toEqual([[99.5, 100.5]]);
  expect(rowSpans([])).toEqual([]);
});

test("anchor validation explains rejected input before submission", async () => {
  const { anchorError } = await import("./coordinates");
  expect(
    anchorError(
      [
        { frame: 0, depth_nm: 0 },
        { frame: 1, depth_nm: 100 },
        { frame: 2, depth_nm: 50 },
      ],
      3,
    ),
  ).toContain("increase");
  expect(anchorError([{ frame: 0, depth_nm: 4 }], 3)).toContain("fixed");
  expect(anchorError([{ frame: 3, depth_nm: 100 }], 3)).toContain(
    "acquisition",
  );
  expect(anchorError([{ frame: 1, depth_nm: 100 }], 3)).toBe("");
});
