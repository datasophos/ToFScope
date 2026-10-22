import { expect, test } from "vitest";
import { formatNumber } from "./numbers";
test("readable values suppress floating-point tails and redundant zeroes", () => {
  expect(formatNumber(13.387507820129395)).toBe("13.3875");
  expect(formatNumber(13.587507820129394)).toBe("13.5875");
  expect(formatNumber(0.1 + 0.2)).toBe("0.3");
  expect(formatNumber(75)).toBe("75");
  expect(formatNumber(-0)).toBe("0");
  expect(formatNumber(1.123456789, 2)).toBe("1.12");
});
test("small nonzero scientific values stay nonzero and large values stay compact", () => {
  expect(formatNumber(0.000000013376)).toBe("1.338e-8");
  expect(formatNumber(-0.000000013376)).toBe("-1.338e-8");
  expect(formatNumber(123456789)).toBe("1.235e8");
  expect(formatNumber(null)).toBe("Unavailable");
  expect(formatNumber(NaN)).toBe("Unavailable");
});
