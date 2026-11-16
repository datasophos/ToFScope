import { expect, test } from "@playwright/test";

test("calculate a selected spectrum and return to the acquisition spectrum", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `roi-spectrum-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  const panel = page.getByTestId("panel-spectrum");
  await expect(
    panel.getByRole("button", { name: "Total sum", exact: true }),
  ).toBeVisible();
  await page.route("**/api/v1/jobs/*", async (route) => {
    const response = await route.fetch();
    await new Promise((resolve) => setTimeout(resolve, 500));
    await route.fulfill({ response });
  });
  await panel.getByRole("button", { name: "Calculate ROI" }).click();
  await expect(
    panel.getByRole("progressbar", {
      name: "ROI spectrum calculation progress",
    }),
  ).toBeVisible();
  await expect(
    panel.getByText(/Selected spectrum · x 0–1, y 0–0, frames 0–2/),
  ).toBeVisible();
  const calculate = panel.getByRole("button", {
    name: /^(Calculate|Update) ROI$/,
  });
  await expect(calculate).toBeDisabled();
  await expect(calculate).toHaveAttribute(
    "title",
    "This ROI spectrum has already been calculated.",
  );
  await page.getByRole("button", { name: /ROI: Full field/ }).click();
  await page.getByLabel("ROI x first").fill("1");
  await page.getByRole("button", { name: "Apply ROI" }).click();
  await expect(calculate.locator(".spectrum-outdated")).toBeVisible();
  await expect(calculate).toHaveAttribute("title", /Spectrum out of date/);
  await expect(calculate).toBeEnabled();
  await page.getByRole("button", { name: /ROI: x 1/ }).click();
  await page.getByRole("button", { name: "Full field", exact: true }).click();
  await expect(calculate.locator(".spectrum-outdated")).toHaveCount(0);
  await expect(calculate).toBeDisabled();
  await panel.getByRole("button", { name: "Total sum", exact: true }).click();
  await expect(
    panel.getByRole("button", { name: "Total sum", exact: true }),
  ).toBeVisible();
  await expect(calculate).toBeDisabled();
  await panel.getByRole("button", { name: "ROI", exact: true }).click();
  await expect(
    panel.getByText(/Selected spectrum · x 0–1, y 0–0, frames 0–2/),
  ).toBeVisible();
  await expect(panel.getByRole("button", { name: "Identify peak", exact: true })).not.toBeVisible();
  await panel.locator("summary").filter({ hasText: "Analyze" }).click();
  await panel.getByRole("button", { name: "Identify peak", exact: true }).click();
  await expect(page.getByText("Atomic identification", { exact: true })).toBeVisible();
  await expect(panel.locator("details")).not.toHaveAttribute("open");
});
