import { it, expect } from "vitest";
import { volumeDisplayStats } from "./spatialRenderer";

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
