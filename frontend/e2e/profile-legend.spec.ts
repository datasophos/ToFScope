import { manageSignals, addSignal } from "./signal-controls";
import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("profile legend and tray markers identify curves and retain colors after removal", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `legend-${Date.now()}` });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Choose an HDF5 acquisition" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).click();
  await page.getByRole("button", { name: "Add signal", exact: true }).click();
  await page
    .getByRole("listbox", { name: "Stored signals" })
    .getByRole("option")
    .first()
    .click();
  await manageSignals(page);
  await expect(page.getByTestId("signal-row")).toHaveCount(2);
  await addSignal(page);
  await page
    .getByRole("button", { name: "Create from spectrum", exact: true })
    .click();
  await page.getByLabel("Mass lower 1", { exact: true }).fill("1");
  await page.getByLabel("Mass upper 1", { exact: true }).fill("2");
  await page
    .getByRole("button", { name: "Calculate signal", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Signal editor" }),
  ).toBeHidden();
  const profile = page.getByTestId("panel-profile");
  const legend = profile.getByRole("list", { name: "Depth profile legend" });
  await expect(legend.getByRole("listitem")).toHaveCount(3);
  await expect(legend.getByRole("listitem").first()).toContainText("Images");
  const entries = await legend.getByRole("listitem").evaluateAll((items) =>
    items.map((item) => ({
      id: item.getAttribute("data-curve-id")!,
      color:
        item.querySelector<HTMLElement>(".curve-marker")!.style.borderTopColor,
      label: item.textContent,
    })),
  );
  expect(new Set(entries.map((entry) => entry.color)).size).toBe(3);
  await manageSignals(page);
  for (const entry of entries) {
    const row = page.locator(
      `[data-testid="signal-row"][data-signal-id="${entry.id}"]`,
    );
    await expect(row.locator(".text-button").first()).not.toBeEmpty();
    await expect(row.locator(".curve-marker")).toHaveCSS(
      "border-top-color",
      entry.color,
    );
  }
  await page
    .locator(`[data-testid="signal-row"][data-signal-id="${entries[1].id}"]`)
    .getByRole("button", { name: /^Remove / })
    .click();
  await expect(legend.getByRole("listitem")).toHaveCount(2);
  const survivor = legend.locator(`[data-curve-id="${entries[2].id}"]`);
  await expect(survivor.locator(".curve-marker")).toHaveCSS(
    "border-top-color",
    entries[2].color,
  );
  // Verify the plotted line itself, not only the HTML marker, uses that color.
  await expect
    .poll(() =>
      profile
        .locator("canvas")
        .first()
        .evaluate((canvas: HTMLCanvasElement, color: string) => {
          const expected = color.match(/\d+/g)!.map(Number);
          const pixels = canvas
            .getContext("2d")!
            .getImageData(0, 0, canvas.width, canvas.height).data;
          let matching = 0;
          for (let i = 0; i < pixels.length; i += 4)
            if (
              pixels[i] === expected[0] &&
              pixels[i + 1] === expected[1] &&
              pixels[i + 2] === expected[2] &&
              pixels[i + 3] === 255
            )
              matching++;
          return matching;
        }, entries[2].color),
    )
    .toBeGreaterThan(5);
  await page
    .getByRole("button", { name: "Maximize Depth profile", exact: true })
    .click();
  await expect(legend).toBeVisible();
  const download = page.waitForEvent("download");
  await profile
    .getByRole("button", { name: "Export Depth profile PNG" })
    .click();
  const exported = await download;
  expect(exported.suggestedFilename()).toBe("tofscope-profile.png");
  const png = (await readFile((await exported.path())!)).toString("base64");
  const header = await page.evaluate(async (base64) => {
    const image = new Image();
    image.src = `data:image/png;base64,${base64}`;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = image.width;
    canvas.height = image.height;
    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(image, 0, 0);
    // First legend row: blue swatch and dark label pixels above the chart.
    const swatch = [...ctx.getImageData(30, 41, 1, 1).data];
    const pixels = ctx.getImageData(72, 24, image.width - 96, 34).data;
    let textPixels = 0;
    for (let i = 0; i < pixels.length; i += 4)
      if (pixels[i] === 32 && pixels[i + 1] === 55 && pixels[i + 2] === 68)
        textPixels++;
    return { swatch, textPixels };
  }, png);
  expect(header.swatch).toEqual([22, 125, 154, 255]);
  expect(header.textPixels).toBeGreaterThan(20);
});
