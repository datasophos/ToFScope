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
  await expect(panel.getByText(/Acquisition-wide spectrum/)).toBeVisible();
  await panel.getByRole("button", { name: "Calculate ROI spectrum" }).click();
  await expect(
    panel.getByText(/Selected spectrum · x 0–1, y 0–0, frames 0–2/),
  ).toBeVisible();
  await panel
    .getByRole("button", { name: "Show acquisition spectrum" })
    .click();
  await expect(panel.getByText(/Acquisition-wide spectrum/)).toBeVisible();
  await panel.getByRole("button", { name: "Show ROI spectrum" }).click();
  await expect(
    panel.getByText(/Selected spectrum · x 0–1, y 0–0, frames 0–2/),
  ).toBeVisible();
});
