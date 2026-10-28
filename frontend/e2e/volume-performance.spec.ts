import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
test("optional read-only acquisition renderer benchmark", async ({ page }) => {
  test.skip(
    !process.env.TOFSCOPE_VOLUME_BENCHMARK,
    "Set payload path after read-only presenter qualification.",
  );
  test.setTimeout(120000);
  const data = JSON.parse(
    readFileSync(process.env.TOFSCOPE_VOLUME_BENCHMARK!, "utf8"),
  );
  await page.goto("/evaluation/index.html");
  const result = await page.evaluate(async (data) => {
    const { mountSpatial, defaultLayer, defaultCamera } = await import(
      "/src/volumes/spatialRenderer.ts" as string
    );
    document.body.innerHTML =
      '<div id="benchmark" style="width:1000px;height:700px"></div>';
    const el = document.getElementById("benchmark")!;
    const state: any = {
      screen: "volume",
      layers: data.layers.map((l: any) => defaultLayer(l.signal_id)),
      mode: "overlay",
      quality: "Fast",
      scale: "independent",
      linked: true,
      camera: defaultCamera,
      solo: null,
      page: 0,
      frame_stretch: 1.2,
      depth_exaggeration: 1,
    };
    const start = performance.now();
    const renderer = await mountSpatial(el, () => {});
    await renderer.update(data, state, { log: true });
    const ready = performance.now() - start;
    const { Plotly } = await import(
      "/evaluation/spatialBenchmark.ts" as string
    );
    const times: number[] = [];
    for (let i = 0; i < 30; i++) {
      const t = performance.now();
      await Plotly.relayout(el, {
        "scene.camera.eye": { x: 1.3 + i / 100, y: 1.3, z: 1.3 },
      });
      await new Promise(requestAnimationFrame);
      times.push(performance.now() - t);
    }
    (window as any).benchmarkRenderer = renderer;
    return {
      readyMs: ready,
      cameraMs: times.sort((a, b) => a - b),
      traceTypes: (el as any).data.map((t: any) => t.type),
      heapBytes: (performance as any).memory?.usedJSHeapSize ?? null,
    };
  }, data);
  expect(result.traceTypes).toEqual(["volume", "volume", "volume"]);
  const el = page.locator("#benchmark"),
    box = (await el.boundingBox())!;
  const drags: number[] = [];
  for (let i = 0; i < 30; i++) {
    const start = Date.now();
    await page.mouse.move(box.x + 450, box.y + 320);
    await page.mouse.down();
    await page.mouse.move(box.x + 470, box.y + 330);
    await page.mouse.up();
    await page.evaluate(() => new Promise(requestAnimationFrame));
    drags.push(Date.now() - start);
  }
  console.log(
    JSON.stringify({ ...result, dragMs: drags.sort((a, b) => a - b) }),
  );
  await page.screenshot({
    path: test.info().outputPath("real-acquisition-overlay.png"),
  });
  await page.evaluate(() => (window as any).benchmarkRenderer.destroy());
});

test("optional real all-depth payload through the full application camera lifecycle", async ({
  page,
}) => {
  test.skip(
    !process.env.TOFSCOPE_VOLUME_BENCHMARK,
    "Set a read-only real-acquisition payload.",
  );
  test.setTimeout(120000);
  const payload = JSON.parse(
    readFileSync(process.env.TOFSCOPE_VOLUME_BENCHMARK!, "utf8"),
  );
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `volume-ui-benchmark-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  await expect(page.getByTestId("analysis")).toBeVisible();
  await page.route("**/api/v1/analyses/*/volumes", async (route) => {
    const source = await route.fetch(),
      current = await source.json();
    await route.fulfill({
      json: {
        ...payload,
        analysis_id: current.analysis_id,
        revision: current.revision,
        dataset_generation: current.dataset_generation,
        layers: current.layers.map((l: any, i: number) => ({
          ...payload.layers[i],
          signal_id: l.signal_id,
          label: l.label,
        })),
      },
    });
  });
  await page.evaluate(async () => {
    const session = await (await fetch("/api/v1/auth/session")).json();
    const command = async (command: any) => {
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
          command,
        }),
      });
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    };
    await command({ type: "add_stored_signal", index: 0 });
    const a = await command({
      type: "add_stored_signal",
      index: 1,
      duplicate: true,
    });
    await command({
      type: "set_spatial",
      spatial: {
        ...a.spatial,
        screen: "volume",
        layers: a.signals.map((s: any) => ({ signal_id: s.id })),
      },
    });
  });
  const canvas = page.getByTestId("volume-canvas");
  await expect(canvas.locator("canvas").first()).toBeVisible();
  await expect
    .poll(async () => canvas.evaluate((el: any) => el.data?.length))
    .toBe(3);
  await canvas.evaluate(
    (el: any) => ((window as any).originalVolumeX = el.data[0].x),
  );
  const box = (await canvas.boundingBox())!,
    times: number[] = [];
  for (let i = 0; i < 30; i++) {
    const saved = page.waitForResponse(
      (r) =>
        r.url().endsWith("/commands") &&
        r.request().method() === "POST" &&
        r.request().postDataJSON()?.command.type === "set_spatial",
    );
    const start = Date.now();
    await page.mouse.move(box.x + box.width * 0.45, box.y + box.height * 0.45);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.55, {
      steps: 3,
    });
    await page.mouse.up();
    await saved;
    await page.evaluate(() => new Promise(requestAnimationFrame));
    times.push(Date.now() - start);
  }
  for (let i = 0; i < 3; i++)
    await page.waitForResponse(
      (r) =>
        /\/api\/v1\/analyses\/[^/]+$/.test(new URL(r.url()).pathname) &&
        r.request().method() === "GET",
    );
  expect(
    await canvas.evaluate(
      (el: any) => el.data[0].x === (window as any).originalVolumeX,
    ),
  ).toBe(true);
  console.log(
    JSON.stringify({
      fullApplication: true,
      visibleVoxels: payload.total_voxels,
      dragAndSaveMs: times.sort((a, b) => a - b),
      geometryRetained: true,
    }),
  );
  await page.screenshot({
    path: test.info().outputPath("full-app-real-volume.png"),
  });
});
