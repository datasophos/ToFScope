import { test, expect, type Page } from "@playwright/test";
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
test("multi-signal overlay, tiles, Solo, styles, camera and full-resolution profile", async ({
  page,
}) => {
  await open(page);
  await setupLayers(page);
  await page.getByLabel("3D view mode").selectOption("tiles");
  await expect
    .poll(async () =>
      page.getByTestId("volume-canvas").evaluate((e: any) => e.data?.length),
    )
    .toBe(3);
  const first = page.getByTestId("volume-layer").first(),
    name = await first.locator("legend").textContent();
  await first.getByRole("combobox").selectOption("Reds");
  await first.getByLabel(`3D opacity for ${name}`).fill("0.4");
  await first.getByLabel(`3D percentile for ${name}`).fill("35");
  await expect
    .poll(async () => {
      const a = await state(page);
      return a.spatial.layers[0].percentile;
    })
    .toBe(35);
  const before = await page
    .getByTestId("volume-canvas")
    .evaluate((e: any) => e.data[0].uid);
  await first
    .getByRole("button", { name: `Solo ${name}`, exact: true })
    .click();
  await expect(page.getByTestId("volume-status")).toContainText("1 layers");
  await first
    .getByRole("button", { name: `Solo ${name}`, exact: true })
    .click();
  await expect(page.getByTestId("volume-status")).toContainText("3 layers");
  await page.getByLabel("3D intensity scale").selectOption("shared");
  await page
    .getByRole("button", { name: "Orthographic camera", exact: true })
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
    .poll(async () =>
      page
        .getByTestId("volume-canvas")
        .evaluate(
          (e: any) =>
            JSON.stringify(e.layout.scene.camera) ===
            JSON.stringify(e.layout.scene2.camera),
        ),
    )
    .toBe(true);
  await page.getByRole("button", { name: "Maximize 3D", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Restore 3D", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("panel-profile")).toBeVisible();
  expect(
    (await page
      .getByTestId("panel-profile")
      .locator("canvas")
      .first()
      .boundingBox())!.height,
  ).toBeGreaterThan(150);
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
    .poll(async () =>
      page
        .getByTestId("volume-canvas")
        .evaluate((e: any) => [...new Set(e.data[0].z)]),
    )
    .toEqual([0, 0.01, 0.02, 0.04, 0.06]);
  await expect(page.getByLabel("Depth exaggeration")).toHaveValue("1");
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
test("six layers page four scenes, hide/show, independent cameras and single-frame points", async ({
  page,
}) => {
  await open(page);
  await setupLayers(page, 6);
  await page.getByLabel("3D view mode").selectOption("tiles");
  await expect
    .poll(async () =>
      page.getByTestId("volume-canvas").evaluate((e: any) => e.data?.length),
    )
    .toBe(4);
  await page.getByRole("button", { name: "Next 3D page", exact: true }).click();
  await expect
    .poll(async () =>
      page.getByTestId("volume-canvas").evaluate((e: any) => e.data?.length),
    )
    .toBe(2);
  await page.getByLabel("Linked cameras", { exact: true }).uncheck();
  await page
    .getByRole("button", { name: "Previous 3D page", exact: true })
    .click();
  const first = page.getByTestId("volume-layer").first();
  await first.getByRole("checkbox").uncheck();
  await expect(page.getByTestId("volume-status")).toContainText("5 layers");
  await first.getByRole("checkbox").check();
  await expect(page.getByTestId("volume-status")).toContainText("6 layers");
  await command(page, {
    type: "set_depth",
    depth: { mode: "frame", index: 2 },
  });
  await expect
    .poll(async () =>
      page
        .getByTestId("volume-canvas")
        .evaluate((e: any) => e.data?.map((t: any) => t.type)),
    )
    .toEqual(["scatter3d", "scatter3d", "scatter3d", "scatter3d"]);
  await expect(page.getByTestId("panel-profile")).toBeVisible();
});

test("removing a named layer and rendering partial coverage keeps 3D usable", async ({
  page,
}) => {
  await open(page);
  await setupLayers(page, 2);
  await expect
    .poll(async () =>
      page.getByTestId("volume-canvas").evaluate((e: any) => e.data?.[1]?.type),
    )
    .toBe("scatter3d");
  await expect
    .poll(async () =>
      page
        .getByTestId("volume-canvas")
        .evaluate((e: any) => e.data?.[1]?.marker?.color?.length),
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
    .poll(async () =>
      page
        .getByTestId("volume-canvas")
        .evaluate((e: any) => e.data?.[1]?.z?.length),
    )
    .toBe(48);
  await command(page, { type: "remove_signal", signal_id: sid });
  await expect(page.getByTestId("volume-status")).toContainText("1 layers");
  await expect(page.getByTestId("volume-layer")).toHaveCount(1);
  await expect(
    page.getByTestId("volume-canvas").locator("canvas").first(),
  ).toBeVisible();
});
