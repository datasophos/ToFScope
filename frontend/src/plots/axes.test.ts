import { expect, test } from "vitest";
import { axisTitle, formatTick, plotInsets } from "./axes";
test("scientific axes identify frame, depth and spatial units", () => {
  expect(axisTitle({ name: "frame", unit: "frame" })).toBe("Frame");
  expect(axisTitle({ name: "depth", unit: "µm" })).toBe("Depth (µm)");
  expect(axisTitle({ name: "x", unit: "native pixel" })).toBe(
    "X (native pixel)",
  );
  expect(axisTitle({ name: "m/z", unit: "Th" })).toBe("m/z");
});
test("tick formatting stays compact without changing the value domain", () => {
  expect(formatTick(216.725151)).toBe("216.73");
  expect(formatTick(10000000)).toBe("1e7");
  expect(formatTick(0.000001)).toBe("1e-6");
  expect(formatTick(0)).toBe("0");
});
test("image plot insets keep a square data viewport", () => {
  const p = plotInsets("image");
  expect(p.left + p.right).toBe(p.top + p.bottom);
});

test("frame labels and hover positions are integer acquisition frames", async () => {
  const { formatFrameTick, formatPosition } = await import("./axes");
  expect(formatFrameTick(0.5)).toBe("");
  expect(formatFrameTick(2)).toBe("2");
  expect(formatPosition(1.7, { unit: "frame", values: [0, 1, 2] })).toBe("2");
  expect(formatPosition(2.5, { unit: "frame", values: [0, 1, 2] })).toBe("2");
  expect(formatPosition(-0.5, { unit: "frame", values: [0, 1, 2] })).toBe("0");
  expect(formatPosition(0.125, { unit: "nm", values: [0, 1] })).toBe("0.125");
});
