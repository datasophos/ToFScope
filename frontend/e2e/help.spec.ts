import { test, expect } from "@playwright/test";

// A stalled action should name its locator before the overall test budget expires.
test.use({ actionTimeout: 10_000 });

test.beforeEach(async ({ page }) => {
  await test.step("Open a disposable acquisition", async () => {
    await page.setExtraHTTPHeaders({
      "x-tofscope-user": `help-${crypto.randomUUID()}`,
    });
    await page.goto("/");
    await expect(page.locator(".brand svg")).toBeVisible();
    await expect(page.locator(".brand-name")).toContainText(
      "FIB–SEM / TOF–SIMS",
    );
    await page
      .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
      .click();
    await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
    await expect(
      page.getByRole("heading", { name: "a.h5", exact: true }),
    ).toBeVisible();
  });
});

test("help buttons are discoverable and hover help stays within the viewport", async ({
  page,
}) => {
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
});

test("keyboard and pinned help dismiss without changing analysis state", async ({
  page,
}) => {
  const tooltip = page.getByRole("tooltip");
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
});

test("Escape dismisses help before restoring a maximized plot", async ({
  page,
}) => {
  const tooltip = page.getByRole("tooltip");
  const ionHelp = page.getByRole("button", {
    name: "Ion map help",
    exact: true,
  });
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
});

test("SE image help follows the displayed image type", async ({ page }) => {
  const tooltip = page.getByRole("tooltip");
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

test("plot heading help stays clickable beside toolbars with larger text", async ({
  page,
}, testInfo) => {
  // Larger text reproduces the overflow caused by Linux font metrics in CI.
  await page.addStyleTag({
    content: ".plot-panel header h2 { font-size: 20px; }",
  });
  await page
    .getByRole("button", { name: "Image display settings", exact: true })
    .click();
  await page.getByLabel("Image", { exact: true }).selectOption("se");
  await page
    .getByRole("button", { name: "Close Image display", exact: true })
    .click();
  for (const label of [
    "SE Image",
    "Mass spectrum",
    "Front projection",
    "Depth profile",
  ]) {
    const help = page.getByRole("button", {
      name: `${label} help`,
      exact: true,
    });
    await help.scrollIntoViewIfNeeded();
    await expect
      .poll(
        () =>
          help.evaluate((button) => {
            const box = button.getBoundingClientRect();
            const hit = document.elementFromPoint(
              box.x + box.width / 2,
              box.y + box.height / 2,
            );
            return hit === button || button.contains(hit);
          }),
        { message: `${label} help must not be covered by its toolbar` },
      )
      .toBe(true);
    await help.click();
    await expect(page.getByRole("tooltip")).toBeVisible();
    await page.keyboard.press("Escape");
  }
  await page.screenshot({
    path: testInfo.outputPath("accessible-plot-headings.png"),
    fullPage: true,
  });
});
