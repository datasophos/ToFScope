import { test, expect } from "@playwright/test";

test("depth modes show contextual controls, committed ranges and one desktop row", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `depth-modes-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  const toolbar = page.getByRole("region", {
    name: "Viewing depths",
    exact: true,
  });
  const mode = (name: string) =>
    toolbar.getByRole("button", { name, exact: true });
  await expect(mode("All frames")).toHaveAttribute("aria-pressed", "true");
  await expect(toolbar.getByRole("status")).toHaveText(
    "Summing frames 0–2 · 3 frames",
  );
  await expect(toolbar.getByLabel("Frame", { exact: true })).toHaveCount(0);
  const height = (await toolbar.boundingBox())!.height;
  await expect(
    page.getByRole("button", { name: "Analysis settings", exact: true }),
  ).toHaveCount(0);
  const csv = page
    .getByTestId("panel-profile")
    .getByRole("button", { name: "Profile CSV", exact: true });
  await expect(csv).toBeVisible();
  const downloaded = page.waitForEvent("download");
  await csv.click();
  expect((await downloaded).suggestedFilename()).toMatch(/\.csv$/);

  await mode("Single frame").click();
  await expect(mode("Single frame")).toHaveAttribute("aria-pressed", "true");
  await expect(
    toolbar.getByRole("button", { name: "Previous frame" }),
  ).toBeDisabled();
  await toolbar.getByRole("button", { name: "Next frame" }).click();
  await expect(toolbar.getByRole("status")).toHaveText(
    "Showing frame 1 of 0–2",
  );
  expect((await toolbar.boundingBox())!.height).toBe(height);

  await mode("Frame range").click();
  await expect(mode("Frame range")).toHaveAttribute("aria-pressed", "true");
  await toolbar.getByLabel("First frame", { exact: true }).fill("0");
  await toolbar.getByLabel("Last frame", { exact: true }).fill("2");
  await expect(toolbar.getByRole("status")).toHaveText(
    "Summing frames 1–1 · 1 frame",
  );
  await toolbar.getByRole("button", { name: "Apply", exact: true }).click();
  await expect(toolbar.getByRole("status")).toHaveText(
    "Summing frames 0–2 · 3 frames",
  );
  expect((await toolbar.boundingBox())!.height).toBe(height);
  await page.screenshot({ path: testInfo.outputPath("frame-range.png") });

  await mode("All frames").click();
  const profile = page.getByLabel("Depth profile selection", { exact: true });
  const box = (await profile.boundingBox())!;
  await profile.click({ position: { x: box.width / 2, y: box.height / 2 } });
  await expect(mode("Single frame")).toHaveAttribute("aria-pressed", "true");
  await expect(toolbar.getByLabel("Frame", { exact: true })).toHaveValue("1");
  await page.setViewportSize({ width: 600, height: 800 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
