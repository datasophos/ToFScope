import { test, expect } from "@playwright/test";
test("explicit spectrum modes, dirty-draft choice, precise bounds and independent file drafts", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `editor-${Date.now()}` });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Choose an HDF5 acquisition" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).click();
  const spectrum = page.getByTestId("panel-spectrum");
  await expect(spectrum).toContainText("Viewing spectrum");
  const overlay = spectrum.getByTestId("selection-overlay");
  await expect(overlay).toBeVisible();
  const before = await overlay.getAttribute("data-x-range"),
    b = (await overlay.boundingBox())!;
  await page.mouse.move(b.x + b.width * 0.2, b.y + 30);
  await page.mouse.down();
  await page.mouse.move(b.x + b.width * 0.7, b.y + 30);
  await page.mouse.up();
  await expect(overlay).not.toHaveAttribute("data-x-range", before!);
  await expect(page.getByRole("region", { name: "Signal editor" })).toHaveCount(
    0,
  );
  await page
    .getByRole("button", { name: "Create from spectrum", exact: true })
    .click();
  await page.getByLabel("Mass lower 1", { exact: true }).fill("1.123456789123");
  await page
    .getByRole("button", { name: "Create from spectrum", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Keep editing", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Keep editing", exact: true }).click();
  await expect(page.getByLabel("Mass lower 1", { exact: true })).toHaveValue(
    "1.123456789123",
  );
  await page
    .getByRole("button", { name: "Maximize Mass spectrum", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Signal editor" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Restore Mass spectrum", exact: true })
    .click();
  await page.getByRole("button", { name: "＋ Open acquisition" }).click();
  await page.getByRole("button", { name: "◫ b.h5" }).click();
  await expect(
    page.getByRole("region", { name: "Signal editor" }),
  ).toBeHidden();
  await page.getByRole("tab", { name: "1 · a.h5" }).click();
  await expect(
    page.getByLabel("Mass lower 1", { exact: true }).filter({ visible: true }),
  ).toHaveValue("1.123456789123");
  await page
    .getByRole("button", { name: "Create from spectrum", exact: true })
    .filter({ visible: true })
    .click();
  await page
    .getByRole("button", { name: "Discard and continue", exact: true })
    .click();
  await expect(
    page.getByLabel("Mass lower 1", { exact: true }).filter({ visible: true }),
  ).not.toHaveValue("1.123456789123");
});
test("invalid calculation keeps its draft for correction and stored copies have explicit provenance", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `invalid-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Choose an HDF5 acquisition" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).click();
  await page
    .getByTestId("signal-row")
    .first()
    .getByRole("button", { name: "Details", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Create custom copy", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Signal editor" }),
  ).toBeVisible();
  await page.getByLabel("Mass lower 1", { exact: true }).fill("10000");
  await page.getByLabel("Mass upper 1", { exact: true }).fill("20000");
  await page
    .getByRole("button", { name: "Calculate signal", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Signal editor" }).getByRole("alert"),
  ).toBeVisible();
  await expect(page.getByLabel("Mass lower 1", { exact: true })).toHaveValue(
    "10000",
  );
  await page.getByLabel("Mass lower 1", { exact: true }).fill("1");
  await page.getByLabel("Mass upper 1", { exact: true }).fill("2");
  await page
    .getByRole("button", { name: "Calculate signal", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Signal editor" }),
  ).toBeHidden();
  await expect(page.getByTestId("signal-row").last()).toContainText(
    "Raw integration",
  );
});

test("removing a submitted signal also closes its frozen editor", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `remove-pending-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Choose an HDF5 acquisition" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).click();
  let release!: () => void;
  const gate = new Promise<void>((r) => (release = r));
  await page.route("**/api/v1/jobs/*", async (route) => {
    if (route.request().method() === "GET") await gate;
    await route.continue();
  });
  try {
    await page
      .getByRole("button", { name: "Create from spectrum", exact: true })
      .click();
    await page.getByLabel("Signal name", { exact: true }).fill("Remove me");
    await page.getByLabel("Mass lower 1", { exact: true }).fill("1");
    await page.getByLabel("Mass upper 1", { exact: true }).fill("2");
    await page
      .getByRole("button", { name: "Calculate signal", exact: true })
      .click();
    const row = page.getByTestId("signal-row").filter({ hasText: "Remove me" });
    await expect(row).toBeVisible();
    await row
      .getByRole("button", { name: "Remove Remove me", exact: true })
      .click();
    await expect(row).toHaveCount(0);
    await expect(
      page.getByRole("region", { name: "Signal editor" }),
    ).toBeHidden();
  } finally {
    release();
  }
});
