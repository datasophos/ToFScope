import { test, expect } from "@playwright/test";
test.use({ extraHTTPHeaders: { "x-tofscope-user": "browser-a" } });
test.setTimeout(60000);
test("independent files, exact Explore state, custom Apply and offline downloads", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `explore-${Date.now()}-${Math.random()}`,
  });
  const requests: string[] = [];
  page.on("request", (r) => {
    if (
      /^https?:/.test(r.url()) &&
      !r.url().startsWith("http://127.0.0.1:18763")
    )
      requests.push(r.url());
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Choose an HDF5 acquisition" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).click();
  await expect(page.getByRole("button", { name: "Select stored signal" })).toBeVisible();
  await page.getByRole("button", { name: "Select stored signal" }).click();
  await page.getByRole("listbox", { name: "Stored signals" }).getByRole("option").first().click();
  await expect(page.getByTestId("analysis-revision")).toHaveText("1");
  const ion = page.getByTestId("panel-ion").getByTestId("selection-overlay");
  const bounds = (await ion.boundingBox())!;
  await page.mouse.move(
    bounds.x + bounds.width * 0.6,
    bounds.y + bounds.height * 0.2,
  );
  await page.mouse.down();
  await page.mouse.move(
    bounds.x + bounds.width * 0.9,
    bounds.y + bounds.height * 0.8,
    { steps: 5 },
  );
  await page.mouse.up();
  await expect(page.getByLabel("ROI x first")).toHaveValue("1");
  await expect(page.getByTestId("analysis-revision")).toHaveText("2");
  await page.getByRole("button", { name: "＋ Open acquisition" }).click();
  await page.getByRole("button", { name: "◫ b.h5" }).click();
  await expect(
    page.getByTestId("analysis-revision").filter({ visible: true }),
  ).toHaveText("0");
  await expect(page.getByRole("tab", { name: "2 · b.h5" })).toBeVisible();
  await page.getByRole("button", { name: "＋ Open acquisition" }).click();
  await page.getByRole("button", { name: "◫ a.h5" }).click();
  await expect(page.getByRole("tab", { name: "3 · a.h5" })).toBeVisible();
  await page.getByRole("tab", { name: "1 · a.h5" }).click();
  await expect(
    page.getByLabel("ROI x first").filter({ visible: true }),
  ).toHaveValue("1");
  const screen = page.locator(".explore-screen").filter({ visible: true });
  await screen.getByLabel("Mass lower 1").fill("1");
  await screen.getByLabel("Mass upper 1").fill("2");
  await screen.getByRole("button", { name: "Add interval" }).click();
  await screen.getByLabel("Mass lower 2").fill("4");
  await screen.getByLabel("Mass upper 2").fill("5");
  await screen
    .getByRole("button", { name: "Apply custom window", exact: true })
    .click();
  await expect(screen.getByTestId("job-status")).toContainText("succeeded");
  await expect(screen.getByTestId("active-source")).toContainText("custom");
  await screen.getByRole("button", { name: "Maximize Spectrum" }).click();
  await expect(screen.locator(".plot-panel.maximized")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(screen.locator(".plot-panel.maximized")).toHaveCount(0);
  const download = page.waitForEvent("download");
  await screen.getByRole("button", { name: "Settings JSON" }).click();
  expect((await download).suggestedFilename()).toMatch(/\.json$/);
  expect(requests).toEqual([]);
});

test("Explore layout, signal picker and chart wheel behavior", async ({ page }) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": "browser-b" });
  await page.goto("/");
  await page.getByRole("button", { name: "Choose an HDF5 acquisition" }).click();
  await page.getByRole("button", { name: "◫ a.h5" }).click();
  const panels = ["ion", "spectrum", "front", "profile"].map((name) =>
    page.getByTestId(`panel-${name}`),
  );
  const boxes = await Promise.all(panels.map((panel) => panel.boundingBox()));
  expect(boxes[0]!.y).toBeLessThan(boxes[2]!.y);
  expect(boxes[1]!.y).toBeLessThan(boxes[3]!.y);
  expect(Math.abs(boxes[0]!.x - boxes[2]!.x)).toBeLessThan(2);
  expect(Math.abs(boxes[1]!.x - boxes[3]!.x)).toBeLessThan(2);
  const imageStage = page.getByTestId("plot-stage-ion");
  await expect(imageStage).toBeVisible();
  const imageBox = (await imageStage.boundingBox())!;
  expect(Math.abs(imageBox.width - imageBox.height)).toBeLessThan(2);
  const picker = page.getByRole("button", { name: "Select stored signal" });
  await expect(picker).toBeVisible();
  await picker.click();
  await expect(page.getByRole("listbox", { name: "Stored signals" })).toBeVisible();
  expect(
    await page
      .getByRole("listbox", { name: "Stored signals" })
      .evaluate((element) => element.getBoundingClientRect().height),
  ).toBeLessThanOrEqual(200);
  await page.getByLabel("Search signals").fill("2");
  await expect(
    page.getByRole("listbox", { name: "Stored signals" }).getByRole("option"),
  ).toHaveCount(1);
  await expect(page.locator("select[aria-label='Stored signal']")).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("listbox", { name: "Stored signals" })).toBeHidden();

  const overlay = page
    .getByTestId("panel-spectrum")
    .getByTestId("selection-overlay");
  await overlay.scrollIntoViewIfNeeded();
  let range = await overlay.getAttribute("data-x-range");
  const bounds = (await overlay.boundingBox())!;
  const beforeScroll = await page.evaluate(() => window.scrollY);
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  await page.mouse.wheel(0, 140);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(beforeScroll);
  await expect(overlay).toHaveAttribute("data-x-range", range!);
  range = await overlay.getAttribute("data-x-range");
  const afterPageScroll = (await overlay.boundingBox())!;
  await page.keyboard.down("Control");
  await page.mouse.move(
    afterPageScroll.x + afterPageScroll.width / 2,
    afterPageScroll.y + afterPageScroll.height / 2,
  );
  await page.mouse.wheel(0, -140);
  await page.keyboard.up("Control");
  await expect(overlay).not.toHaveAttribute("data-x-range", range!);
});
