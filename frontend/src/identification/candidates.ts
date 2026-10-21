import type { components } from "../api/generated";
export type Candidate = components["schemas"]["IonCandidate"];
export type CandidateOrder = "abundance" | "mass";
const referenceFraction = (candidate: Candidate) => {
  const { abundance_low: low, abundance_high: high } = candidate.isotope;
  return low == null || high == null ? null : (low + high) / 2;
};
/** Presentation order within the API's exact mass tolerance, never an identity probability. */
export function orderCandidates(
  candidates: Candidate[],
  order: CandidateOrder,
  includeUnlisted: boolean,
): Candidate[] {
  return candidates
    .filter((c) => includeUnlisted || (referenceFraction(c) ?? 0) > 0)
    .sort((a, b) => {
      if (order === "abundance") {
        const difference =
          (referenceFraction(b) ?? -1) - (referenceFraction(a) ?? -1);
        if (difference) return difference;
      }
      return (
        Math.abs(a.error_Th) - Math.abs(b.error_Th) ||
        a.isotope.symbol.localeCompare(b.isotope.symbol) ||
        a.isotope.mass_number - b.isotope.mass_number ||
        a.charge - b.charge
      );
    });
}
export function formatAbundance(isotope: {
  abundance_low: number | null;
  abundance_high: number | null;
}): string {
  const { abundance_low: low, abundance_high: high } = isotope;
  if (low == null || high == null) return "Not tabulated";
  const format = (value: number) =>
    new Intl.NumberFormat("en-US", { maximumSignificantDigits: 5 }).format(
      value * 100,
    );
  return low === high ? `${format(low)}%` : `${format(low)}–${format(high)}%`;
}
