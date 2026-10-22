import { test, expect } from "@playwright/test";

for (const zero of [true, false]) {
  test(`measurement explains ${zero ? "zero intensity" : "a single signal's share"} without an isotope assignment`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 1000 });
    await page.setExtraHTTPHeaders({
      "x-tofscope-user": `measure-explain-${zero}-${Date.now()}`,
    });
    await page.goto("/");
    await page
      .getByRole("button", { name: /Open TOFexplorer/ })
      .first()
      .click();
    await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
    await page
      .getByTestId("panel-spectrum")
      .getByRole("button", { name: "Create signal", exact: true })
      .click();
    await page.getByLabel("Signal name", { exact: true }).fill("Test window");
    await page
      .getByLabel("Mass lower 1", { exact: true })
      .fill(zero ? "0" : "1");
    await page
      .getByLabel("Mass upper 1", { exact: true })
      .fill(zero ? "0.5" : "2");
    await page
      .getByRole("button", { name: "Calculate signal", exact: true })
      .click();
    await expect(
      page.getByRole("region", { name: "Signal editor", exact: true }),
    ).toBeHidden();
    await page
      .getByRole("button", { name: "Isotope measurements", exact: true })
      .click();
    const dialog = page.getByRole("dialog", {
      name: "Isotope measurements",
      exact: true,
    });
    await dialog
      .getByRole("checkbox", { name: "Test window", exact: true })
      .check();
    await dialog.getByRole("button", { name: "Measure", exact: true }).click();
    const results = dialog.getByTestId("isotope-results");
    await expect(results).toContainText("Region: 2 × 1 pixels");
    await expect(results).toContainText("Columns 0–1; rows 0–0");
    await expect(results).toContainText("Only one signal was measured");
    const row = results.locator("tbody tr").first();
    await expect(row).toContainText("No isotope assigned");
    await expect(row).toContainText(
      "Assign an isotope to see its reference abundance",
    );
    if (zero) {
      await expect(row).toContainText(
        "No signal detected in this region/frame range",
      );
      await expect(row).toContainText("Unavailable — total intensity is zero");
    } else {
      await expect(row.locator("td").nth(2)).toHaveText("100%");
    }
    await dialog.screenshot({
      path: test.info().outputPath("measurement-desktop.png"),
    });
    await expect(dialog.locator(".measurement-help")).not.toHaveAttribute(
      "open",
    );
    await dialog
      .getByText("How these measurements work", { exact: true })
      .click();
    await expect(dialog.locator(".measurement-help")).toContainText(
      "Use Identify peak",
    );
    await page.setViewportSize({ width: 560, height: 800 });
    await expect
      .poll(() => dialog.evaluate((el) => el.scrollWidth <= el.clientWidth))
      .toBe(true);
    await dialog.screenshot({
      path: test.info().outputPath("measurement-mobile.png"),
    });
  });
}
