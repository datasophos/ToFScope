import { test, expect } from "@playwright/test";
test.use({ extraHTTPHeaders: { "x-tofscope-user": "browser-a" } });
test.setTimeout(60000);
test("independent files, exact Explore state, union calculation and offline downloads", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `explore-${Date.now()}`,
  });
  const external: string[] = [];
  page.on("request", (r) => {
    if (
      /^https?:/.test(r.url()) &&
      !r.url().startsWith("http://127.0.0.1:18763")
    )
      external.push(r.url());
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Choose an HDF5 acquisition" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).click();
  await expect(page.getByLabel("Log colors", { exact: true })).toBeChecked();
  await expect(
    page.getByLabel("Relative profiles", { exact: true }),
  ).toBeChecked();
  const ion = page.getByTestId("panel-ion").getByTestId("selection-overlay");
  await expect(ion).toBeVisible();
  const b = (await ion.boundingBox())!;
  await page.mouse.move(b.x + b.width * 0.6, b.y + b.height * 0.2);
  await page.mouse.down();
  await page.mouse.move(b.x + b.width * 0.9, b.y + b.height * 0.8, {
    steps: 5,
  });
  await page.mouse.up();
  await expect(page.getByTestId("analysis-revision")).toHaveText("1");
  for (const name of ["b.h5", "a.h5"]) {
    await page.getByRole("button", { name: "＋ Open acquisition" }).click();
    await page.getByRole("button", { name: `◫ ${name}` }).click();
  }
  await expect(page.getByRole("tab")).toHaveCount(3);
  await page.getByRole("tab", { name: "1 · a.h5" }).click();
  await expect(
    page.getByRole("button", { name: /^ROI:/ }).filter({ visible: true }),
  ).toContainText("x 1–1");
  const screen = page.locator(".explore-screen").filter({ visible: true });
  await screen
    .getByRole("button", { name: "Create from spectrum", exact: true })
    .click();
  await screen.getByLabel("Mass lower 1", { exact: true }).fill("1");
  await screen.getByLabel("Mass upper 1", { exact: true }).fill("2");
  await screen
    .getByRole("button", { name: "Add interval", exact: true })
    .click();
  await screen.getByLabel("Mass lower 2", { exact: true }).fill("4");
  await screen.getByLabel("Mass upper 2", { exact: true }).fill("5");
  await screen
    .getByRole("button", { name: "Calculate signal", exact: true })
    .click();
  await expect(
    screen.getByRole("region", { name: "Signal editor" }),
  ).toBeHidden();
  await expect(screen.getByTestId("signal-row").last()).toContainText(
    "Raw integration",
  );
  await screen
    .getByRole("button", { name: "Maximize Mass spectrum", exact: true })
    .click();
  await expect(screen.locator(".spectrum-workbench.maximized")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(screen.locator(".spectrum-workbench.maximized")).toHaveCount(0);
  const download = page.waitForEvent("download");
  await screen
    .getByRole("button", { name: "Settings JSON", exact: true })
    .click();
  expect((await download).suggestedFilename()).toMatch(/\.json$/);
  expect(external).toEqual([]);
});

test("Explore layout, signal picker and chart wheel behavior", async ({
  page,
}) => {
  await page.route("**/analyses/*/data?*", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 500));
    await route.continue();
  });
  await page.addInitScript(() => {
    const state = window as Window & { imageStageFlash?: boolean };
    state.imageStageFlash = false;
    const check = () => {
      if (
        Array.from(
          document.querySelectorAll<HTMLElement>(".plot-stage.image"),
        ).some(
          (stage) =>
            stage.dataset.stageReady !== "true" &&
            stage.querySelector("canvas"),
        )
      )
        state.imageStageFlash = true;
    };
    new MutationObserver(check).observe(document, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-stage-ready"],
    });
  });
  await page.setExtraHTTPHeaders({ "x-tofscope-user": "browser-b" });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Choose an HDF5 acquisition" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).click();
  const ionLoader = page
    .getByTestId("panel-ion")
    .getByRole("status", { name: "Loading image plot" });
  await expect(ionLoader).toBeVisible();
  await expect(ionLoader).toBeHidden();
  const spectrum = page.getByTestId("panel-spectrum");
  await expect(spectrum).toHaveAttribute("data-y-scale", "log");
  const logSpectrum = await spectrum
    .locator("canvas")
    .first()
    .evaluate((canvas: HTMLCanvasElement) => canvas.toDataURL());
  await spectrum.getByRole("button", { name: "Use linear y scale" }).click();
  await expect(spectrum).toHaveAttribute("data-y-scale", "linear");
  await expect
    .poll(
      async () =>
        (await spectrum
          .locator("canvas")
          .first()
          .evaluate((canvas: HTMLCanvasElement) => canvas.toDataURL())) !==
        logSpectrum,
    )
    .toBe(true);
  await spectrum
    .getByRole("button", { name: "Use logarithmic y scale" })
    .click();
  await expect(spectrum).toHaveAttribute("data-y-scale", "log");
  await expect
    .poll(
      async () =>
        (await spectrum
          .locator("canvas")
          .first()
          .evaluate((canvas: HTMLCanvasElement) => canvas.toDataURL())) ===
        logSpectrum,
    )
    .toBe(true);
  const panels = ["ion", "spectrum", "front", "profile"].map((name) =>
    page.getByTestId(`panel-${name}`),
  );
  const boxes = await Promise.all(panels.map((panel) => panel.boundingBox()));
  expect(boxes[0]!.y).toBeLessThan(boxes[2]!.y);
  expect(boxes[1]!.y).toBeLessThan(boxes[3]!.y);
  expect(Math.abs(boxes[0]!.x - boxes[2]!.x)).toBeLessThan(2);
  expect(Math.abs(boxes[1]!.x - boxes[3]!.x)).toBeLessThan(2);
  expect(boxes[0]!.width).toBeLessThan(boxes[1]!.width * 0.8);
  const imageStage = page.getByTestId("plot-stage-ion");
  await expect(imageStage).toBeVisible();
  await expect(imageStage).toHaveAttribute("data-stage-ready", "true");
  expect(
    await page.evaluate(
      () => (window as Window & { imageStageFlash?: boolean }).imageStageFlash,
    ),
  ).toBe(false);
  const imageBox = (await imageStage.boundingBox())!;
  expect(Math.abs(imageBox.width - imageBox.height)).toBeLessThan(2);
  const picker = page.getByRole("button", { name: "Add stored signal" });
  await expect(picker).toBeVisible();
  await expect(page.getByLabel("Search stored signals")).toBeHidden();
  await picker.click();
  await expect(page.getByLabel("Search stored signals")).toBeFocused();
  await expect(
    page.locator(".signal-picker-popover").getByLabel("Search stored signals"),
  ).toBeVisible();
  await expect(
    page.getByRole("listbox", { name: "Stored signals" }),
  ).toBeVisible();
  expect(
    await page
      .getByRole("listbox", { name: "Stored signals" })
      .evaluate((element) => element.getBoundingClientRect().height),
  ).toBeLessThanOrEqual(200);
  await page.getByLabel("Search stored signals").fill("2");
  await expect(
    page.getByRole("listbox", { name: "Stored signals" }).getByRole("option"),
  ).toHaveCount(1);
  await expect(page.locator("select[aria-label='Stored signal']")).toHaveCount(
    0,
  );
  await page.getByLabel("Search stored signals").fill("no such signal");
  await expect(page.getByText("No matching signals")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(picker).toBeFocused();
  await picker.click();
  await expect(page.getByLabel("Search stored signals")).toHaveValue("");
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("listbox", { name: "Stored signals" }),
  ).toBeHidden();

  const overlay = page
    .getByTestId("panel-spectrum")
    .getByTestId("selection-overlay");
  await overlay.scrollIntoViewIfNeeded();
  let range = await overlay.getAttribute("data-x-range");
  const bounds = (await overlay.boundingBox())!;
  const beforeScroll = await page.evaluate(() => window.scrollY);
  await page.mouse.move(
    bounds.x + bounds.width / 2,
    bounds.y + bounds.height / 2,
  );
  await page.mouse.wheel(0, 140);
  await expect
    .poll(() => page.evaluate(() => window.scrollY))
    .toBeGreaterThan(beforeScroll);
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

test("full-size image maximize and restore stay responsive without fetching data", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `resize-${Date.now()}` });
  let dataRequests = 0;
  await page.route("**/analyses/*/data?*", async (route) => {
    dataRequests++;
    const response = await route.fetch();
    const data = await response.json();
    for (const name of ["ion", "front"]) {
      const panel = data.panels[name];
      if (!panel) continue;
      const rows = name === "ion" ? 128 : 1301;
      for (const [index, count] of [
        [0, 128],
        [1, rows],
      ]) {
        const axis = panel.axes[index];
        const low = axis.boundaries[0],
          high = axis.boundaries.at(-1);
        axis.values = Array.from(
          { length: count },
          (_, i) => low + ((i + 0.5) * (high - low)) / count,
        );
      }
      panel.values = Array.from({ length: rows }, (_, y) =>
        Array.from({ length: 128 }, (_, x) => x + y),
      );
      panel.intensity_range = [0, rows + 126];
    }
    await route.fulfill({ response, json: data });
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Choose an HDF5 acquisition" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).click();
  await expect(
    page.getByTestId("panel-front").locator("canvas").first(),
  ).toBeVisible();
  const requestsBefore = dataRequests;
  for (const name of ["ion", "front"]) {
    const panel = page.getByTestId(`panel-${name}`);
    const times: number[] = [];
    for (let i = 0; i < 6; i++) {
      times.push(
        await panel.evaluate(async (el) => {
          const start = performance.now();
          el.querySelector<HTMLButtonElement>(
            'button[aria-label^="Maximize"],button[aria-label^="Restore"]',
          )!.click();
          await new Promise((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(resolve)),
          );
          return performance.now() - start;
        }),
      );
      const canvas = await panel.locator("canvas").first().boundingBox();
      const stage = await panel.locator(".plot-stage").boundingBox();
      expect(Math.abs(canvas!.width - stage!.width)).toBeLessThan(2);
      expect(Math.abs(canvas!.height - stage!.height)).toBeLessThan(2);
    }
    console.log(JSON.stringify({ image: name, resize_ms: times }));
    expect(
      Math.max(...times),
      `${name} resize must paint within 200 ms`,
    ).toBeLessThan(200);
  }
  expect(dataRequests).toBe(requestsBefore);
});
