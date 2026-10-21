import { test, expect } from "@playwright/test";

test("spectrum clicks and tiny pointer jitter preserve zoom; dragging still zooms", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `spectrum-click-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  const panel = page.getByTestId("panel-spectrum");
  const overlay = panel.getByLabel("Mass spectrum selection");
  await overlay.hover();
  const original = (await overlay.getAttribute("data-x-range"))!;
  const b = (await overlay.boundingBox())!;
  await overlay.click({ position: { x: b.width * 0.9, y: b.height * 0.5 } });
  await expect(overlay).toHaveAttribute("data-x-range", original);
  await page.mouse.move(b.x + b.width * 0.9, b.y + b.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(b.x + b.width * 0.9 + 2, b.y + b.height * 0.5 + 1);
  await page.mouse.up();
  await expect(overlay).toHaveAttribute("data-x-range", original);
  await page.mouse.move(b.x + b.width * 0.2, b.y + b.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(b.x + b.width * 0.8, b.y + b.height * 0.5, {
    steps: 5,
  });
  await page.mouse.up();
  await expect(overlay).not.toHaveAttribute("data-x-range", original);
  const zoom = (await overlay.getAttribute("data-x-range"))!
    .split(",")
    .map(Number);
  expect(zoom[1]).toBeGreaterThan(zoom[0]);
  await panel.getByRole("button", { name: "Reset zoom", exact: true }).click();
  await expect(overlay).toHaveAttribute("data-x-range", original);
  const profile = page
    .getByTestId("panel-profile")
    .getByLabel("Depth profile selection");
  await profile.hover();
  const profileBox = (await profile.boundingBox())!;
  await profile.click({
    position: { x: profileBox.width / 2, y: profileBox.height / 2 },
  });
  await expect(page.getByLabel("Frame", { exact: true })).toHaveValue("1");
});
