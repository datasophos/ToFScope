import { expect, test } from "vitest";
import { seIntensityRange } from "./seDisplay";

test("SE brightness and contrast adjust and reset the display window", () => {
  expect(seIntensityRange([10, 110], 0, 1)).toEqual([10, 110]);
  expect(seIntensityRange([10, 110], 0.2, 1)).toEqual([-10, 90]);
  expect(seIntensityRange([10, 110], 0, 2)).toEqual([35, 85]);
  expect(seIntensityRange([5, 5], 0, 1)).toEqual([5, 6]);
});
