import { expect, it } from "vitest";
import { moveWindow } from "./levels";

it("moves the window without changing its width, clamped to the histogram", () => {
  expect(moveWindow([2, 6], 10, [0, 10])).toEqual([6, 10]);
  expect(moveWindow([2, 6], -10, [0, 10])).toEqual([0, 4]);
});
