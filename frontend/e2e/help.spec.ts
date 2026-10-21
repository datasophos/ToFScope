import { test, expect } from "@playwright/test";

test("contextual help works with mouse, keyboard and maximized panes", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `help-${Date.now()}` });
  await page.goto("/");
  await expect(page.locator(".brand svg")).toBeVisible();
  await expect(page.locator(".brand-name")).toContainText("FIB–SEM / TOF–SIMS");
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).dblclick();
  for (const label of [
    "Files and saved analyses",
    "Signals",
    "Exports",
    "Ion map",
    "Mass spectrum",
    "Front projection",
    "Depth profile",
  ]) {
    await expect(
      page.getByRole("button", { name: `${label} help`, exact: true }),
    ).toBeVisible();
  }
  const ionHelp = page.getByRole("button", {
    name: "Ion map help",
    exact: true,
  });
  await ionHelp.hover();
  const tooltip = page.getByRole("tooltip");
  await expect(tooltip).toContainText("Draw a rectangle");
  expect(await ionHelp.getAttribute("aria-describedby")).toBe(
    await tooltip.getAttribute("id"),
  );
  const bounds = (await tooltip.boundingBox())!;
  expect(bounds.x).toBeGreaterThanOrEqual(0);
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(
    page.viewportSize()!.width,
  );
  expect(bounds.y).toBeGreaterThanOrEqual(0);
  expect(bounds.y + bounds.height).toBeLessThanOrEqual(
    page.viewportSize()!.height,
  );
  expect(
    await tooltip.evaluate((el) => {
      const b = el.getBoundingClientRect();
      return el.contains(
        document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2),
      );
    }),
  ).toBe(true);
  await page.mouse.move(0, 0);
  await expect(tooltip).toBeHidden();

  const massHelp = page.getByRole("button", {
    name: "Mass spectrum help",
    exact: true,
  });
  await massHelp.focus();
  await expect(tooltip).toContainText("vendor-summed");
  await page.keyboard.press("Escape");
  await expect(tooltip).toBeHidden();
  await expect(massHelp).toBeFocused();

  await page
    .getByRole("button", { name: "Depth profile help", exact: true })
    .click();
  await page.mouse.move(0, 0);
  await expect(tooltip).toContainText("mean");
  await page.getByRole("heading", { name: "a.h5", exact: true }).click();
  await expect(tooltip).toBeHidden();
  await expect(page.getByTestId("analysis-revision")).toHaveText("0");

  await page
    .getByRole("button", { name: "Maximize Ion map", exact: true })
    .click();
  await ionHelp.focus();
  await expect(tooltip).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(tooltip).toBeHidden();
  await expect(page.locator(".plot-panel.maximized")).toHaveCount(1);
  await page.keyboard.press("Escape");
  await expect(page.locator(".plot-panel.maximized")).toHaveCount(0);

  await page
    .getByRole("button", { name: "Image display settings", exact: true })
    .click();
  await page.getByLabel("Image", { exact: true }).selectOption("se");
  await page
    .getByRole("button", { name: "Close Image display", exact: true })
    .click();
  await page
    .getByRole("button", { name: "SE Image help", exact: true })
    .click();
  await expect(tooltip).toContainText("native pixels");
  await expect(tooltip).toContainText("unregistered");
});
