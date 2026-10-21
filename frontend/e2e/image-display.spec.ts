import { test, expect } from "@playwright/test";

test("image panes keep full extents and colormap changes repaint pixels", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `image-display-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  const ion = page.getByTestId("panel-ion");
  await expect(ion.locator("canvas").first()).toBeVisible();
  const pixels = () =>
    ion
      .locator("canvas")
      .first()
      .evaluate((c) => (c as HTMLCanvasElement).toDataURL());
  const before = await pixels();
  await expect(page.getByLabel("SIMS colormap", { exact: true })).toHaveCount(
    0,
  );
  const stage = ion.getByTestId("plot-stage-ion");
  const initialSize = await stage.boundingBox();
  const context = await ion.locator(".plot-context").boundingBox();
  expect(context!.height).toBeLessThan(80);
  await ion.getByRole("button", { name: "Image display settings" }).click();
  await expect(
    page.getByRole("dialog", { name: "Image display" }),
  ).toBeVisible();
  expect((await stage.boundingBox())!.height).toBe(initialSize!.height);
  await page.getByLabel("SIMS colormap", { exact: true }).selectOption("magma");
  await expect(ion).toHaveAttribute("data-palette", "magma");
  await page
    .getByRole("button", { name: "Close Image display", exact: true })
    .click();
  await expect(page.getByLabel("SIMS colormap", { exact: true })).toHaveCount(
    0,
  );
  await expect.poll(pixels).not.toBe(before);
  await ion.screenshot({
    path: test.info().outputPath("compact-ion-controls.png"),
  });
  for (const name of ["ion", "front"]) {
    const panel = page.getByTestId(`panel-${name}`);
    await expect(
      panel.getByRole("button", { name: "Pan", exact: true }),
    ).toHaveCount(0);
    await expect(
      panel.getByRole("button", { name: "Reset zoom", exact: true }),
    ).toHaveCount(0);
    const overlay = panel.getByTestId("selection-overlay");
    const range = await overlay.getAttribute("data-x-range");
    await overlay.dispatchEvent("wheel", { deltaY: -120, ctrlKey: true });
    await expect(overlay).toHaveAttribute("data-x-range", range!);
  }
});

test("nonuniform calibrated rows retain opaque colors at display resolution", async ({
  page,
}) => {
  await page.goto("/evaluation/index.html");
  const alpha = await page.evaluate(async () => {
    // @ts-expect-error Vite serves this module directly in the browser.
    const { mountChart } = await import("/src/plots/selectedRenderer.ts");
    const element = document.createElement("div");
    element.style.cssText = "width:400px;height:400px";
    document.body.append(element);
    const y = Array.from({ length: 1301 }, (_, i) =>
      i <= 300 ? i * 0.3 : 90 + (i - 300) * 0.7,
    );
    const chart = mountChart(element, {
      kind: "image",
      x: [0, 1],
      y,
      values: y.map(() => [1, 1]),
      xRange: [-0.5, 1.5],
      yRange: [0, 790],
      yReverse: true,
      range: [0, 1],
      xLabel: "X",
      yLabel: "Depth",
    });
    await new Promise(requestAnimationFrame);
    const canvas = element.querySelector("canvas")!;
    const ratio = canvas.width / 400;
    const context = canvas.getContext("2d")!;
    const values = Array.from(
      { length: 250 },
      (_, i) =>
        context.getImageData(
          Math.round(200 * ratio),
          Math.round((60 + i) * ratio),
          1,
          1,
        ).data[3],
    );
    chart.destroy();
    element.remove();
    return values;
  });
  expect(Math.min(...alpha)).toBe(255);
});
