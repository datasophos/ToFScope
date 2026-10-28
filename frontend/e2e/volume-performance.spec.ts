import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
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
  await expect.poll(() => canvas.getAttribute("data-renderer")).toBe("vtk");
  await canvas.evaluate((el) => {
    (window as any).originalVolumeGeometry = el.querySelector("canvas");
  });
  const box = (await canvas.boundingBox())!,
    times: number[] = [];
  const initialCamera = await page.evaluate(async () => {
    const [a] = await (await fetch("/api/v1/analyses")).json();
    return a.spatial.camera;
  });
  let lastCamera: any;
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
    const response = await saved;
    expect(response.ok()).toBe(true);
    lastCamera = response.request().postDataJSON().command.spatial.camera;
    await page.evaluate(() => new Promise(requestAnimationFrame));
    times.push(Date.now() - start);
  }
  for (let i = 0; i < 3; i++)
    await page.waitForResponse(
      (r) =>
        /\/api\/v1\/analyses\/[^/]+$/.test(new URL(r.url()).pathname) &&
        r.request().method() === "GET",
    );
  const persistedCamera = await page.evaluate(async () => {
    const [a] = await (await fetch("/api/v1/analyses")).json();
    return a.spatial.camera;
  });
  expect(lastCamera).not.toEqual(initialCamera);
  expect(persistedCamera).toEqual(lastCamera);
  expect(
    await canvas.evaluate(
      (el: any) =>
        el.querySelector("canvas") === (window as any).originalVolumeGeometry,
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
