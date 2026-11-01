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

test("favicon uses the header logo and is served as SVG", async ({ page }) => {
  await page.goto("/");
  const href = await page.locator('link[rel="icon"]').getAttribute("href");
  expect(href).toBeTruthy();
  const response = await page.request.get(href!);
  expect(response.ok()).toBe(true);
  expect(response.headers()["content-type"]).toContain("image/svg+xml");
  const svg = await response.text();
  expect(svg).toContain(
    await page.locator(".brand svg path").getAttribute("d"),
  );
  expect(svg).toContain('fill="#44bdac"');
});

test("Datasophos credit displays the supplied wordmark", async ({ page }) => {
  await page.goto("/");
  const navDocs = page
    .getByRole("navigation", { name: "Files and open analyses" })
    .getByRole("link", { name: "Documentation", exact: true });
  await expect(navDocs).toBeVisible();
  await expect(navDocs.locator("svg")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Files and saved analyses help" }),
  ).toHaveCount(0);
  await expect(navDocs).toHaveAttribute(
    "href",
    "https://datasophos.github.io/ToFScope/",
  );
  const repo = page
    .getByRole("navigation", { name: "Files and open analyses" })
    .getByRole("link", { name: "GitHub repository" });
  await expect(repo).toBeVisible();
  await expect(repo).toHaveAttribute(
    "href",
    "https://github.com/datasophos/ToFScope",
  );
  await expect(repo).toHaveAttribute("target", "_blank");
  const footer = page.getByRole("contentinfo");
  const docs = footer.getByRole("link", { name: "Documentation", exact: true });
  await expect(docs).toBeVisible();
  await expect(docs).toHaveAttribute(
    "href",
    "https://datasophos.github.io/ToFScope/",
  );
  await expect(docs).toHaveAttribute("target", "_blank");
  await expect(
    footer.getByRole("link", { name: "Made by Datasophos", exact: true }),
  ).toHaveAttribute("href", "https://datasophos.co");
  await expect(
    footer.getByRole("link", { name: "Report an issue", exact: true }),
  ).toHaveAttribute("href", "https://github.com/datasophos/ToFScope/issues");
  await expect(
    footer
      .getByRole("link", { name: "Report an issue", exact: true })
      .locator("svg"),
  ).toBeVisible();
  const logo = footer.getByRole("img", { name: "Datasophos", exact: true });
  await expect(logo).toBeVisible();
  await expect
    .poll(() => logo.evaluate((el) => (el as HTMLImageElement).naturalWidth))
    .toBeGreaterThan(0);
});
