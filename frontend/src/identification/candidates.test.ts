import { expect, test } from "vitest";
import { orderCandidates, formatAbundance, type Candidate } from "./candidates";
const candidate = (
  symbol: string,
  abundance: number | null,
  error: number,
): Candidate => ({
  charge: 1,
  predicted_mz: 48 - error,
  error_Th: error,
  error_ppm: (error / 48) * 1e6,
  isotope: {
    symbol,
    mass_number: 48,
    neutral_mass_u: 48,
    source_id: "fixture",
    mass_estimated: false,
    abundance_low: abundance,
    abundance_high: abundance,
  },
});
const rows = [
  candidate("K", null, -0.00554502),
  candidate("Ca", 0.00187, 0.00727341),
  candidate("Ti", 0.7372, 0.01185419),
];
test("natural-abundance ordering puts Ti ahead of rare Ca and omits unlisted abundances by default", () => {
  expect(
    orderCandidates(rows, "abundance", false).map((r) => r.isotope.symbol),
  ).toEqual(["Ti", "Ca"]);
  expect(rows.map((r) => r.isotope.symbol)).toEqual(["K", "Ca", "Ti"]);
});
test("unlisted isotope masses remain available and closest-mass ordering is explicit", () => {
  expect(
    orderCandidates(rows, "abundance", true).map((r) => r.isotope.symbol),
  ).toEqual(["Ti", "Ca", "K"]);
  expect(
    orderCandidates(rows, "mass", true).map((r) => r.isotope.symbol),
  ).toEqual(["K", "Ca", "Ti"]);
  expect(
    orderCandidates(rows, "mass", false).map((r) => r.isotope.symbol),
  ).toEqual(["Ca", "Ti"]);
});
test("natural abundance is formatted as percentages, preserving intervals and trace abundances", () => {
  expect(formatAbundance(rows[2].isotope)).toBe("73.72%");
  expect(formatAbundance(rows[1].isotope)).toBe("0.187%");
  expect(formatAbundance(rows[0].isotope)).toBe("Not tabulated");
  expect(
    formatAbundance({ abundance_low: 0.9884, abundance_high: 0.9904 }),
  ).toBe("98.84–99.04%");
  expect(
    formatAbundance({ abundance_low: 0.00001, abundance_high: 0.00028 }),
  ).toBe("0.001–0.028%");
});
