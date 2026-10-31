import { test, expect } from "@playwright/test";

test("atomic annotation preserves labels and explicit measurement becomes stale", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `identify-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  await page
    .getByRole("button", { name: "Identify peak", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Atomic identification" });
  await expect(dialog.getByText(/pre-alpha/i)).toHaveCount(0);
  await expect(dialog.getByLabel("Tolerance unit")).toHaveValue("Th");
  await expect(dialog.getByRole("option", { name: "Absolute m/z difference" })).toBeAttached();
  await dialog.getByLabel("Measured m/z", { exact: true }).fill("26.981");
  await dialog
    .getByRole("button", { name: "Find candidates", exact: true })
    .click();
  await dialog.getByRole("radio", { name: "Al-27:+1", exact: true }).check();
  await dialog
    .getByLabel("Signal to assign", { exact: true })
    .selectOption({ index: 0 });
  await dialog
    .getByRole("button", { name: "Assign isotope to signal", exact: true })
    .click();
  await expect(
    dialog.getByText("Assigned Al-27:+1", { exact: true }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await page
    .getByRole("button", { name: "Isotope measurements", exact: true })
    .click();
  const measurements = page.getByRole("dialog", {
    name: "Isotope measurements",
    exact: true,
  });
  await expect(measurements.getByText(/pre-alpha: isotope measurements have not been thoroughly tested/i)).toBeVisible();
  await measurements.getByRole("checkbox").first().check();
  await measurements
    .getByRole("button", { name: "Measure", exact: true })
    .click();
  await expect(measurements.getByTestId("isotope-results")).toContainText("75");
  await expect(measurements.getByTestId("isotope-results")).toContainText(
    "Al-27:+1",
  );
  await measurements
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await page.getByRole("button", { name: "Single frame", exact: true }).click();
  await page
    .getByRole("button", { name: "Isotope measurements", exact: true })
    .click();
  await expect(measurements.getByText(/Out of date/)).toBeVisible();
});

test("exact identification window creates an assigned raw comparison and exports measurements", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `identify-window-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  await page
    .getByRole("button", { name: "Identify peak", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Atomic identification" });
  await dialog.getByLabel("Measured m/z", { exact: true }).fill("2.014");
  await dialog
    .getByRole("button", { name: "Find candidates", exact: true })
    .click();
  await dialog.getByRole("radio", { name: "H-2:+1", exact: true }).check();
  await dialog.getByLabel("Lower m/z", { exact: true }).fill("1");
  await dialog.getByLabel("Upper m/z", { exact: true }).fill("2");
  await dialog
    .getByRole("button", { name: "Add signal", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator(".profile-legend")).toContainText("H-2:+1");
  await page
    .getByRole("button", { name: "Isotope measurements", exact: true })
    .click();
  const measurements = page.getByRole("dialog", {
    name: "Isotope measurements",
    exact: true,
  });
  await measurements.getByRole("checkbox", { name: /H-2/ }).check();
  await measurements
    .getByRole("button", { name: "Measure", exact: true })
    .click();
  await expect(measurements.getByTestId("isotope-results")).toContainText(
    "Measured",
  );
  await expect(
    measurements.getByTestId("isotope-results").locator("tbody td").nth(1),
  ).toHaveText("3");
  const csv = page.waitForEvent("download");
  await measurements
    .getByRole("button", { name: "Isotope CSV", exact: true })
    .click();
  expect((await csv).suggestedFilename()).toBe("tofscope-isotopes.csv");
  await page.screenshot({
    path: test.info().outputPath("isotope-measurements.png"),
  });
  await measurements
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Identify peak", exact: true })
    .click();
  await page.screenshot({
    path: test.info().outputPath("atomic-identification.png"),
  });
  await dialog
    .getByRole("button", { name: "Apply window", exact: true })
    .click();
  const draft = page.getByRole("region", { name: "Signal editor" });
  await expect(draft.getByLabel("Signal name", { exact: true })).toHaveValue(
    "H-2:+1",
  );
  await expect(draft.getByLabel("Mass lower 1", { exact: true })).toHaveValue(
    "1",
  );
  await expect(draft.getByLabel("Mass upper 1", { exact: true })).toHaveValue(
    "2",
  );
  await draft.getByRole("button", { name: "Discard", exact: true }).click();
});

test("identification uses log scale, spaced fields and natural-abundance ordering", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `identify-polish-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  await page
    .getByRole("button", { name: "Use linear y scale", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Identify peak", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Atomic identification" });
  const spectrum = dialog.getByTestId("panel-identification");
  await expect(spectrum).toHaveAttribute("data-y-scale", "log");
  await dialog
    .getByRole("button", { name: "Use linear y scale", exact: true })
    .click();
  await expect(spectrum).toHaveAttribute("data-y-scale", "linear");
  await dialog
    .getByRole("button", { name: "Use logarithmic y scale", exact: true })
    .click();
  const mass = dialog.getByLabel("Measured m/z", { exact: true });
  await expect(mass).toHaveCSS("border-top-color", "rgb(113, 138, 152)");
  const field = (await mass.boundingBox())!,
    tolerance = (await dialog
      .getByLabel("Tolerance", { exact: true })
      .boundingBox())!;
  expect(tolerance.x - field.x - field.width).toBeGreaterThanOrEqual(12);
  expect(
    Math.abs(field.y + field.height - tolerance.y - tolerance.height),
  ).toBeLessThan(2);
  await mass.fill("47.95924758911");
  const toleranceField = dialog.getByLabel("Tolerance", { exact: true });
  await toleranceField.fill("0.1");
  await toleranceField.focus();
  await toleranceField.press("ArrowUp");
  await expect(toleranceField).toHaveValue("0.2");
  await toleranceField.press("ArrowDown");
  await expect(toleranceField).toHaveValue("0.1");
  const search = page.waitForRequest((r) => r.url().endsWith("/candidates"));
  await dialog
    .getByRole("button", { name: "Find candidates", exact: true })
    .click();
  expect((await search).postDataJSON().mz).toBe(47.95924758911);
  await expect(mass).toHaveValue("47.9592");
  await mass.focus();
  await expect(mass).toHaveValue("47.95924758911");
  await toleranceField.focus();
  const table = dialog.getByRole("table");
  await expect(table.locator("tbody tr").first()).toContainText("Ti-48:+1");
  await expect(table.locator("tbody tr").first()).toContainText("73.72%");
  await expect(
    dialog.getByRole("radio", { name: "K-48:+1", exact: true }),
  ).toHaveCount(0);
  await page.screenshot({
    path: test.info().outputPath("identification-natural-abundance.png"),
  });
  await dialog
    .getByLabel("Include isotopes without natural abundance", { exact: true })
    .check();
  await expect(
    dialog.getByRole("radio", { name: "K-48:+1", exact: true }),
  ).toBeVisible();
  await expect(table.locator("tbody")).toContainText("Not tabulated");
  await dialog
    .getByLabel("Candidate order", { exact: true })
    .selectOption("mass");
  await expect(table.locator("tbody tr").first()).toContainText("K-48:+1");
  await dialog.getByLabel("Tolerance", { exact: true }).fill("0.01");
  await dialog
    .getByRole("button", { name: "Find candidates", exact: true })
    .click();
  await expect(
    dialog.getByRole("radio", { name: "Ti-48:+1", exact: true }),
  ).toHaveCount(0);
  await page.setViewportSize({ width: 560, height: 800 });
  await expect
    .poll(async () => {
      const box = (await dialog.boundingBox())!;
      return box.x >= 10 && box.x + box.width <= 550;
    })
    .toBe(true);
  expect(await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(
    true,
  );
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await expect(page.getByTestId("panel-spectrum")).toHaveAttribute(
    "data-y-scale",
    "linear",
  );
});

test("spectrum picks search immediately with current settings and discard older responses", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `identify-pick-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  await page
    .getByRole("button", { name: "Identify peak", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Atomic identification" });
  await dialog.getByLabel("Tolerance", { exact: true }).fill("0.2");
  await dialog.getByLabel("+2", { exact: true }).check();
  let count = 0;
  let releaseOld!: () => void;
  const oldGate = new Promise<void>((resolve) => {
    releaseOld = resolve;
  });
  await page.route("**/candidates", async (route) => {
    const first = ++count === 1;
    const response = await route.fetch();
    if (first) await oldGate;
    await route.fulfill({ response });
  });
  const overlay = dialog.getByLabel("Identification spectrum selection", {
    exact: true,
  });
  const box = (await overlay.boundingBox())!;
  const first = page.waitForRequest((r) => r.url().endsWith("/candidates"), {
    timeout: 3000,
  });
  await overlay.click({
    position: { x: box.width * 0.25, y: box.height * 0.5 },
  });
  const request = await first;
  expect(request.postDataJSON().mz).toBeCloseTo(1, 1);
  expect(request.postDataJSON()).toMatchObject({
    tolerance: 0.2,
    unit: "Th",
    charges: [1, 2],
  });
  const second = page.waitForRequest((r) => r.url().endsWith("/candidates"));
  await overlay.click({
    position: { x: box.width * 0.42, y: box.height * 0.5 },
  });
  expect((await second).postDataJSON().mz).toBeGreaterThan(1.9);
  await expect(
    dialog.getByRole("radio", { name: "He-4:+2", exact: true }),
  ).toBeVisible();
  const oldResponse = page.waitForResponse(
    (r) =>
      r.url().endsWith("/candidates") && r.request().postDataJSON().mz < 1.5,
  );
  releaseOld();
  await (await oldResponse).finished();
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => requestAnimationFrame(() => resolve())),
  );
  await expect(
    dialog.getByRole("radio", { name: "He-4:+2", exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("radio", { name: "H-1:+1", exact: true }),
  ).toHaveCount(0);
  expect(
    Number(
      await dialog.getByLabel("Measured m/z", { exact: true }).inputValue(),
    ),
  ).toBeGreaterThan(1.9);
});

test("search settings immediately refresh candidates with the updated values", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `identify-settings-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  await page
    .getByRole("button", { name: "Identify peak", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Atomic identification" });
  await dialog.getByLabel("Measured m/z", { exact: true }).fill("2.014");
  const search = async (change: () => Promise<unknown>, expected: object) => {
    const request = page.waitForRequest(
      (r) => r.url().endsWith("/candidates"),
      { timeout: 3000 },
    );
    await change();
    expect((await request).postDataJSON()).toMatchObject({
      mz: 2.014,
      ...expected,
    });
    await expect(
      dialog.getByRole("button", { name: "Find candidates", exact: true }),
    ).toBeEnabled();
  };
  await search(
    () =>
      dialog
        .getByRole("button", { name: "Find candidates", exact: true })
        .click(),
    { tolerance: 0.3, unit: "Th", charges: [1] },
  );
  await expect(
    dialog.getByRole("radio", { name: "H-2:+1", exact: true }),
  ).toBeVisible();
  await search(
    () => dialog.getByLabel("Tolerance", { exact: true }).fill("0.2"),
    { tolerance: 0.2, unit: "Th", charges: [1] },
  );
  await search(
    () =>
      dialog.getByLabel("Tolerance unit", { exact: true }).selectOption("ppm"),
    { tolerance: 0.2, unit: "ppm", charges: [1] },
  );
  await expect(
    dialog.getByRole("radio", { name: "H-2:+1", exact: true }),
  ).toHaveCount(0);
  await search(() => dialog.getByLabel("+2", { exact: true }).check(), {
    tolerance: 0.2,
    unit: "ppm",
    charges: [1, 2],
  });
  await search(() => dialog.getByLabel("-1", { exact: true }).check(), {
    tolerance: 0.2,
    unit: "ppm",
    charges: [1, 2, -1],
  });
  await search(() => dialog.getByLabel("+1", { exact: true }).uncheck(), {
    tolerance: 0.2,
    unit: "ppm",
    charges: [2, -1],
  });
});

test("Apply window retains the chosen isotope through a renamed draft and measurement", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `identify-draft-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  await page
    .getByRole("button", { name: "Identify peak", exact: true })
    .click();
  const identify = page.getByRole("dialog", { name: "Atomic identification" });
  await identify
    .getByLabel("Measured m/z", { exact: true })
    .fill("2.014123456789");
  await identify
    .getByRole("button", { name: "Find candidates", exact: true })
    .click();
  await identify.getByRole("radio", { name: "H-2:+1", exact: true }).check();
  await identify.getByLabel("Lower m/z", { exact: true }).fill("1");
  await identify.getByLabel("Upper m/z", { exact: true }).fill("2");
  await identify
    .getByRole("button", { name: "Apply window", exact: true })
    .click();
  const draft = page.getByRole("region", {
    name: "Signal editor",
    exact: true,
  });
  await draft
    .getByLabel("Signal name", { exact: true })
    .fill("Hydrogen window");
  const submitted = page.waitForRequest(
    (r) => r.url().endsWith("/jobs") && r.method() === "POST",
  );
  await draft
    .getByRole("button", { name: "Calculate signal", exact: true })
    .click();
  expect((await submitted).postDataJSON().spec).toMatchObject({
    name: "Hydrogen window",
    candidate_id: "H-2:+1",
    measured_mz: 2.014123456789,
  });
  await expect(draft).toBeHidden();
  await page
    .getByRole("button", { name: "Isotope measurements", exact: true })
    .click();
  const measurements = page.getByRole("dialog", {
    name: "Isotope measurements",
    exact: true,
  });
  await measurements.getByRole("checkbox", { name: /Hydrogen window/ }).check();
  await measurements
    .getByRole("button", { name: "Measure", exact: true })
    .click();
  const results = measurements.getByTestId("isotope-results");
  await expect(results.locator("tbody tr")).toContainText("H-2:+1");
  await expect(results).not.toContainText("No isotope assigned");
  await expect(results.locator("tbody td").nth(3)).toContainText("%");
});
