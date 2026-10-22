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
    await renderer.update(data, state);
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
