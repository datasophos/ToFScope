import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
test("vtk scene renders a nonuniform real preview and persists camera changes", async ({
  page,
}) => {
  page.on("pageerror", (e) => console.log("PAGEERROR", e.message, e.stack));
  test.skip(
    !process.env.TOFSCOPE_VOLUME_BENCHMARK,
    "Set read-only preview payload",
  );
  const data = JSON.parse(
    readFileSync(process.env.TOFSCOPE_VOLUME_BENCHMARK!, "utf8"),
  );
  await page.goto("/evaluation/index.html");
  const result = await page.evaluate(async (data) => {
    const { React, createRoot } = await import(
      "/evaluation/vtkReactProbe.ts" as string
    );
    const { VtkScene } = await import("/src/volumes/VtkScene.tsx" as string);
    const { prepareVtkPreview } = await import(
      "/src/volumes/vtkPreview.ts" as string
    );
    const { defaultLayer, defaultCamera } = await import(
      "/src/volumes/spatialRenderer.ts" as string
    );
    const preview = prepareVtkPreview(data);
    if (preview.kind !== "vtk") throw Error(preview.reason);
    document.body.innerHTML =
      '<div id="root" style="width:800px;height:600px"></div>';
    const view: any = {
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
    const root = createRoot(document.getElementById("root")!);
    root.render(
      React.createElement(VtkScene, {
        data: preview.data,
        source: data,
        view,
        log: true,
        onError: (message: string) => {
          throw Error(message);
        },
        onCamera: (_: string, c: any) => {
          (window as any).cameraResult = c;
        },
      }),
    );
    (window as any).vtkRoot = root;
    return { resampled: preview.resampled, points: preview.data.z.length };
  }, data);
  expect(result.resampled).toBe(true);
  expect(result.points).toBeGreaterThan(2);
  const canvas = page.locator("[data-renderer=vtk] canvas");
  await expect(canvas).toBeVisible();
  const box = (await canvas.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    box.x + box.width / 2 + 40,
    box.y + box.height / 2 + 20,
    { steps: 4 },
  );
  await page.mouse.up();
  await expect
    .poll(() => page.evaluate(() => (window as any).cameraResult?.projection))
    .toBe("perspective");
  await page.screenshot({ path: test.info().outputPath("vtk-real.png") });
  await page.evaluate(() => (window as any).vtkRoot.unmount());
});
