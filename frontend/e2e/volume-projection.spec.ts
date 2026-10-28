import { test, expect, type Page } from "@playwright/test";
async function coloredPixels(page: Page) {
  const png = await page.locator("#plot").screenshot();
  return page.evaluate(async (bytes) => {
    const bitmap = await createImageBitmap(
      new Blob([new Uint8Array(bytes)], { type: "image/png" }),
    );
    const canvas = document.createElement("canvas");
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(bitmap, 0, 0);
    const pixels = ctx.getImageData(200, 150, 400, 350).data;
    let count = 0;
    for (let i = 0; i < pixels.length; i += 4)
      if (pixels[i + 1] > pixels[i] * 1.2 && pixels[i + 1] > 75) count++;
    return count;
  }, Array.from(png));
}
test("volume remains visible when switching projection", async ({ page }) => {
  await page.goto("/evaluation/index.html");
  await page.evaluate(async () => {
    const { mountSpatial, defaultLayer, defaultCamera } = await import(
      "/src/volumes/spatialRenderer.ts" as string
    );
    document.body.innerHTML =
      '<div id="plot" style="width:900px;height:650px"></div>';
    const n = 20,
      axis = Array.from({ length: n }, (_, i) => i);
    const values = Array.from({ length: n * n * n }, (_, i) => {
      const x = (i % n) - 9.5,
        y = (Math.floor(i / n) % n) - 9.5,
        z = Math.floor(i / n / n) - 9.5;
      return Math.exp(-(x * x + y * y + z * z) / 60);
    });
    const data: any = {
      dataset_generation: "1",
      x: axis,
      y: axis,
      z: axis,
      extent: [20, 20, 20],
      block_edges: [axis, axis, axis],
      xy_unit: "pixel",
      z_unit: "frame",
      physical_aspect: false,
      layers: [{ signal_id: "a", label: "A", values }],
    };
    const state: any = {
      layers: [{ ...defaultLayer("a"), percentile: 0, opacity: 0.5 }],
      mode: "overlay",
      quality: "Detailed",
      scale: "independent",
      linked: true,
      camera: defaultCamera,
      solo: null,
      page: 0,
      frame_stretch: 1.2,
      depth_exaggeration: 1,
    };
    (window as any).debugRenderer = await mountSpatial(
      document.getElementById("plot")!,
      () => {},
    );
    (window as any).debugData = data;
    (window as any).debugState = state;
    await (window as any).debugRenderer.update(data, state);
  });
  expect(await coloredPixels(page)).toBeGreaterThan(1000);
  await page.evaluate(async () => {
    const s = (window as any).debugState;
    await (window as any).debugRenderer.update((window as any).debugData, {
      ...s,
      camera: { ...s.camera, projection: "orthographic" },
    });
  });
  expect(await coloredPixels(page)).toBeGreaterThan(1000);
  await page.evaluate(async () => {
    const s = (window as any).debugState;
    await (window as any).debugRenderer.update((window as any).debugData, s);
  });
  expect(await coloredPixels(page)).toBeGreaterThan(1000);
});
