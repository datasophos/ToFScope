import { it, expect } from "vitest";
import {
  volumeDisplayStats,
  levelStats,
  defaultLayer,
  histogram,
} from "./spatialRenderer";

it("maps persisted intensity levels into log display coordinates", () => {
  const style = { ...defaultLayer("x"), levels: [1, 9] as [number, number] };
  const result = levelStats([0, 1, 9], style, true);
  expect(result.lower).toBeCloseTo(Math.log(2));
  expect(result.upper).toBeCloseTo(Math.log(10));
});

it("histogram excludes missing values and places covered values in bins", () => {
  expect(histogram([0, null, 1, 2], 0, 2, 2)).toEqual([1, 2]);
});

it("matches prototype nonzero percentile thresholds and robust display limits", () => {
  const values = [...Array(1000).fill(0), 1, 2, 3, 1000];
  expect(volumeDisplayStats(values, 10, false).threshold).toBeCloseTo(1.3);
  const outlier = volumeDisplayStats(
    [...Array.from({ length: 1000 }, (_, i) => i + 1), 1e9],
    70,
    false,
  );
  expect(outlier.upper).toBeCloseTo(998);
  const log = volumeDisplayStats([0, 1, 3], 50, true);
  expect(log.lower).toBeCloseTo((Math.log(2) + Math.log(4)) / 2);
  expect(log.threshold).toBeCloseTo(Math.sqrt(8) - 1);
});
