import { manageSignals } from "./signal-controls";
import { test, expect } from "@playwright/test";

test("all draft intervals remain visible and compact bounds preserve exact values", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `interval-ui-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  const spectrum = page.getByTestId("panel-spectrum");
  await spectrum
    .getByRole("button", { name: "Create signal", exact: true })
    .click();
  const name = page.getByLabel("Signal name", { exact: true });
  await name.fill("Two windows");
  await page.getByLabel("Mass lower 1", { exact: true }).fill("1.123456789");
  await page.getByLabel("Mass upper 1", { exact: true }).fill("2.234567891");
  await page.getByRole("button", { name: "Add interval", exact: true }).click();
  await page.getByLabel("Mass lower 2", { exact: true }).fill("3.345678912");
  await page.getByLabel("Mass upper 2", { exact: true }).fill("4.456789123");
  await name.focus();
  await expect(page.getByLabel("Mass lower 1", { exact: true })).toHaveValue(
    "1.12",
  );
  await expect(page.getByLabel("Mass upper 2", { exact: true })).toHaveValue(
    "4.46",
  );
  await expect(spectrum.locator("[data-draft-window]")).toHaveCount(2);
  await spectrum
    .getByRole("button", { name: "Select spectrum interval 1", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Edit interval 1", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  const lower = page.getByLabel("Mass lower 1", { exact: true });
  await lower.focus();
  await expect(lower).toHaveValue("1.123456789");
  await name.focus();
  await expect(lower).toHaveValue("1.12");
  await page.locator(".spectrum-workbench").screenshot({
    path: test.info().outputPath("signal-editor-intervals.png"),
  });
  await page
    .getByRole("button", { name: "Calculate signal", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Signal editor", exact: true }),
  ).toBeHidden();
  const state = await page.evaluate(
    async () => (await (await fetch("/api/v1/analyses")).json())[0],
  );
  const signal = state.signals.find(
    (s: { name: string }) => s.name === "Two windows",
  );
  expect(signal.recipe.intervals).toEqual([
    [1.123456789, 2.234567891],
    [3.345678912, 4.456789123],
  ]);
  await manageSignals(page);
  await page
    .getByTestId("signal-row")
    .filter({ hasText: "Two windows" })
    .getByRole("button", { name: "Details", exact: true })
    .click();
  const details = page.getByRole("dialog", {
    name: "Signal details: Two windows",
    exact: true,
  });
  await expect(details).toContainText("1.12–2.23 Th ∪ 3.35–4.46 Th");
  await expect(details.locator("[data-mass-intervals]")).toHaveAttribute(
    "title",
    "1.123456789–2.234567891 Th ∪ 3.345678912–4.456789123 Th",
  );
});
