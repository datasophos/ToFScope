/** Readable presentation only; callers retain exact values for commands and exports. */
export function formatNumber(
  value: number | null | undefined,
  decimals = 4,
): string {
  if (value == null || !Number.isFinite(value)) return "Unavailable";
  const magnitude = Math.abs(value);
  if (magnitude > 0 && (magnitude < 10 ** -decimals || magnitude >= 1e7)) {
    const [coefficient, exponent] = value.toExponential(3).split("e");
    return `${Number(coefficient)}e${Number(exponent)}`;
  }
  return String(Number(value.toFixed(decimals)));
}
