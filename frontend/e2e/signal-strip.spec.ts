import { test, expect } from "@playwright/test";

test("compact signal strip keeps plots visible and exposes the full collection on demand", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `strip-${Date.now()}` });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).dblclick();
  const strip = page.getByRole("region", { name: "Signals", exact: true });
  await expect(
    page.getByRole("dialog", { name: "Manage signals", exact: true }),
  ).toHaveCount(0);
  await expect(page.getByTestId("signal-row")).toHaveCount(0);
  await expect(strip.getByLabel("Image signal", { exact: true })).toBeVisible();
  await strip.getByRole("button", { name: "Add signal", exact: true }).click();
  await page
    .getByRole("listbox", { name: "Stored signals" })
    .getByRole("option")
    .first()
    .click();
  const chips = strip.getByTestId("profile-chip");
  await expect(chips).toHaveCount(2);
  const desktopHeight = (await strip.boundingBox())!.height;
  console.log(JSON.stringify({ signal_strip_desktop_px: desktopHeight }));
  expect(desktopHeight).toBeLessThan(90);
  expect((await page.getByTestId("panel-ion").boundingBox())!.y).toBeLessThan(
    500,
  );
  await page.screenshot({
    path: "/private/tmp/tofscope-compact-strip-desktop.png",
  });
  const added = await chips.last().getAttribute("data-signal-id");
  await chips
    .last()
    .getByRole("button", { name: /^Hide / })
    .click();
  await expect(chips).toHaveCount(1);
  await strip
    .getByRole("button", { name: "Manage signals", exact: true })
    .click();
  const manager = page.getByRole("dialog", {
    name: "Manage signals",
    exact: true,
  });
  await expect(manager.getByTestId("signal-row")).toHaveCount(2);
  const row = manager.locator(
    `[data-signal-id="${added}"][data-testid="signal-row"]`,
  );
  await row.getByRole("checkbox").click();
  await expect(row.getByRole("checkbox")).toBeChecked();
  await page
    .getByRole("button", { name: "Close Manage signals", exact: true })
    .click();
  await expect(chips).toHaveCount(2);
  await strip.getByLabel("Image signal", { exact: true }).selectOption(added!);
  await expect(
    chips.last().getByRole("button", { name: /^Hide / }),
  ).toBeDisabled();
  await expect(page.getByTestId("panel-ion")).toContainText(
    await chips.last().getByRole("button").first().innerText(),
  );
  await chips.last().getByRole("button").first().click();
  await expect(page.getByLabel("Rename signal", { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 600, height: 800 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const narrowHeight = (await strip.boundingBox())!.height;
  console.log(JSON.stringify({ signal_strip_narrow_px: narrowHeight }));
  expect(narrowHeight).toBeLessThan(140);
  await page.screenshot({
    path: "/private/tmp/tofscope-compact-strip-narrow.png",
  });
});

test("signal collection belongs only to its active analysis tab", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `strip-tabs-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).dblclick();
  await page
    .getByRole("button", { name: "Manage signals", exact: true })
    .click();
  const manager = page.getByRole("dialog", {
    name: "Manage signals",
    exact: true,
  });
  await expect(manager).toBeVisible();
  await page.getByRole("button", { name: "＋ Open TOFexplorer file" }).click();
  await page.getByRole("button", { name: "◫ b.h5" }).dblclick();
  await expect(page.getByRole("tab", { name: "2 · b.h5" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(manager).toHaveCount(0);
  await page.getByRole("tab", { name: "1 · a.h5" }).click();
  await expect(manager.getByTestId("signal-row")).toHaveCount(1);
  await page.keyboard.press("Escape");
  await expect(manager).toHaveCount(0);
});

test("signal markers align with labels and Add signal never clips at larger text sizes", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `strip-alignment-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).dblclick();
  const strip = page.locator(".signal-strip");
  await expect(strip).toBeVisible();
  for (const fontSize of [14, 20]) {
    await page.addStyleTag({
      content: `.signal-strip, .signal-strip button, .signal-strip select { font-size: ${fontSize}px; }`,
    });
    for (const width of [1600, 600]) {
      await page.setViewportSize({ width, height: 900 });
      const offsets = await strip
        .locator(".curve-marker")
        .evaluateAll((markers) =>
          markers.map((marker) => {
            const line = marker.getBoundingClientRect();
            const label = marker.nextElementSibling!.getBoundingClientRect();
            return Math.abs(
              line.y + line.height / 2 - label.y - label.height / 2,
            );
          }),
        );
      expect(offsets.length).toBeGreaterThan(1);
      expect(Math.max(...offsets)).toBeLessThan(1);
      const label = strip.locator(".signal-picker-trigger > span").first();
      expect(
        await label.evaluate((el) => el.scrollWidth <= el.clientWidth),
      ).toBe(true);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
  }
});
