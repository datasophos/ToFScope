import { expect, test } from "vitest";
import { subvolumePanel, spectrumIsOutOfDate } from "./subvolumeSpectrum";
import type { Analysis, Panel } from "../api/client";

const result = {
  job_id: "j",
  dataset_generation: "g",
  roi: [1, 2, 3, 4] as [number, number, number, number],
  frames: [0, 6] as [number, number],
  values: [0, 2],
};

test("detects ROI and frame changes against the calculated selection", () => {
  const analysis = {
    roi: [1, 2, 3, 4],
    shape: [7, 5, 5, 1],
    depth: { mode: "all" },
  } as Analysis;
  expect(spectrumIsOutOfDate(result, analysis)).toBe(false);
  expect(spectrumIsOutOfDate(result, { ...analysis, roi: [1, 3, 3, 4] })).toBe(
    true,
  );
  expect(
    spectrumIsOutOfDate(result, {
      ...analysis,
      depth: { mode: "frame", index: 3 },
    }),
  ).toBe(true);
  expect(
    spectrumIsOutOfDate(result, {
      ...analysis,
      depth: { mode: "window", first: 0, last: 6 },
    }),
  ).toBe(false);
  expect(
    spectrumIsOutOfDate(result, {
      ...analysis,
      depth: { mode: "window", first: 1, last: 6 },
    }),
  ).toBe(true);
});

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
