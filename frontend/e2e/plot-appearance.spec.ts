import { test, expect } from "@playwright/test";

test("plots have no resize handles and share rounded maximized surfaces", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `appearance-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  for (const [id, title] of [
    ["ion", "Ion map"],
    ["front", "Front projection"],
    ["profile", "Depth profile"],
    ["spectrum", "Mass spectrum"],
  ]) {
    const panel = page.getByTestId(`panel-${id}`);
    await expect(panel).toHaveCSS("resize", "none");
    await panel
      .getByRole("button", { name: `Maximize ${title}`, exact: true })
      .click();
    const surface =
      id === "spectrum" ? page.locator(".spectrum-workbench.maximized") : panel;
    await expect(surface).toHaveCSS("border-radius", "7px");
    await expect(surface).toHaveCSS(
      "box-shadow",
      "rgba(32, 55, 68, 0.6) 0px 0px 0px 30px",
    );
    await expect(panel).toHaveCSS("resize", "none");
    if (id === "spectrum") {
      await expect
        .poll(async () =>
          panel
            .locator("canvas")
            .first()
            .evaluate((canvas) =>
              Math.abs(
                canvas.getBoundingClientRect().width -
                  canvas.closest(".chart")!.getBoundingClientRect().width,
              ),
            ),
        )
        .toBeLessThan(2);
      await page.screenshot({
        path: testInfo.outputPath("maximized-spectrum.png"),
      });
    }
    await panel
      .getByRole("button", { name: `Restore ${title}`, exact: true })
      .click();
  }
});
