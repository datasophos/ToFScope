import { openSpectrumAction } from "./spectrum-actions";
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
  await expect(panel.getByRole("button", { name: /^ROI:/ })).toHaveAttribute(
    "aria-label",
    /x 1–1/,
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
  await openSpectrumAction(page, "Create signal");
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

test("SE image selection updates the SIMS ROI and display controls reset", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `se-roi-${Date.now()}` });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  const panel = page.getByTestId("panel-ion");
  await panel.getByRole("button", { name: "Image display settings" }).click();
  await page.getByLabel("Image", { exact: true }).selectOption("se");
  await expect(page.getByLabel("Preview intensity histogram")).toBeVisible();
  const imageBox = (await panel
    .getByTestId("selection-overlay")
    .boundingBox())!;
  const dialog = page.getByRole("dialog", { name: "Image display" });
  const dialogBox = (await dialog.boundingBox())!;
  expect(dialogBox.x).toBeGreaterThanOrEqual(imageBox.x + imageBox.width);
  await expect(
    page.getByLabel("Image", { exact: true }).locator('option[value="se"]'),
  ).toHaveText("SE");
  const lower = page.getByLabel("Lower level value");
  const defaultLower = await lower.inputValue();
  const canvas = panel.locator("canvas").first();
  const before = await canvas.evaluate((c) =>
    (c as HTMLCanvasElement).toDataURL(),
  );
  await lower.fill("6");
  await lower.press("Enter");
  await expect(lower).toHaveValue("6");
  await expect
    .poll(() => canvas.evaluate((c) => (c as HTMLCanvasElement).toDataURL()))
    .not.toBe(before);
  await page.getByRole("button", { name: "Single frame", exact: true }).click();
  await expect(panel).toContainText("frames 0–0");
  await expect(lower).toHaveValue("6");
  await dialog.getByRole("button", { name: "Reset", exact: true }).click();
  await expect(lower).not.toHaveValue(defaultLower);
  await page.getByRole("button", { name: "All frames", exact: true }).click();
  await expect(panel).toContainText("frames 0–2");
  await expect(lower).toHaveValue(defaultLower);
  await page.getByRole("button", { name: "Close Image display" }).click();
  await expect(panel.getByRole("heading", { name: /SE Image/ })).toBeVisible();
  const overlay = panel.getByTestId("selection-overlay");
  await overlay.scrollIntoViewIfNeeded();
  const b = (await overlay.boundingBox())!;
  await page.mouse.move(b.x + b.width * 0.6, b.y + b.height * 0.25);
  await page.mouse.down();
  await page.mouse.move(b.x + b.width * 0.9, b.y + b.height * 0.75, {
    steps: 5,
  });
  await page.mouse.up();
  await expect(panel.getByRole("button", { name: /^ROI:/ })).toHaveAttribute(
    "aria-label",
    /x 1–1/,
  );
});

test("front projection refreshes when only the ROI X bounds change", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `roi-x-${Date.now()}` });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  const front = page.getByTestId("panel-front");
  await expect(front).toHaveAttribute("data-content-version", /.+/);
  const before = await front.getAttribute("data-content-version");
  await page.getByRole("button", { name: /^ROI:/ }).click();
  await page.getByLabel("ROI x first", { exact: true }).fill("1");
  await page.getByRole("button", { name: "Apply ROI", exact: true }).click();
  await expect(front).not.toHaveAttribute("data-content-version", before!);
  await expect(front.getByTestId("selection-overlay")).toHaveAttribute(
    "data-x-range",
    "10,20",
  );
});

test("front projection switches between XZ and YZ", async ({ page }) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `front-axis-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  const panel = page.getByTestId("panel-front");
  const toggle = panel.getByRole("button", {
    name: "Switch to Y-Z projection",
  });
  await expect(toggle).toHaveText("XZ");
  await toggle.click();
  await expect(
    panel.getByRole("button", { name: "Switch to X-Z projection" }),
  ).toHaveText("YZ");
  await expect(panel).toHaveAttribute("data-x-axis", /Y/);
  await panel.getByRole("button", { name: "Switch to X-Z projection" }).click();
  await expect(panel).toHaveAttribute("data-x-axis", /X/);
});

test("YZ projection refreshes when the ROI X bounds change", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `roi-yz-${Date.now()}` });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  const front = page.getByTestId("panel-front");
  await front.getByRole("button", { name: "Switch to Y-Z projection" }).click();
  await expect(front).toHaveAttribute("data-x-axis", /Y/);
  await expect(front).toHaveAttribute("data-content-version", /.+/);
  const before = await front.getAttribute("data-content-version");
  await page.getByRole("button", { name: /^ROI:/ }).click();
  await page.getByLabel("ROI x first", { exact: true }).fill("1");
  await page.getByRole("button", { name: "Apply ROI", exact: true }).click();
  await expect(front).not.toHaveAttribute("data-content-version", before!);
  await expect(front).toHaveAttribute("data-x-axis", /Y/);
});
