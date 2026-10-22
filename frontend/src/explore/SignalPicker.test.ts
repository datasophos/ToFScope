import { expect, test } from "vitest";
import { matchesSignalOption } from "./SignalPicker";
test("stored signals can be found by the visible rounded mass and by exact mass", () => {
  const option = { index: 0, label: "Titanium", mass: 13.38756 };
  expect(matchesSignalOption(option, "13.3876")).toBe(true);
  expect(matchesSignalOption(option, "13.38756")).toBe(true);
  expect(matchesSignalOption(option, " TITAN ")).toBe(true);
  expect(matchesSignalOption(option, "missing")).toBe(false);
});
test("scientific display values remain searchable without losing raw numeric search", () => {
  const option = { index: 0, label: "Trace", mass: 1.3376e-8 };
  expect(matchesSignalOption(option, "1.338e-8")).toBe(true);
  expect(matchesSignalOption(option, "1.3376e-8")).toBe(true);
});
