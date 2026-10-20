import type { Page } from "@playwright/test";

export async function manageSignals(page: Page) {
  if (
    !(await page
      .getByRole("dialog", { name: "Manage signals", exact: true })
      .isVisible())
  )
    await page
      .getByRole("button", { name: "Manage signals", exact: true })
      .filter({ visible: true })
      .click();
}

export async function addSignal(page: Page) {
  await page
    .getByRole("button", { name: "Add signal", exact: true })
    .filter({ visible: true })
    .click();
}
