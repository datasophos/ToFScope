import { test, expect as baseExpect, type Page } from "@playwright/test";

// VTK startup and analysis polling can take longer on software-rendered CI.
const expect = baseExpect.configure({ timeout: 15_000 });
test.setTimeout(60_000);
async function open(page: Page) {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `volume-${Date.now()}-${Math.random()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page
    .getByRole("button", { name: "◫ spatial.h5", exact: true })
    .dblclick();
  await expect(page.getByTestId("analysis")).toBeVisible();
}
async function command(page: Page, command: any) {
  const revision = await page.evaluate(async (c) => {
    const session = await (await fetch("/api/v1/auth/session")).json();
    const [a] = await (await fetch("/api/v1/analyses")).json();
    const r = await fetch(`/api/v1/analyses/${a.id}/commands`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": session.csrf,
      },
      body: JSON.stringify({
        request_id: crypto.randomUUID(),
        expected_revision: a.revision,
        dataset_generation: a.dataset.generation,
        command: c,
      }),
    });
    if (!r.ok) throw new Error(await r.text());
    return (await r.json()).revision;
  }, command);
  await expect(page.getByTestId("analysis")).toHaveAttribute(
    "data-revision",
    String(revision),
  );
}
async function state(page: Page) {
  return page.evaluate(
    async () => (await (await fetch("/api/v1/analyses")).json())[0],
  );
}
async function volumeData(page: Page) {
  return page.evaluate(async () => {
    const [a] = await (await fetch("/api/v1/analyses")).json();
    return (await fetch(`/api/v1/analyses/${a.id}/volumes`)).json();
  });
}
async function setupLayers(page: Page, count = 3) {
  for (let i = 0; i < count; i++)
    await command(page, { type: "add_stored_signal", index: i });
  const a = await state(page);
  await command(page, {
    type: "set_spatial",
    spatial: {
      ...a.spatial,
      screen: "volume",
      layers: a.signals
        .slice(0, count)
        .map((s: any) => ({ signal_id: s.id, percentile: 0 })),
    },
  });
  await expect(page.getByTestId("volume-status")).toContainText(
    `${count} layers`,
  );
  await expect(
    page.getByTestId("volume-canvas").locator("canvas").first(),
  ).toBeVisible();
}
test("3D signal table starts with the image signal and recovers a saved solo selection", async ({
  page,
}) => {
  await open(page);
  await command(page, { type: "add_stored_signal", index: 0 });
  const before = await state(page);
  const main = before.signals.find((s: any) => s.id === before.image_signal_id);
  const other = before.signals.find(
    (s: any) => s.id !== before.image_signal_id,
  );
  await page.getByRole("tab", { name: "3D volume" }).click();
  await expect(
    page.getByRole("checkbox", { name: `Show ${main.name} in 3D` }),
  ).toBeChecked();
  await expect(
    page.getByRole("checkbox", { name: `Show ${other.name} in 3D` }),
  ).not.toBeChecked();
  await expect(page.getByTestId("panel-profile")).not.toBeVisible();
  await page
    .getByRole("checkbox", { name: `Show ${other.name} in 3D` })
    .check();
  await expect(page.getByTestId("volume-status")).toContainText("2 layers");
  const current = await state(page);
  await command(page, {
    type: "set_spatial",
    spatial: { ...current.spatial, solo: main.id },
  });
  await expect(
    page.getByRole("checkbox", { name: `Show ${other.name} in 3D` }),
  ).not.toBeChecked();
  await page
    .getByRole("checkbox", { name: `Show ${other.name} in 3D` })
    .check();
  await expect.poll(async () => (await state(page)).spatial.solo).toBeNull();
  await expect(page.getByTestId("volume-status")).toContainText("2 layers");
  await page
    .getByRole("button", { name: `3D settings for ${other.name}` })
    .click();
  await expect(page.getByLabel(`3D opacity for ${other.name}`)).toBeVisible();
  await page.getByRole("button", { name: "Close 3D signal settings" }).click();
  await page
    .getByRole("checkbox", { name: `Show ${main.name} in 3D` })
    .uncheck();
  await page
    .getByRole("checkbox", { name: `Show ${other.name} in 3D` })
    .uncheck();
  await page.getByRole("tab", { name: "Explore" }).click();
  await page.getByRole("tab", { name: "3D volume" }).click();
  await expect(
    page.getByRole("checkbox", { name: `Show ${main.name} in 3D` }),
  ).not.toBeChecked();
  await expect(
    page.getByRole("checkbox", { name: `Show ${other.name} in 3D` }),
  ).not.toBeChecked();
});

test("3D view and preview switches change their settings", async ({ page }) => {
  await open(page);
  await setupLayers(page, 1);
  const view = page.getByRole("switch", { name: "Tiles view" });
  const quality = page.getByRole("switch", { name: "Detailed preview" });
  await expect(view).toHaveAttribute("aria-checked", "false");
  await expect(quality).toHaveAttribute("aria-checked", "false");
  await view.click();
  await quality.click();
  await expect.poll(async () => (await state(page)).spatial.mode).toBe("tiles");
  await expect
    .poll(async () => (await state(page)).spatial.quality)
    .toBe("Detailed");
  await expect(view).toHaveAttribute("aria-checked", "true");
  await expect(quality).toHaveAttribute("aria-checked", "true");
});

test("3D preview keeps its size while a new preview loads", async ({
  page,
}) => {
  await open(page);
  await setupLayers(page, 1);
  const canvas = page.getByTestId("volume-canvas");
  const before = (await canvas.boundingBox())!;
  await page.route("**/api/v1/analyses/*/volumes", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1200));
    await route.continue();
  });
  await page.getByRole("switch", { name: "Detailed preview" }).click();
  const placeholder = page.getByRole("status", {
    name: "Preparing 3D preview",
  });
  await expect(placeholder).toBeVisible();
  const during = (await placeholder.boundingBox())!;
  expect(during.width).toBeCloseTo(before.width, 0);
  expect(during.height).toBeCloseTo(before.height, 0);
  await expect(placeholder).toBeHidden();
  await expect(
    page.getByTestId("volume-canvas").locator("canvas"),
  ).toBeVisible();
});
test("maximizing 3D expands the canvas and restores its size", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await open(page);
  await setupLayers(page, 2);
  await page.getByRole("switch", { name: "Tiles view" }).click();
  const canvas = page.getByTestId("volume-canvas");
  await expect(page.getByTestId("vtk-tile")).toHaveCount(2);
  const titleInset = await page
    .locator(".vtk-tile")
    .first()
    .evaluate((tile) => {
      const title = tile.firstElementChild!;
      const range = document.createRange();
      range.selectNodeContents(title);
      const text = range.getBoundingClientRect(),
        bounds = tile.getBoundingClientRect();
      return { x: text.x - bounds.x, y: text.y - bounds.y };
    });
  expect(titleInset.x).toBeGreaterThanOrEqual(8);
  expect(titleInset.y).toBeGreaterThanOrEqual(8);
  const initial = (await canvas.boundingBox())!;
  await expect(page.getByRole("button", { name: "Maximize 3D" })).toHaveText(
    "↗",
  );
  await page.getByRole("button", { name: "Maximize 3D" }).click();
  await expect(page.getByRole("button", { name: "Restore 3D" })).toHaveText(
    "↙",
  );
  await expect
    .poll(async () => (await canvas.boundingBox())!.height)
    .toBeGreaterThan(initial.height + 100);
  const maximized = (await canvas.boundingBox())!;
  expect(maximized.height).toBeGreaterThan(650);
  await page.getByRole("button", { name: "Restore 3D" }).click();
  await expect
    .poll(async () => (await canvas.boundingBox())!.height)
    .toBeCloseTo(initial.height, 0);
});

test("maximized 3D controls can be collapsed and restored", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await open(page);
  await setupLayers(page, 2);
  await page.getByRole("button", { name: "Maximize 3D" }).click();
  const canvas = page.getByTestId("volume-canvas");
  const canvasBox = (await canvas.boundingBox())!;
  const initialWidth = canvasBox.width;
  const hideBox = (await page
    .getByRole("button", { name: "Hide controls" })
    .boundingBox())!;
  expect(hideBox.y).toBeGreaterThanOrEqual(canvasBox.y);
  expect(hideBox.x + hideBox.width).toBeLessThanOrEqual(
    canvasBox.x + canvasBox.width,
  );
  await page.getByRole("button", { name: "Hide controls" }).click();
  const showBox = (await page
    .getByRole("button", { name: "Show controls" })
    .boundingBox())!;
  expect(showBox.y).toBeGreaterThanOrEqual((await canvas.boundingBox())!.y);
  await expect(
    page.getByRole("complementary", { name: "Volume layers" }),
  ).toBeHidden();
  await expect
    .poll(async () => (await canvas.boundingBox())!.width)
    .toBeGreaterThan(initialWidth + 150);
  await page.getByRole("button", { name: "Show controls" }).click();
  await expect(
    page.getByRole("complementary", { name: "Volume layers" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Restore 3D" }).click();
  await expect(page.getByRole("button", { name: "Maximize 3D" })).toBeVisible();
});

test("tile controls and warnings stay concise when only one page is needed", async ({
  page,
}) => {
  await open(page);
  await setupLayers(page, 2);
  await command(page, {
    type: "set_depth_anchors",
    anchors: [
      { frame: 2, depth_nm: 20 },
      { frame: 4, depth_nm: 60 },
    ],
  });
  await command(page, {
    type: "set_depth_display",
    unit: "nm",
    coordinates: "depth",
  });
  await page.getByRole("switch", { name: "Tiles view" }).click();
  await expect(page.getByTestId("vtk-tile")).toHaveCount(2);
  await expect(page.getByRole("button", { name: "Next 3D page" })).toHaveCount(
    0,
  );
  await expect(page.locator(".vtk-tile small")).toHaveCount(0);
  await expect(
    page.getByText(/resampled.*profiles, measurements and exports/i),
  ).toHaveCount(1);
  const canvasBounds = (await page.getByTestId("volume-canvas").boundingBox())!;
  const statusBounds = (await page.getByTestId("volume-status").boundingBox())!;
  const warningBounds = (await page
    .getByText(/resampled.*profiles, measurements and exports/i)
    .boundingBox())!;
  expect(statusBounds.y).toBeGreaterThanOrEqual(
    canvasBounds.y + canvasBounds.height,
  );
  expect(warningBounds.y).toBeGreaterThanOrEqual(
    canvasBounds.y + canvasBounds.height,
  );
  expect(
    Math.abs(
      statusBounds.x + statusBounds.width - canvasBounds.x - canvasBounds.width,
    ),
  ).toBeLessThan(2);
  await expect(page.getByText(/shift-drag to pan/i).first()).toBeVisible();
});

test("shift-drag pans the vtk camera", async ({ page }) => {
  await open(page);
  await setupLayers(page, 1);
  const before = (await state(page)).spatial.camera.center;
  const box = (await page
    .getByTestId("volume-canvas")
    .locator("canvas")
    .boundingBox())!;
  await page.keyboard.down("Shift");
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.6, box.y + box.height * 0.55, {
    steps: 4,
  });
  await page.mouse.up();
  await page.keyboard.up("Shift");
  await expect
    .poll(async () => (await state(page)).spatial.camera.center)
    .not.toEqual(before);
});

test("one or two 3D tiles use the full available height", async ({ page }) => {
  await open(page);
  await setupLayers(page, 2);
  await page.getByRole("switch", { name: "Tiles view" }).click();
  await expect(page.getByTestId("vtk-tile")).toHaveCount(2);
  const container = page.getByTestId("volume-canvas");
  const height = (await container.boundingBox())!.height;
  for (const tile of await container.locator(".vtk-tile").all())
    expect((await tile.boundingBox())!.height).toBeGreaterThan(height * 0.9);
  await page.getByTestId("volume-layer").nth(1).getByRole("checkbox").uncheck();
  await expect(page.getByTestId("vtk-tile")).toHaveCount(1);
  const tile = (await container.locator(".vtk-tile").boundingBox())!;
  const bounds = (await container.boundingBox())!;
  expect(tile.height).toBeGreaterThan(bounds.height * 0.9);
  expect(tile.width).toBeGreaterThan(bounds.width * 0.9);
});

test("multi-signal overlay, tiles, styles and linked cameras", async ({
  page,
}) => {
  await open(page);
  await setupLayers(page);
  await page.getByRole("switch", { name: "Tiles view" }).click();
  await expect(page.getByTestId("vtk-tile")).toHaveCount(3);
  const first = page.getByTestId("volume-layer").first(),
    name = await first.getByTestId("volume-signal-name").textContent();
  await first.getByRole("button", { name: `3D settings for ${name}` }).click();
  await page
    .getByLabel(`3D colormap for ${name}`, { exact: true })
    .selectOption("Reds");
  await page.getByLabel(`3D opacity for ${name}`).fill("0.4");
  await page.getByLabel(`3D intensity threshold for ${name}`).fill("35");
  await page.getByRole("button", { name: "Close 3D signal settings" }).click();
  await expect
    .poll(async () => {
      const a = await state(page);
      return a.spatial.layers[0].percentile;
    })
    .toBe(35);
  const before = (await state(page)).spatial.layers[0].signal_id;
  const second = page.getByTestId("volume-layer").nth(1).getByRole("checkbox");
  await second.uncheck();
  await expect(page.getByTestId("volume-status")).toContainText("2 layers");
  await second.check();
  await expect(page.getByTestId("volume-status")).toContainText("3 layers");
  await page.getByText("Display settings", { exact: true }).click();
  await page
    .getByRole("switch", {
      name: "Shared numerical intensity scale",
      exact: true,
    })
    .click();
  await page.getByText("Display settings", { exact: true }).click();
  await page
    .getByRole("switch", { name: "Orthographic projection", exact: true })
    .click();
  await expect
    .poll(async () => (await state(page)).spatial.camera.projection)
    .toBe("orthographic");
  const oldEye = (await state(page)).spatial.camera.eye;
  const canvasBox = (await page.getByTestId("volume-canvas").boundingBox())!;
  await page.mouse.move(
    canvasBox.x + canvasBox.width * 0.3,
    canvasBox.y + canvasBox.height * 0.25,
  );
  await page.mouse.down();
  await page.mouse.move(
    canvasBox.x + canvasBox.width * 0.4,
    canvasBox.y + canvasBox.height * 0.35,
    { steps: 5 },
  );
  await page.mouse.up();
  await expect
    .poll(async () => (await state(page)).spatial.camera.eye)
    .not.toEqual(oldEye);
  await expect
    .poll(async () => {
      const cameras = await page
        .getByTestId("vtk-tile")
        .evaluateAll((els) => els.map((e) => e.getAttribute("data-camera")));
      return cameras.length === 3 && cameras.every((c) => c === cameras[0]);
    })
    .toBe(true);
  await page.getByRole("button", { name: "Maximize 3D", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Restore 3D", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("panel-profile")).not.toBeVisible();
  await expect(page.getByTestId("panel-ion")).not.toBeVisible();
  expect(before).toBe((await state(page)).spatial.layers[0].signal_id);
  await page.screenshot({
    path: test.info().outputPath("multi-signal-tiles.png"),
    fullPage: true,
  });
});
test("calibrated nonuniform geometry, missing coverage, original profile and saved restore", async ({
  page,
}) => {
  await open(page);
  await setupLayers(page, 2);
  await command(page, {
    type: "set_depth_anchors",
    anchors: [
      { frame: 2, depth_nm: 20 },
      { frame: 4, depth_nm: 60 },
    ],
  });
  await command(page, {
    type: "set_depth_display",
    unit: "nm",
    coordinates: "depth",
  });
  await expect(page.getByTestId("volume-status")).toContainText(
    "2 frames with unknown depth omitted",
  );
  await expect
    .poll(async () => (await volumeData(page)).z)
    .toEqual([0, 0.01, 0.02, 0.04, 0.06]);
  await expect(page.getByTestId("volume-canvas")).toHaveAttribute(
    "data-renderer",
    "vtk",
  );
  await page.getByText("Display settings", { exact: true }).click();
  await expect(page.getByLabel("Depth exaggeration")).toHaveValue("1");
  await page.getByText("Display settings", { exact: true }).click();
  await page.getByRole("button", { name: "Save as…", exact: true }).click();
  await page
    .getByLabel("Saved filename", { exact: true })
    .fill("spatial-state.h5");
  await page.getByRole("button", { name: "Save copy", exact: true }).click();
  await expect(page.getByText("Copy saved.", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Close save dialog", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Close analysis 1", exact: true })
    .click();
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "Saved files", exact: true }).click();
  await page
    .getByRole("button", { name: "◫ spatial-state.h5", exact: true })
    .dblclick();
  await expect(page.getByTestId("volume-status")).toContainText("2 layers");
  await expect(page.getByTestId("volume-status")).toContainText(
    "2 frames with unknown depth omitted",
  );
  await expect(
    page.getByTestId("volume-canvas").locator("canvas").first(),
  ).toBeVisible();
  await page.screenshot({
    path: test.info().outputPath("calibrated-overlay.png"),
    fullPage: true,
  });
});
test("six layers page four scenes, hide/show, independent cameras and depth ranges", async ({
  page,
}) => {
  await open(page);
  await setupLayers(page, 6);
  await page.getByRole("switch", { name: "Tiles view" }).click();
  await expect(page.getByTestId("vtk-tile")).toHaveCount(4);
  await page.getByRole("button", { name: "Next 3D page", exact: true }).click();
  await expect(page.getByTestId("vtk-tile")).toHaveCount(2);
  await page.getByText("Display settings", { exact: true }).click();
  await page.getByLabel("Linked cameras", { exact: true }).uncheck();
  await page.getByText("Display settings", { exact: true }).click();
  await page
    .getByRole("button", { name: "Previous 3D page", exact: true })
    .click();
  const beforeCameras = (await state(page)).spatial.layers.map(
    (l: any) => l.camera,
  );
  const tileBox = (await page
    .getByTestId("vtk-tile")
    .first()
    .locator("canvas")
    .boundingBox())!;
  await page.mouse.move(
    tileBox.x + tileBox.width * 0.45,
    tileBox.y + tileBox.height * 0.45,
  );
  await page.mouse.down();
  await page.mouse.move(
    tileBox.x + tileBox.width * 0.6,
    tileBox.y + tileBox.height * 0.55,
    { steps: 4 },
  );
  await page.mouse.up();
  await expect
    .poll(async () => (await state(page)).spatial.layers[0].camera)
    .not.toEqual(beforeCameras[0]);
  expect((await state(page)).spatial.layers[1].camera).toEqual(
    beforeCameras[1],
  );
  const first = page.getByTestId("volume-layer").first();
  await first.getByRole("checkbox").uncheck();
  await expect(page.getByTestId("volume-status")).toContainText("5 layers");
  await first.getByRole("checkbox").check();
  await expect(page.getByTestId("volume-status")).toContainText("6 layers");
  await expect(
    page.getByRole("button", { name: "Single frame", exact: true }),
  ).toHaveCount(0);
  await command(page, {
    type: "set_depth",
    depth: { mode: "window", first: 2, last: 4 },
  });
  await expect(page.getByTestId("volume-status")).toContainText("3 × 4 × 4");
  await expect(page.getByTestId("panel-profile")).not.toBeVisible();
});

test("removing a named layer and rendering partial coverage keeps 3D usable", async ({
  page,
}) => {
  await open(page);
  await setupLayers(page, 2);
  await expect(page.getByTestId("volume-canvas")).toHaveAttribute(
    "data-renderer",
    "vtk",
  );
  await expect
    .poll(
      async () =>
        (await volumeData(page)).layers[1].values.filter(
          (x: number | null) => x !== null,
        ).length,
    )
    .toBe(111);
  const a = await state(page),
    sid = a.spatial.layers[1].signal_id;
  await command(page, {
    type: "set_stored_coverage",
    signal_id: sid,
    frames: [2, 4],
  });
  await expect
    .poll(
      async () =>
        (await volumeData(page)).layers[1].values.filter(
          (x: number | null) => x !== null,
        ).length,
    )
    .toBe(48);
  await expect(
    page.getByText(/original preview samples as points/i),
  ).toBeVisible();
  await command(page, { type: "remove_signal", signal_id: sid });
  await expect(page.getByTestId("volume-status")).toContainText("1 layers");
  await expect(page.getByTestId("volume-layer")).toHaveCount(
    (await state(page)).signals.filter((s: any) => s.recipe).length,
  );
  await expect(
    page.getByTestId("volume-canvas").locator("canvas").first(),
  ).toBeVisible();
});

test("analysis view tabs sit beside the file heading and support keyboard navigation", async ({
  page,
}) => {
  await open(page);
  const tabs = page.getByRole("tablist", { name: "Analysis view" });
  const explore = tabs.getByRole("tab", { name: "Explore", exact: true });
  const volume = tabs.getByRole("tab", { name: "3D volume", exact: true });
  await expect(explore).toHaveAttribute("aria-selected", "true");
  const bounds = (await tabs.boundingBox())!;
  const signals = (await page
    .getByRole("region", { name: "Signals", exact: true })
    .boundingBox())!;
  const heading = (await page
    .getByRole("heading", { name: "spatial.h5", exact: true })
    .boundingBox())!;
  expect(bounds.y + bounds.height).toBeLessThanOrEqual(signals.y);
  expect(bounds.x).toBeGreaterThan(heading.x + heading.width);
  await explore.focus();
  await explore.press("ArrowRight");
  await expect(volume).toHaveAttribute("aria-selected", "true");
  await expect(volume).toBeFocused();
  await volume.press("Home");
  await expect(explore).toHaveAttribute("aria-selected", "true");
  await page.screenshot({
    path: test.info().outputPath("analysis-heading-tabs.png"),
  });
  await page.setViewportSize({ width: 700, height: 900 });
  const narrow = (await tabs.boundingBox())!;
  const narrowSignals = (await page
    .getByRole("region", { name: "Signals", exact: true })
    .boundingBox())!;
  expect(narrow.y + narrow.height).toBeLessThanOrEqual(narrowSignals.y);
  expect(narrow.x + narrow.width).toBeLessThanOrEqual(700);
});

test("polling and camera persistence retain the existing volume geometry", async ({
  page,
}) => {
  await open(page);
  await setupLayers(page, 1);
  await page.getByTestId("volume-canvas").evaluate((el: any) => {
    (window as any).initialVolumeGeometry =
      el.dataset.renderer === "vtk" ? el.querySelector("canvas") : el.data[0].x;
  });
  for (let i = 0; i < 3; i++)
    await page.waitForResponse(
      (r) =>
        /\/api\/v1\/analyses\/[^/]+$/.test(new URL(r.url()).pathname) &&
        r.request().method() === "GET",
    );
  expect(
    await page
      .getByTestId("volume-canvas")
      .evaluate(
        (el: any) =>
          (el.dataset.renderer === "vtk"
            ? el.querySelector("canvas")
            : el.data[0].x) === (window as any).initialVolumeGeometry,
      ),
  ).toBe(true);
  const before = (await state(page)).spatial.camera.eye;
  const box = (await page.getByTestId("volume-canvas").boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.45, box.y + box.height * 0.45);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.55, {
    steps: 5,
  });
  await page.mouse.up();
  await expect
    .poll(async () => (await state(page)).spatial.camera.eye)
    .not.toEqual(before);
  expect(
    await page
      .getByTestId("volume-canvas")
      .evaluate(
        (el: any) =>
          (el.dataset.renderer === "vtk"
            ? el.querySelector("canvas")
            : el.data[0].x) === (window as any).initialVolumeGeometry,
      ),
  ).toBe(true);
});

test("3D uses all frames or a range and does not inherit Explore single-frame navigation", async ({
  page,
}) => {
  await open(page);
  await page.getByRole("button", { name: "Single frame", exact: true }).click();
  await expect(
    page.getByRole("group", { name: "Frame navigation", exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "3D volume", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Single frame", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("group", { name: "Frame navigation", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "All frames", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Frame range", exact: true }).click();
  await expect(
    page.getByRole("form", { name: "Frame range", exact: true }),
  ).toBeVisible();
  const a = await state(page);
  await command(page, {
    type: "set_stored_coverage",
    signal_id: a.image_signal_id,
    frames: [2, 4],
  });
  await expect(page.getByLabel("First frame", { exact: true })).toHaveAttribute(
    "min",
    "2",
  );
  await expect(page.getByLabel("Last frame", { exact: true })).toHaveAttribute(
    "max",
    "4",
  );
  await page.getByRole("button", { name: "All frames", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Viewing depths", exact: true }),
  ).toContainText("Volume frames 0–6");
  await page.getByRole("tab", { name: "Explore", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Single frame", exact: true }),
  ).toBeVisible();
});
async function vtkColoredPixels(page: Page) {
  const png = await page
    .getByTestId("volume-canvas")
    .locator("canvas")
    .screenshot();
  return page.evaluate(async (bytes) => {
    const bitmap = await createImageBitmap(
      new Blob([new Uint8Array(bytes)], { type: "image/png" }),
    );
    const canvas = document.createElement("canvas");
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(bitmap, 0, 0);
    const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    let count = 0;
    for (let i = 0; i < pixels.length; i += 4)
      if (
        (pixels[i + 1] > 75 &&
          pixels[i + 1] > pixels[i] * 1.2 &&
          pixels[i + 1] > pixels[i + 2] * 1.05) ||
        (pixels[i] > 150 && pixels[i + 1] > 150 && pixels[i + 2] < 100)
      )
        count++;
    return count;
  }, Array.from(png));
}
test("vtk renders irregular XY preview blocks in frames mode with a warning", async ({
  page,
}) => {
  await open(page);
  await page.route("**/api/v1/analyses/*/volumes", async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    for (const axis of [payload.x, payload.y]) {
      if (axis.length < 3)
        throw new Error("Fixture needs at least three XY blocks");
      axis[axis.length - 1] =
        (axis[axis.length - 1] + axis[axis.length - 2]) / 2;
    }
    await route.fulfill({ response, json: payload });
  });
  await command(page, { type: "add_stored_signal", index: 1 });
  const a = await state(page);
  await command(page, {
    type: "set_spatial",
    spatial: {
      ...a.spatial,
      screen: "volume",
      layers: [{ signal_id: a.signals[0].id, percentile: 0 }],
    },
  });
  await expect(page.getByTestId("volume-canvas")).toHaveAttribute(
    "data-renderer",
    "vtk",
  );
  await expect(page.getByText(/nonuniform XY.*resampled/i)).toBeVisible();
  await expect.poll(() => vtkColoredPixels(page)).toBeGreaterThan(100);
});

test("vtk renders four complete overlay signals as volumes", async ({
  page,
}) => {
  await open(page);
  await page.route("**/api/v1/analyses/*/volumes", async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    for (const layer of payload.layers) {
      layer.values = layer.values.map((v: number | null) => v ?? 0);
      layer.coverage = layer.coverage.map(() => 1);
    }
    await route.fulfill({ response, json: payload });
  });
  await setupLayers(page, 4);
  await expect(page.getByTestId("volume-canvas")).toHaveAttribute(
    "data-volume-signals",
    "4",
  );
  await expect(
    page.getByText(/original preview samples as points/i),
  ).toHaveCount(0);
  for (let i = 0; i < 4; i++) {
    const layer = page.getByTestId("volume-layer").nth(i);
    const name = (await layer.getByTestId("volume-signal-name").textContent())!;
    await layer
      .getByRole("button", { name: `3D settings for ${name}` })
      .click();
    await page.getByLabel(`3D opacity for ${name}`).fill(i === 3 ? "1" : "0");
    await page
      .getByRole("button", { name: "Close 3D signal settings" })
      .click();
  }
  await expect.poll(() => vtkColoredPixels(page)).toBeGreaterThan(10);
});

test("vtk renders a complete signal and warns when calibrated depth is resampled", async ({
  page,
}) => {
  await open(page);
  await command(page, { type: "add_stored_signal", index: 1 });
  let a = await state(page);
  await command(page, {
    type: "set_spatial",
    spatial: {
      ...a.spatial,
      screen: "volume",
      layers: [{ signal_id: a.signals[0].id, percentile: 0 }],
    },
  });
  await expect(page.getByTestId("volume-canvas")).toHaveAttribute(
    "data-renderer",
    "vtk",
  );
  await command(page, {
    type: "set_depth_anchors",
    anchors: [
      { frame: 2, depth_nm: 20 },
      { frame: 4, depth_nm: 60 },
    ],
  });
  await command(page, {
    type: "set_depth_display",
    unit: "nm",
    coordinates: "depth",
  });
  await expect(page.getByTestId("volume-canvas")).toHaveAttribute(
    "data-renderer",
    "vtk",
  );
  await expect(page.getByText(/nonuniform depth.*resampled/i)).toBeVisible();
  await expect(page.getByText(/3D sampling is reduced/i)).toBeVisible();
  await expect(
    page.getByTestId("volume-canvas").locator("canvas"),
  ).toBeVisible();
  const name = (await page
    .getByTestId("volume-layer")
    .first()
    .getByTestId("volume-signal-name")
    .textContent())!;
  await page.getByRole("button", { name: `3D settings for ${name}` }).click();
  await page.getByLabel(`3D opacity for ${name}`).fill("0.8");
  await expect.poll(() => vtkColoredPixels(page)).toBeGreaterThan(100);
  await page
    .getByRole("switch", { name: "Orthographic projection", exact: true })
    .click();
  await expect
    .poll(async () => (await state(page)).spatial.camera.projection)
    .toBe("orthographic");
  await expect.poll(() => vtkColoredPixels(page)).toBeGreaterThan(100);
  await expect(page.getByTestId("volume-canvas")).toHaveAttribute(
    "data-renderer",
    "vtk",
  );
  const before = (await state(page)).spatial.camera.eye;
  const box = (await page
    .getByTestId("volume-canvas")
    .locator("canvas")
    .boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.6, box.y + box.height * 0.55, {
    steps: 5,
  });
  await page.mouse.up();
  await expect
    .poll(async () => (await state(page)).spatial.camera.eye)
    .not.toEqual(before);
  const savedCamera = (await state(page)).spatial.camera;
  await page.getByLabel(`Reverse 3D colormap for ${name}`).check();
  await expect
    .poll(async () => (await state(page)).spatial.layers[0].colorscale_reversed)
    .toBe(true);
  await page.getByRole("button", { name: "Save as…", exact: true }).click();
  await page
    .getByLabel("Saved filename", { exact: true })
    .fill("vtk-camera-state.h5");
  await page.getByRole("button", { name: "Save copy", exact: true }).click();
  await expect(page.getByText("Copy saved.", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Close save dialog", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Close analysis 1", exact: true })
    .click();
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "Saved files", exact: true }).click();
  await page
    .getByRole("button", { name: "◫ vtk-camera-state.h5", exact: true })
    .dblclick();
  await expect(page.getByTestId("volume-canvas")).toHaveAttribute(
    "data-renderer",
    "vtk",
  );
  await expect
    .poll(async () => (await state(page)).spatial.camera)
    .toEqual(savedCamera);
  await page.getByRole("button", { name: `3D settings for ${name}` }).click();
  await expect(
    page.getByLabel(`Reverse 3D colormap for ${name}`),
  ).toBeChecked();
});
test("vtk overlay remains usable when a signal is hidden or shown", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await open(page);
  await command(page, { type: "add_stored_signal", index: 1 });
  await command(page, { type: "add_stored_signal", index: 2 });
  const a = await state(page);
  await command(page, {
    type: "set_spatial",
    spatial: {
      ...a.spatial,
      screen: "volume",
      layers: a.signals.map((s: any) => ({ signal_id: s.id, percentile: 0 })),
    },
  });
  await expect(page.getByTestId("volume-canvas")).toHaveAttribute(
    "data-renderer",
    "vtk",
  );
  const layer = page.getByTestId("volume-layer").first();
  const toggle = layer.getByRole("checkbox");
  await toggle.uncheck();
  await expect(page.getByTestId("volume-status")).toContainText(
    `${a.signals.length - 1} layers`,
  );
  await expect(page.getByTestId("volume-canvas")).toHaveAttribute(
    "data-renderer",
    "vtk",
  );
  await toggle.check();
  await expect(page.getByTestId("volume-status")).toContainText(
    `${a.signals.length} layers`,
  );
  await expect(page.getByTestId("volume-canvas")).toHaveAttribute(
    "data-renderer",
    "vtk",
  );
  expect(errors).toEqual([]);
});

test("vtk renders points when a signal threshold reaches the maximum", async ({
  page,
}) => {
  await open(page);
  await command(page, { type: "add_stored_signal", index: 1 });
  const a = await state(page);
  await command(page, {
    type: "set_spatial",
    spatial: {
      ...a.spatial,
      screen: "volume",
      layers: [{ signal_id: a.signals[0].id, percentile: 100 }],
    },
  });
  await expect(
    page.getByTestId("volume-canvas").locator("canvas").first(),
  ).toBeVisible();
  await expect(page.getByTestId("volume-canvas")).toHaveAttribute(
    "data-renderer",
    "vtk",
  );
  await expect(
    page.getByText(/original preview samples as points/i),
  ).toBeVisible();
  const layerName = (await page
    .getByTestId("volume-layer")
    .first()
    .getByTestId("volume-signal-name")
    .textContent())!;
  await page
    .getByRole("button", { name: `3D settings for ${layerName}` })
    .click();
  await page.getByLabel(`3D opacity for ${layerName}`).fill("1");
  await expect.poll(() => vtkColoredPixels(page)).toBeGreaterThan(0);
});

test("vtk colormap changes update the volume and its legend", async ({
  page,
}) => {
  await open(page);
  await command(page, { type: "add_stored_signal", index: 1 });
  const a = await state(page);
  await command(page, {
    type: "set_spatial",
    spatial: {
      ...a.spatial,
      screen: "volume",
      layers: [
        {
          signal_id: a.signals[0].id,
          percentile: 0,
          opacity: 0.8,
          colorscale: "Reds",
        },
      ],
    },
  });
  const canvas = page.getByTestId("volume-canvas").locator("canvas");
  await expect(canvas).toBeVisible();
  const name = a.signals[0].name;
  const ramp = page.locator(".vtk-volume-ramp").first();
  const redsRamp = await ramp.evaluate(
    (e) => getComputedStyle(e).backgroundImage,
  );
  const reds = await canvas.screenshot();
  await page.getByRole("button", { name: `3D settings for ${name}` }).click();
  await page
    .getByLabel(`3D colormap for ${name}`, { exact: true })
    .selectOption("Purples");
  await page.getByRole("button", { name: "Close 3D signal settings" }).click();
  await expect
    .poll(() => ramp.evaluate((e) => getComputedStyle(e).backgroundImage))
    .not.toBe(redsRamp);
  await expect
    .poll(async () => (await canvas.screenshot()).equals(reds))
    .toBe(false);
  const purplesRamp = await ramp.evaluate(
    (e) => getComputedStyle(e).backgroundImage,
  );
  const purples = await canvas.screenshot();
  await page.getByRole("button", { name: `3D settings for ${name}` }).click();
  await page
    .getByLabel(`3D colormap for ${name}`, { exact: true })
    .selectOption("Plasma");
  await page.getByRole("button", { name: "Close 3D signal settings" }).click();
  await expect
    .poll(() => ramp.evaluate((e) => getComputedStyle(e).backgroundImage))
    .not.toBe(purplesRamp);
  await expect
    .poll(async () => (await canvas.screenshot()).equals(purples))
    .toBe(false);
  const plasmaRamp = await ramp.evaluate(
    (e) => getComputedStyle(e).backgroundImage,
  );
  const plasma = await canvas.screenshot();
  await page.getByRole("button", { name: `3D settings for ${name}` }).click();
  await page.getByLabel(`Reverse 3D colormap for ${name}`).check();
  await page.getByRole("button", { name: "Close 3D signal settings" }).click();
  await expect
    .poll(() => ramp.evaluate((e) => getComputedStyle(e).backgroundImage))
    .not.toBe(plasmaRamp);
  await expect
    .poll(async () => (await canvas.screenshot()).equals(plasma))
    .toBe(false);
});

test("vtk applies a colormap to the third overlay volume component", async ({
  page,
}) => {
  await open(page);
  await page.route("**/api/v1/analyses/*/volumes", async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    for (const layer of payload.layers) {
      layer.values = layer.values.map((v: number | null) => v ?? 0);
      layer.coverage = layer.coverage.map(() => 1);
    }
    await route.fulfill({ response, json: payload });
  });
  await setupLayers(page, 3);
  const a = await state(page);
  await command(page, {
    type: "set_spatial",
    spatial: {
      ...a.spatial,
      layers: a.spatial.layers.map((l: any, i: number) => ({
        ...l,
        opacity: i === 2 ? 1 : 0,
        colorscale: "Reds",
      })),
    },
  });
  const canvas = page.getByTestId("volume-canvas").locator("canvas");
  await expect(canvas).toBeVisible();
  const name = a.signals[2].name;
  const reds = await canvas.screenshot();
  await page.getByRole("button", { name: `3D settings for ${name}` }).click();
  await page
    .getByLabel(`3D colormap for ${name}`, { exact: true })
    .selectOption("Plasma");
  await page.getByRole("button", { name: "Close 3D signal settings" }).click();
  await expect
    .poll(async () => (await canvas.screenshot()).equals(reds))
    .toBe(false);
});

test("transparent overlay components do not tint another signal", async ({
  page,
}) => {
  await open(page);
  await page.route("**/api/v1/analyses/*/volumes", async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    for (const layer of payload.layers) {
      layer.values = layer.values.map((v: number | null) => v ?? 0);
      layer.coverage = layer.coverage.map(() => 1);
    }
    await route.fulfill({ response, json: payload });
  });
  await setupLayers(page, 3);
  const a = await state(page);
  await command(page, {
    type: "set_spatial",
    spatial: {
      ...a.spatial,
      layers: a.spatial.layers.map((l: any, i: number) => ({
        ...l,
        opacity: i === 2 ? 1 : 0,
        colorscale: i === 2 ? "Reds" : "Blues",
      })),
    },
  });
  const canvas = page.getByTestId("volume-canvas").locator("canvas");
  await expect(canvas).toBeVisible();
  const ramp = page.locator(".vtk-volume-ramp").first();
  await expect(ramp).toHaveAttribute("style", /rgb\(5, 10, 172\)/);
  const before = await canvas.screenshot();
  const redPixels = await page.evaluate(async (bytes) => {
    const bitmap = await createImageBitmap(
      new Blob([new Uint8Array(bytes)], { type: "image/png" }),
    );
    const c = document.createElement("canvas");
    c.width = bitmap.width;
    c.height = bitmap.height;
    const ctx = c.getContext("2d")!;
    ctx.drawImage(bitmap, 0, 0);
    const pixels = ctx.getImageData(0, 0, c.width, c.height).data;
    let count = 0;
    for (let i = 0; i < pixels.length; i += 4)
      if (
        pixels[i] > 80 &&
        pixels[i] > pixels[i + 1] * 1.3 &&
        pixels[i] > pixels[i + 2] * 1.3
      )
        count++;
    return count;
  }, Array.from(before));
  expect(redPixels).toBeGreaterThan(100);
  const originalRamp = await ramp.evaluate(
    (e) => getComputedStyle(e).backgroundImage,
  );
  const current = await state(page);
  await command(page, {
    type: "set_spatial",
    spatial: {
      ...current.spatial,
      layers: current.spatial.layers.map((l: any, i: number) => ({
        ...l,
        colorscale: i === 2 ? "Reds" : "Greens",
      })),
    },
  });
  await expect
    .poll(() => ramp.evaluate((e) => getComputedStyle(e).backgroundImage))
    .not.toBe(originalRamp);
  const after = await canvas.screenshot();
  const meanDifference = await page.evaluate(
    async ([a, b]) => {
      const decode = async (bytes: number[]) => {
        const bitmap = await createImageBitmap(
          new Blob([new Uint8Array(bytes)], { type: "image/png" }),
        );
        const c = document.createElement("canvas");
        c.width = bitmap.width;
        c.height = bitmap.height;
        const ctx = c.getContext("2d")!;
        ctx.drawImage(bitmap, 0, 0);
        return ctx.getImageData(0, 0, c.width, c.height).data;
      };
      const left = await decode(a),
        right = await decode(b);
      let difference = 0,
        count = 0;
      for (let i = 0; i < left.length; i += 4) {
        const chroma = (pixels: Uint8ClampedArray) =>
          Math.max(pixels[i], pixels[i + 1], pixels[i + 2]) -
          Math.min(pixels[i], pixels[i + 1], pixels[i + 2]);
        if (Math.max(chroma(left), chroma(right)) < 30) continue;
        difference +=
          Math.abs(left[i] - right[i]) +
          Math.abs(left[i + 1] - right[i + 1]) +
          Math.abs(left[i + 2] - right[i + 2]);
        count += 3;
      }
      return difference / count;
    },
    [Array.from(before), Array.from(after)],
  );
  expect(meanDifference).toBeLessThan(1);
});

test("preset views and fixed rotations update saved cameras", async ({
  page,
}) => {
  await open(page);
  await setupLayers(page, 2);
  await page.getByLabel("Camera view").selectOption("top");
  await expect
    .poll(async () => (await state(page)).spatial.camera.eye.z)
    .toBeGreaterThan(0);
  await expect
    .poll(async () => (await state(page)).spatial.camera.eye.x)
    .toBe(0);
  await page.getByRole("button", { name: "Rotate clockwise 15°" }).click();
  await expect
    .poll(async () => Math.abs((await state(page)).spatial.camera.up.x))
    .toBeGreaterThan(0.1);
  await page
    .getByRole("button", { name: "Rotate counterclockwise 15°" })
    .click();
  await expect
    .poll(async () => Math.abs((await state(page)).spatial.camera.up.x))
    .toBeLessThan(0.001);
  await page.getByRole("button", { name: "Rotate right 15°" }).click();
  await expect
    .poll(async () => Math.abs((await state(page)).spatial.camera.eye.x))
    .toBeGreaterThan(0.1);
});

test("3D controls are grouped in the sidebar while maximize stays above the canvas", async ({
  page,
}) => {
  await open(page);
  await setupLayers(page, 2);
  const sidebar = page.getByRole("complementary", { name: "3D controls" });
  await expect(
    sidebar.getByRole("switch", { name: "Tiles view" }),
  ).toBeVisible();
  await expect(sidebar.getByLabel("Camera view")).toBeVisible();
  await expect(
    sidebar.getByRole("button", { name: "Rotate up 15°" }),
  ).toBeVisible();
  await sidebar.getByText("Display settings", { exact: true }).click();
  await expect(
    sidebar.getByRole("switch", { name: "Shared numerical intensity scale" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Maximize 3D" })).toBeVisible();
});

test("arrow keys rotate the 3D camera but leave form controls alone", async ({
  page,
}) => {
  await open(page);
  await setupLayers(page, 1);
  await page.getByLabel("Camera view").selectOption("front");
  await expect
    .poll(async () => (await state(page)).spatial.camera.eye.x)
    .toBe(0);
  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("ArrowRight");
  await expect
    .poll(async () => Math.abs((await state(page)).spatial.camera.eye.x))
    .toBeGreaterThan(0.1);
  const camera = (await state(page)).spatial.camera;
  await page.getByText("Display settings", { exact: true }).click();
  await page.getByLabel("Frame stretch").focus();
  await page.keyboard.press("ArrowUp");
  await expect
    .poll(async () => (await state(page)).spatial.camera)
    .toEqual(camera);
});

test("exports the 3D viewer as a PNG", async ({ page }) => {
  await open(page);
  await setupLayers(page, 2);
  const viewer = page.getByTestId("volume-canvas");
  const save = page.getByRole("button", { name: "Export 3D PNG" });
  await expect(save).toBeVisible();
  const box = (await viewer.boundingBox())!;
  const button = (await save.boundingBox())!;
  expect(button.x).toBeGreaterThan(box.x);
  expect(button.y).toBeGreaterThanOrEqual(box.y);
  expect(button.x + button.width).toBeLessThanOrEqual(box.x + box.width);
  const downloadPromise = page.waitForEvent("download");
  await save.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("tofscope-3d.png");
  const png = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of png!) chunks.push(chunk as Buffer);
  const bytes = Buffer.concat(chunks);
  expect(bytes.subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a");
  expect(bytes.readUInt32BE(16)).toBeGreaterThan(100);
  expect(bytes.readUInt32BE(20)).toBeGreaterThan(100);
  await page.getByRole("switch", { name: "Tiles view" }).click();
  await expect(page.getByTestId("vtk-tile")).toHaveCount(2);
  const tiledDownload = page.waitForEvent("download");
  await save.click();
  expect((await tiledDownload).suggestedFilename()).toBe("tofscope-3d.png");
});
