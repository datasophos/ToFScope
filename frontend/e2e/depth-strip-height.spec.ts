import { expect, test } from "@playwright/test";

test("viewing depths keeps the same height across modes", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `depth-height-${Date.now()}` });
  await page.goto("/");
  await page.getByRole("button", { name: /Open TOFexplorer/ }).first().click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  const strip = page.getByRole("region", { name: "Viewing depths" });
  const initial = (await strip.boundingBox())!.height;
  await strip.getByRole("button", { name: "Single frame" }).click();
  await expect(strip.getByLabel("Depth slider")).toBeVisible();
  expect((await strip.boundingBox())!.height).toBe(initial);
  await strip.getByRole("button", { name: "Frame range" }).click();
  await expect(strip.getByLabel("First frame")).toBeVisible();
  expect((await strip.boundingBox())!.height).toBe(initial);
});
