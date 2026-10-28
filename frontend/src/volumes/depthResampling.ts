/** Experimental linear interpolation onto uniform physical-depth coordinates.
 * Original preview values remain untouched; missing input is rejected. */
export function resampleDepth(
  z: number[],
  values: (number | null)[],
  plane: number,
  count: number,
) {
  if (
    z.length < 2 ||
    z.some((v, i) => !Number.isFinite(v) || (i > 0 && v <= z[i - 1]))
  )
    throw new Error(
      "Depth coordinates must be finite and strictly increasing.",
    );
  if (
    !Number.isInteger(plane) ||
    plane < 1 ||
    values.length !== plane * z.length ||
    !Number.isInteger(count) ||
    count < 2
  )
    throw new Error("Invalid volume dimensions.");
  if (values.some((v) => v === null || !Number.isFinite(v)))
    throw new Error("Missing or non-finite samples are not supported.");
  const first = z[0],
    last = z[z.length - 1];
  const outZ = Array.from(
    { length: count },
    (_, i) => first + ((last - first) * i) / (count - 1),
  );
  const out: number[] = [];
  let lo = 0;
  for (const depth of outZ) {
    while (lo < z.length - 2 && depth > z[lo + 1]) lo++;
    const alpha = (depth - z[lo]) / (z[lo + 1] - z[lo]);
    for (let p = 0; p < plane; p++) {
      const a = values[lo * plane + p]!,
        b = values[(lo + 1) * plane + p]!;
      out.push(a + (b - a) * alpha);
    }
  }
  return { z: outZ, values: out };
}
