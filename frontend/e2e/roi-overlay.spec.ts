import { test, expect } from "@playwright/test";

test("ROI outline updates after drawing and exact edits without reloading the ion image", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `roi-overlay-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  const panel = page.getByTestId("panel-ion");
  const overlay = panel.getByTestId("selection-overlay");
  const rect = overlay.locator('[data-action="move"]');
  await expect(rect).toHaveAttribute("x", "0");
  const content = await panel.getAttribute("data-content-version");
  await overlay.scrollIntoViewIfNeeded();
  const b = (await overlay.boundingBox())!;
  await page.mouse.move(b.x + b.width * 0.6, b.y + b.height * 0.25);
  await page.mouse.down();
  await page.mouse.move(b.x + b.width * 0.9, b.y + b.height * 0.75, {
    steps: 5,
  });
  await page.mouse.up();
  await expect(panel.getByRole("button", { name: /^ROI:/ })).toContainText(
    "x 1–1",
  );
  await expect(rect).toHaveAttribute("x", "50");
  await expect(rect).toHaveAttribute("width", "50");
  await expect(panel).toHaveAttribute("data-content-version", content!);
  await panel.getByRole("button", { name: /^ROI:/ }).click();
  await page.getByLabel("ROI x first", { exact: true }).fill("0");
  await page.getByLabel("ROI x last", { exact: true }).fill("0");
  await page.getByRole("button", { name: "Apply ROI", exact: true }).click();
  await expect(rect).toHaveAttribute("x", "0");
  await expect(rect).toHaveAttribute("width", "50");
  await panel.getByRole("button", { name: /^ROI:/ }).click();
  await page
    .getByRole("dialog", { name: "Spatial ROI" })
    .getByRole("button", { name: "Full field", exact: true })
    .click();
  await expect(rect).toHaveAttribute("width", "100");
});

test("all four ROI edges follow the selected rectangle", async ({ page }) => {
  await page.goto("/evaluation/index.html?renderer=echarts");
  await page.getByRole("button", { name: "Probe image", exact: true }).click();
  const overlay = page.getByTestId("selection-overlay");
  await overlay.scrollIntoViewIfNeeded();
  const b = (await overlay.boundingBox())!;
  await page.mouse.move(b.x + b.width * 0.25, b.y + b.height * 0.25);
  await page.mouse.down();
  await page.mouse.move(b.x + b.width * 0.75, b.y + b.height * 0.75);
  await page.mouse.up();
  for (const action of ["low", "high"]) {
    const edge = overlay.locator(`[data-action="${action}"]`);
    await expect(edge).toHaveAttribute("y1", "25");
    await expect(edge).toHaveAttribute("y2", "75");
  }
});

test("front projection draws a full-width depth band with only horizontal handles", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `depth-band-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  const overlay = page
    .getByTestId("panel-front")
    .getByTestId("selection-overlay");
  await overlay.scrollIntoViewIfNeeded();
  const b = (await overlay.boundingBox())!;
  await page.mouse.move(b.x + b.width * 0.3, b.y + b.height * 0.2);
  await page.mouse.down();
  await page.mouse.move(b.x + b.width * 0.7, b.y + b.height * 0.8, {
    steps: 5,
  });
  const band = overlay.locator('[data-action="move"]');
  await expect(band).toHaveAttribute("x", "0");
  await expect(band).toHaveAttribute("width", "100");
  await expect(band).toHaveAttribute("stroke", "none");
  await expect(
    overlay.locator('[data-action="low"], [data-action="high"]'),
  ).toHaveCount(0);
  await expect(
    overlay.locator('[data-action="top"], [data-action="bottom"]'),
  ).toHaveCount(2);
  await page.mouse.up();
  await expect(band).toHaveAttribute("width", "100");
});

test("double-clicking the mass spectrum restores its full horizontal range", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `double-reset-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  const overlay = page
    .getByTestId("panel-spectrum")
    .getByTestId("selection-overlay");
  const full = await overlay.getAttribute("data-x-range");
  await overlay.scrollIntoViewIfNeeded();
  const b = (await overlay.boundingBox())!;
  await page.mouse.move(b.x + b.width * 0.2, b.y + b.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(b.x + b.width * 0.6, b.y + b.height * 0.5);
  await page.mouse.up();
  await expect(overlay).not.toHaveAttribute("data-x-range", full!);
  await overlay.dblclick();
  await expect(overlay).toHaveAttribute("data-x-range", full!);
  await page
    .getByTestId("panel-spectrum")
    .getByRole("button", { name: "Create signal", exact: true })
    .click();
  await page.getByLabel("Mass lower 1", { exact: true }).fill("1.25");
  await page.getByLabel("Mass upper 1", { exact: true }).fill("2.75");
  await overlay.dblclick();
  await expect(page.getByLabel("Mass lower 1", { exact: true })).toHaveValue(
    "1.25",
  );
  await expect(page.getByLabel("Mass upper 1", { exact: true })).toHaveValue(
    "2.75",
  );
});
