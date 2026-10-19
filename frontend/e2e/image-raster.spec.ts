import { test, expect } from "@playwright/test";

test("raster preserves pixel positions, missing data, sharp boundaries and zoom", async ({
  page,
}) => {
  await page.goto("/evaluation/index.html?renderer=echarts");
  const result = await page.evaluate(async () => {
    const modulePath = "/src/plots/selectedRenderer.ts";
    const { mountChart } = await import(modulePath);
    const element = document.createElement("div");
    element.style.cssText = "width:400px;height:400px";
    document.body.append(element);
    const data = {
      kind: "image",
      x: [0, 1],
      y: [0, 1],
      values: [
        [0, 9],
        [null, 4.5],
      ],
      range: [0, 9],
      xRange: [-0.5, 1.5],
      yRange: [-0.5, 1.5],
      yReverse: true,
    };
    const chart = mountChart(element, data);
    const painted = () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      );
    const pixel = (x: number, y: number) => {
      const canvas = element.querySelector("canvas")!;
      const ratio = canvas.width / 400;
      return Array.from(
        canvas.getContext("2d")!.getImageData(x * ratio, y * ratio, 1, 1).data,
      );
    };
    await painted();
    const original = [
      pixel(90, 90),
      pixel(270, 90),
      pixel(90, 270),
      pixel(270, 270),
    ];
    const boundary = [pixel(199, 90), pixel(201, 90)];
    chart.update({ ...data, xRange: [0.5, 1.5] });
    await painted();
    const zoomed = [pixel(90, 90), pixel(270, 90)];
    chart.destroy();
    element.remove();
    return { original, boundary, zoomed };
  });
  expect(result.original).toEqual([
    [25, 30, 90, 255],
    [245, 220, 40, 255],
    [0, 0, 0, 0],
    [135, 125, 65, 255],
  ]);
  expect(result.boundary).toEqual([
    [25, 30, 90, 255],
    [245, 220, 40, 255],
  ]);
  expect(result.zoomed).toEqual([
    [245, 220, 40, 255],
    [245, 220, 40, 255],
  ]);
});
