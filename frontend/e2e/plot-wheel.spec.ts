import { test, expect } from "@playwright/test";

test("modifier wheel zoom consumes scrolling, ordinary wheel still scrolls the page", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `wheel-${Date.now()}` });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  const overlay = page
    .getByTestId("panel-profile")
    .getByLabel("Depth profile selection");
  await overlay.hover();
  await page.evaluate(() => {
    (window as any).plotWheel = [];
    document.addEventListener(
      "wheel",
      (e) =>
        (window as any).plotWheel.push({
          prevented: e.defaultPrevented,
          modifier: e.ctrlKey || e.metaKey,
        }),
      { passive: true },
    );
  });
  const scroll = await page.evaluate(() => window.scrollY);
  const before = await overlay.getAttribute("data-x-range");
  for (const key of ["Control", "Meta"]) {
    await page.keyboard.down(key);
    await page.mouse.wheel(0, -120);
    await page.keyboard.up(key);
    await expect
      .poll(() =>
        page.evaluate(() => (window as any).plotWheel.at(-1)?.prevented),
      )
      .toBe(true);
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(scroll);
  }
  await expect(overlay).not.toHaveAttribute("data-x-range", before!);
  await page.mouse.wheel(0, -120);
  await expect
    .poll(() =>
      page.evaluate(() => (window as any).plotWheel.at(-1)?.prevented),
    )
    .toBe(false);
  await expect
    .poll(() => page.evaluate(() => window.scrollY))
    .toBeLessThan(scroll);
});
