import { test, expect, type Page } from "@playwright/test";
async function coloredPixels(page: Page) {
  const png = await page.locator("#plot canvas").screenshot();
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
      if (pixels[i + 1] > pixels[i] * 1.2 && pixels[i + 1] > 75) count++;
    return count;
  }, Array.from(png));
}
test("vtk volume remains visible when switching projection", async ({
  page,
}) => {
  await page.goto("/evaluation/index.html");
  await page.evaluate(async () => {
    const { React, createRoot } = await import(
      "/evaluation/vtkReactProbe.ts" as string
    );
    const { VtkScene } = await import("/src/volumes/VtkScene.tsx" as string);
    const { defaultLayer, defaultCamera } = await import(
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
      xy_unit: "pixel",
      z_unit: "frame",
      physical_aspect: false,
      layers: [
        { signal_id: "a", label: "A", values, coverage: values.map(() => 1) },
      ],
    };
    const view: any = {
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
    const root = createRoot(document.getElementById("plot")!);
    (window as any).renderProjection = (projection: string) =>
      root.render(
        React.createElement(VtkScene, {
          data,
          source: data,
          view: { ...view, camera: { ...view.camera, projection } },
          log: false,
          onCamera: () => {},
          onError: (message: string) => {
            throw Error(message);
          },
        }),
      );
    (window as any).renderProjection("perspective");
  });
  await expect(page.locator("#plot canvas")).toBeVisible();
  await expect.poll(() => coloredPixels(page)).toBeGreaterThan(1000);
  await page.evaluate(() => (window as any).renderProjection("orthographic"));
  await expect(page.getByTestId("volume-canvas")).toHaveAttribute(
    "data-camera",
    /orthographic/,
  );
  await expect.poll(() => coloredPixels(page)).toBeGreaterThan(1000);
  await page.evaluate(() => (window as any).renderProjection("perspective"));
  await expect(page.getByTestId("volume-canvas")).toHaveAttribute(
    "data-camera",
    /perspective/,
  );
  await expect.poll(() => coloredPixels(page)).toBeGreaterThan(1000);
});
