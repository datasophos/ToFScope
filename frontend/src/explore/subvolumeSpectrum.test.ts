import { expect, test } from "vitest";
import { subvolumePanel } from "./subvolumeSpectrum";
import type { Panel } from "../api/client";

test("spectrum panel preserves the native axis and labels the captured selection", () => {
  const base = {
    kind: "line",
    content_version: "old",
    axes: [],
    series: [],
  } as unknown as Panel;
  const panel = subvolumePanel(base, {
    job_id: "j",
    dataset_generation: "g",
    roi: [1, 2, 3, 4],
    frames: [5, 6],
    values: [0, 2],
  });
  expect(panel.axes).toBe(base.axes);
  expect(panel.series?.[0].values).toEqual([0, 2]);
  expect(panel.series?.[0].label).toContain("x 1–2, y 3–4, frames 5–6");
});
