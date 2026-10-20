import { manageSignals, addSignal } from "./signal-controls";
import { test, expect } from "@playwright/test";
test("signal collection scrolls without losing labels and contextual controls fit narrow screens", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `layout-${Date.now()}` });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).dblclick();
  for (let i = 0; i < 5; i++) {
    await manageSignals(page);
    await page
      .getByTestId("signal-row")
      .first()
      .getByRole("button", { name: "Details", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Duplicate stored signal", exact: true })
      .click();
    await expect(page.getByTestId("signal-row")).toHaveCount(i + 2);
  }
  expect(
    await page
      .locator(".signal-rows")
      .evaluate((el) => el.scrollHeight > el.clientHeight),
  ).toBe(true);
  await page
    .locator(".signal-rows")
    .evaluate((el) => (el.scrollTop = el.scrollHeight));
  await expect(page.locator(".signal-columns")).toBeInViewport();
  await addSignal(page);
  await page
    .getByRole("button", { name: "Create from spectrum", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Maximize Mass spectrum", exact: true })
    .click();
  await expect(page.getByLabel("Signal name", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Restore Mass spectrum", exact: true })
    .click();
  await page.screenshot({
    path: "/private/tmp/tofscope-signal-workspace-desktop.png",
    fullPage: true,
  });
  await manageSignals(page);
  await page
    .getByTestId("signal-row")
    .last()
    .getByRole("button", { name: "Details", exact: true })
    .click();
  await page
    .getByLabel("Rename signal", { exact: true })
    .fill("Titanium".repeat(16));
  await page
    .getByRole("button", { name: "Save signal name", exact: true })
    .click();
  await page.setViewportSize({ width: 600, height: 800 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await expect(
    page.getByTestId("signal-row").first().getByText("Images", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Analysis settings", exact: true })
    .click();
  await expect(
    page.getByLabel("Analysis first", { exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Analysis settings", exact: true }),
  ).toBeFocused();
  await page.getByRole("button", { name: /^ROI:/ }).click();
  await expect(page.getByLabel("ROI x first", { exact: true })).toBeVisible();
});
