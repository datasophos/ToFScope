import { test, expect } from "@playwright/test";
test.use({ extraHTTPHeaders: { "x-tofscope-user": "browser-a" } });
test.setTimeout(60000);
test("independent files, exact Explore state, custom Apply and offline downloads", async ({
  page,
}) => {
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
  await expect(page.getByLabel("Stored signal")).toBeVisible();
  await page.getByLabel("Stored signal").selectOption("0");
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
  await page.getByRole("button", { name: "◫ a.h5" }).click();
  await expect(
    page.getByTestId("analysis-revision").filter({ visible: true }),
  ).toHaveText("0");
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
