import { test, expect } from "@playwright/test";

test("selection boundaries stay thin on wide plots and retain easy edge dragging", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1800, height: 900 });
  await page.goto("/evaluation/index.html?renderer=echarts");
  const overlay = page.getByTestId("selection-overlay");
  await expect(overlay).toBeVisible();
  let box = (await overlay.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.6, box.y + box.height * 0.5);
  await page.mouse.up();
  for (const width of [1800, 1000]) {
    await page.setViewportSize({ width, height: 900 });
    const thickness = await overlay.evaluate(async (svg) => {
      const box = svg.getBoundingClientRect();
      const clone = svg.cloneNode(true) as SVGSVGElement;
      clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      clone.setAttribute("width", String(box.width));
      clone.setAttribute("height", String(box.height));
      const image = new Image();
      image.src = `data:image/svg+xml;base64,${btoa(new XMLSerializer().serializeToString(clone))}`;
      await image.decode();
      const canvas = document.createElement("canvas");
      canvas.width = box.width;
      canvas.height = box.height;
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = "white";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(image, 0, 0);
      const row = ctx.getImageData(
        0,
        Math.floor(canvas.height / 2),
        canvas.width,
        1,
      ).data;
      let longest = 0,
        run = 0;
      for (let i = 0; i < row.length; i += 4) {
        // Include antialiased edge pixels, while excluding the faint fill.
        const gold = row[i] - row[i + 2] > 25 && row[i + 1] - row[i + 2] > 10;
        run = gold ? run + 1 : 0;
        longest = Math.max(longest, run);
      }
      return longest;
    });
    expect(thickness).toBeGreaterThan(0);
    expect(thickness).toBeLessThanOrEqual(2);
  }
  box = (await overlay.boundingBox())!;
  // Four pixels from the edge still grabs its transparent resize target.
  await page.mouse.move(box.x + box.width * 0.3 - 4, box.y + box.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.4, box.y + box.height * 0.5);
  await page.mouse.up();
  await expect(page.getByTestId("selection")).toHaveText(
    "2.00000000,3.00000000",
  );
});
