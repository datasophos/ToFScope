import { test, expect } from "@playwright/test";

test("panning a zoomed spectrum preserves width and signal draft intervals", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `pan-${Date.now()}` });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  const panel = page.getByTestId("panel-spectrum");
  const overlay = panel.getByLabel("Mass spectrum selection");
  await overlay.hover();
  const b = (await overlay.boundingBox())!;
  await page.mouse.move(b.x + b.width * 0.3, b.y + b.height / 2);
  await page.mouse.down();
  await page.mouse.move(b.x + b.width * 0.6, b.y + b.height / 2);
  await page.mouse.up();
  const before = (await overlay.getAttribute("data-x-range"))!
    .split(",")
    .map(Number);
  await panel
    .getByRole("button", { name: "Create signal", exact: true })
    .click();
  await page.getByLabel("Mass lower 1", { exact: true }).fill("1.123456789");
  await page.getByLabel("Mass upper 1", { exact: true }).fill("2.987654321");
  const pan = panel.getByRole("button", { name: "Pan", exact: true });
  await pan.click();
  await expect(pan).toHaveAttribute("aria-pressed", "true");
  await overlay.hover();
  const box = (await overlay.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.7, box.y + box.height / 2, {
    steps: 5,
  });
  await page.mouse.up();
  const after = (await overlay.getAttribute("data-x-range"))!
    .split(",")
    .map(Number);
  expect(after[0]).toBeLessThan(before[0]);
  expect(after[1] - after[0]).toBeCloseTo(before[1] - before[0], 10);
  await page.getByLabel("Mass lower 1", { exact: true }).focus();
  await expect(page.getByLabel("Mass lower 1", { exact: true })).toHaveValue(
    "1.123456789",
  );
  await page.getByLabel("Mass upper 1", { exact: true }).focus();
  await expect(page.getByLabel("Mass upper 1", { exact: true })).toHaveValue(
    "2.987654321",
  );
  const pannedRange = (await overlay.getAttribute("data-x-range"))!;
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.7, box.y + box.height / 2);
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height / 2);
  await page.mouse.up();
  await expect(overlay).toHaveAttribute("data-x-range", pannedRange);
  await pan.click();
  await page.mouse.move(box.x + box.width * 0.3, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.6, box.y + box.height / 2);
  await page.mouse.up();
  await expect(
    page.getByLabel("Mass lower 1", { exact: true }),
  ).not.toHaveValue("1.123456789");
});
