import { test, expect } from "@playwright/test";
for (const candidate of ["echarts", "plotly"])
  test(`${candidate}: exact selections, move/resize, zoom and async resize`, async ({
    page,
  }) => {
    const remote: string[] = [];
    page.on("request", (r) => {
      if (!r.url().startsWith("http://127.0.0.1:18763")) remote.push(r.url());
    });
    await page.goto(`/evaluation/index.html?renderer=${candidate}`);
    const svg = page.getByTestId("selection-overlay");
    await expect(svg).toBeVisible();
    const b = (await svg.boundingBox())!;
    await page.mouse.move(b.x + b.width * 0.8, b.y + b.height * 0.8);
    await page.mouse.down();
    await page.mouse.move(b.x + b.width * 0.2, b.y + b.height * 0.2, {
      steps: 5,
    });
    await page.mouse.up();
    await expect(page.getByTestId("selection")).toHaveText(
      "1.00000000,4.00000000",
    );
    await page.getByLabel("Exact lower").fill("1.00000001");
    await page.getByLabel("Exact lower").press("Enter");
    await expect(page.getByTestId("selection")).toHaveText(
      "1.00000001,4.00000000",
    );
    await svg.hover();
    await page.keyboard.down("Control");
    await page.mouse.wheel(0, -200);
    await page.keyboard.up("Control");
    await expect(page.getByTestId("zoom")).not.toHaveText("0,5");
    const zoom = await page.getByTestId("zoom").textContent();
    await page.getByRole("button", { name: "Async update + maximize" }).click();
    await page.waitForTimeout(150);
    expect(await page.getByTestId("zoom").textContent()).toEqual(zoom);
    await expect(
      page.getByTestId("rendered-chart").locator("canvas,svg").first(),
    ).toBeVisible();
    expect(remote).toEqual([]);
    await page.getByRole("button", { name: "Probe image" }).click();
    let box = (await svg.boundingBox())!;
    await page.mouse.move(box.x + box.width * 0.75, box.y + box.height * 0.75);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.25, box.y + box.height * 0.25);
    await page.mouse.up();
    await expect(page.getByTestId("selection")).toHaveText(
      "31.50000000,95.50000000,31.50000000,95.50000000",
    );
    if (candidate === "echarts") {
      await page.getByRole("button", { name: "Probe long image" }).click();
      const covered = await page.getByTestId("rendered-chart").evaluate((el) =>
        Array.from(el.querySelectorAll("canvas")).some((canvas) => {
          const c = canvas.getContext("2d")!;
          const p = c.getImageData(
            Math.floor(60 + (canvas.width - 80) * 0.9),
            Math.floor(20 + (canvas.height - 60) * 0.9),
            1,
            1,
          ).data;
          return p[3] > 0 && p[2] < 100;
        }),
      );
      expect(
        covered,
        "last image rows must render in the committed update",
      ).toBe(true);
    }
    await page.getByRole("button", { name: "Probe depth" }).click();
    box = (await svg.boundingBox())!;
    await page.mouse.move(box.x + box.width * 0.2, box.y + 30);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.4, box.y + 30);
    await page.mouse.up();
    await expect(page.getByTestId("selection")).toHaveText(
      "260.00000000,520.00000000",
    );
    const times = await page.evaluate(() =>
      (window as unknown as { measure: () => Promise<number[]> }).measure(),
    );
    times.sort((a, b) => a - b);
    console.log(
      JSON.stringify({ candidate, p50_ms: times[10], p95_ms: times[18] }),
    );
  });
