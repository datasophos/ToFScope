import { test, expect } from "@playwright/test";

test("raw opening requires confirmation, prepares a copy and opens working plots", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `raw-${Date.now()}` });
  let preparations = 0;
  page.on("request", (r) => {
    if (r.url().endsWith("/acquisitions/prepare")) preparations++;
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await page.getByRole("button", { name: "▸ nested", exact: true }).dblclick();
  await page.getByRole("button", { name: "◫ raw.h5", exact: true }).dblclick();
  const confirmation = page.getByRole("dialog", {
    name: "Prepare raw acquisition",
  });
  await expect(confirmation).toBeVisible();
  await expect(confirmation).toContainText(
    "original file will remain unchanged",
  );
  await expect(
    page.getByLabel("Prepared filename", { exact: true }),
  ).toHaveValue("raw_prepared.h5");
  expect(preparations).toBe(0);
  for (const width of [1200, 560]) {
    await page.setViewportSize({ width, height: 1000 });
    const back = await confirmation
      .getByRole("button", { name: "Back to files", exact: true })
      .boundingBox();
    const prepare = await confirmation
      .getByRole("button", { name: "Prepare and open", exact: true })
      .boundingBox();
    expect(Math.abs(back!.height - prepare!.height)).toBeLessThan(0.5);
    expect(back!.height).toBeLessThan(46);
  }
  await page
    .getByRole("button", { name: "Back to files", exact: true })
    .click();
  expect(preparations).toBe(0);
  await page.getByRole("button", { name: "◫ raw.h5", exact: true }).dblclick();
  await page
    .getByLabel("Prepared filename", { exact: true })
    .fill("my-prepared.h5");
  await page
    .getByRole("button", { name: "Prepare and open", exact: true })
    .click();
  await expect(
    page.getByRole("tab", { name: "1 · my-prepared.h5", exact: true }),
  ).toBeVisible();
  expect(preparations).toBe(1);
  await expect(
    page.getByTestId("panel-ion").locator("canvas").first(),
  ).toBeVisible();
  await expect(page.getByTestId("save-state")).toHaveText("No changes");
  await page
    .getByRole("button", { name: "Close analysis 1", exact: true })
    .click();
  await expect(page.getByRole("tablist", { name: "Open analyses" }).getByRole("tab")).toHaveCount(0);
});

test("preparation cancellation preserves the existing analysis", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `raw-cancel-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  await page
    .getByRole("button", { name: "Open TOFexplorer file", exact: true })
    .click();
  await page.getByRole("button", { name: "▸ nested", exact: true }).dblclick();
  await page.getByRole("button", { name: "◫ raw.h5", exact: true }).dblclick();
  await page.route("**/api/v1/jobs/*", async (route) => {
    const response = await route.fetch();
    const job = await response.json();
    await route.fulfill({
      json: {
        ...job,
        status: "running",
        stage: "Integrating peak channels",
        done: 1,
        total: 4,
      },
    });
  });
  let cancelled = false;
  await page.route("**/api/v1/jobs/*/cancel", async (route) => {
    cancelled = true;
    await route.fulfill({
      json: {
        id: "cancel-test",
        analysis_id: "",
        status: "cancelled",
        kind: "preparation",
      },
    });
  });
  await page
    .getByRole("button", { name: "Prepare and open", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Cancel preparation", exact: true })
    .click();
  expect(cancelled).toBe(true);
  await page
    .getByRole("button", { name: "Back to files", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "◫ raw.h5", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close picker", exact: true }).click();
  await expect(
    page.getByRole("tab", { name: "1 · a.h5", exact: true }),
  ).toBeVisible();
});

test("launching with a raw filename also asks before preparing", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `raw-startup-${Date.now()}`,
  });
  await page.route("**/api/v1/auth/session", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      json: { ...(await response.json()), initial_file: "nested/raw.h5" },
    });
  });
  await page.goto("/");
  await expect(
    page.getByRole("dialog", { name: "Prepare raw acquisition" }),
  ).toBeVisible();
  await expect(page.getByRole("tablist", { name: "Open analyses" }).getByRole("tab")).toHaveCount(0);
});

test("missing calibration defaults are visible and explicitly accepted before preparation", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `raw-assumptions-${Date.now()}`,
  });
  let acknowledged = false;
  page.on("request", (r) => {
    if (r.url().endsWith("/acquisitions/prepare"))
      acknowledged = r.postDataJSON().accept_assumptions === true;
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await page.getByRole("button", { name: "▸ nested", exact: true }).dblclick();
  await page
    .getByRole("button", { name: "◫ assumed-raw.h5", exact: true })
    .dblclick();
  await expect(
    page.getByRole("region", { name: "Reconstruction assumptions" }),
  ).toContainText("clock ratio 1");
  await expect(
    page.getByRole("region", { name: "Reconstruction assumptions" }),
  ).toContainText("one active channel");
  expect(acknowledged).toBe(false);
  await page
    .getByRole("button", { name: "Prepare with assumptions", exact: true })
    .click();
  await expect(
    page.getByRole("tab", { name: "1 · assumed-raw_prepared.h5", exact: true }),
  ).toBeVisible();
  expect(acknowledged).toBe(true);
});

test("a failed automatic open clearly preserves the prepared copy and can be retried", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `raw-retry-${Date.now()}`,
  });
  let failed = false;
  await page.route("**/api/v1/analyses", async (route) => {
    if (
      route.request().method() === "POST" &&
      route.request().postDataJSON().location === "saved" &&
      !failed
    ) {
      failed = true;
      await route.fulfill({
        status: 409,
        json: {
          code: "source_changed",
          message: "Acquisition changed; explicitly reopen it.",
        },
      });
    } else await route.continue();
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await page.getByRole("button", { name: "▸ nested", exact: true }).dblclick();
  await page.getByRole("button", { name: "◫ raw.h5", exact: true }).dblclick();
  await page
    .getByRole("button", { name: "Prepare and open", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Your prepared copy is safe",
  );
  await expect(page.getByRole("alert")).not.toContainText(
    "Acquisition changed",
  );
  await page
    .getByRole("button", { name: "Open prepared copy", exact: true })
    .click();
  await expect(
    page.getByRole("tab", { name: "1 · raw_prepared.h5", exact: true }),
  ).toBeVisible();
});
