import { expect, test } from "@playwright/test";

test("calculate a selected spectrum and return to the acquisition spectrum", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `roi-spectrum-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  const panel = page.getByTestId("panel-spectrum");
  await expect(
    panel.getByRole("button", { name: "Total sum", exact: true }),
  ).toBeVisible();
  await page.route("**/api/v1/jobs/*", async (route) => {
    const response = await route.fetch();
    await new Promise((resolve) => setTimeout(resolve, 500));
    await route.fulfill({ response });
  });
  await panel.getByRole("button", { name: "Calculate ROI" }).click();
  await expect(
    panel.getByRole("progressbar", {
      name: "ROI spectrum calculation progress",
    }),
  ).toBeVisible();
  await expect(
    panel.getByText(/Selected spectrum · x 0–1, y 0–0, frames 0–2/),
  ).toBeVisible();
  const calculate = panel.getByRole("button", {
    name: /^(Calculate|Update) ROI$/,
  });
  await expect(calculate).toBeDisabled();
  await expect(calculate).toHaveAttribute(
    "title",
    "This ROI spectrum has already been calculated.",
  );
  await page.getByRole("button", { name: /ROI: Full field/ }).click();
  await page.getByLabel("ROI x first").fill("1");
  await page.getByRole("button", { name: "Apply ROI" }).click();
  await expect(calculate.locator(".spectrum-outdated")).toBeVisible();
  await expect(calculate).toHaveAttribute("title", /Spectrum out of date/);
  await expect(calculate).toBeEnabled();
  await page.getByRole("button", { name: /ROI: x 1/ }).click();
  await page.getByRole("button", { name: "Full field", exact: true }).click();
  await expect(calculate.locator(".spectrum-outdated")).toHaveCount(0);
  await expect(calculate).toBeDisabled();
  await panel.getByRole("button", { name: "Total sum", exact: true }).click();
  await expect(
    panel.getByRole("button", { name: "Total sum", exact: true }),
  ).toBeVisible();
  await expect(calculate).toBeDisabled();
  await panel.getByRole("button", { name: "ROI", exact: true }).click();
  await expect(
    panel.getByText(/Selected spectrum · x 0–1, y 0–0, frames 0–2/),
  ).toBeVisible();
  await expect(
    panel.getByRole("button", { name: "Identify peak", exact: true }),
  ).not.toBeVisible();
  await panel.locator("summary").filter({ hasText: "Analyze" }).click();
  await panel
    .getByRole("button", { name: "Identify peak", exact: true })
    .click();
  await expect(
    page.getByText("Atomic identification", { exact: true }),
  ).toBeVisible();
  await expect(panel.locator("details")).not.toHaveAttribute("open");
});

test("exports the complete displayed mass spectrum as CSV", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `spectrum-csv-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  const panel = page.getByTestId("panel-spectrum");
  const exportCsv = async () => {
    const event = page.waitForEvent("download");
    await panel.getByRole("button", { name: "Mass spectrum CSV" }).click();
    const download = await event;
    const stream = await download.createReadStream();
    let text = "";
    for await (const chunk of stream!) text += chunk.toString();
    return {
      filename: download.suggestedFilename(),
      rows: text
        .trim()
        .split(/\r?\n/)
        .filter((row) => row && !row.startsWith("#")),
      text,
    };
  };
  const sum = await exportCsv();
  await panel.getByRole("button", { name: "Use linear y scale" }).click();
  expect((await exportCsv()).rows).toEqual(sum.rows);
  expect(sum.filename).toContain("sum-spectrum");
  expect(sum.text).toContain("# Acquisition,a.h5");
  expect(sum.text).toContain("# Spectrum,Total sum");
  expect(sum.text).toMatch(/# Exported at \(UTC\),\d{4}-/);
  expect(sum.rows).toEqual([
    "m/z,intensity",
    "0,1",
    "1,1",
    "2,1",
    "3,1",
    "4,2",
    "5,2",
  ]);
  await panel.getByRole("button", { name: "Calculate ROI" }).click();
  await expect(
    panel.getByRole("button", { name: "ROI", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  const roi = await exportCsv();
  expect(roi.filename).toContain("roi-spectrum");
  expect(roi.text).toContain("# ROI X pixels,0–1");
  expect(roi.text).toContain("# ROI Y pixels,0–0");
  expect(roi.text).toContain("# Frames,0–2");
  expect(roi.rows).toEqual([
    "m/z,intensity",
    "0,0",
    "1,1.5",
    "2,1.5",
    "3,1.5",
    "4,0.75",
    "5,0.75",
  ]);
  await page.getByRole("button", { name: /ROI: Full field/ }).click();
  await page.getByLabel("ROI x first").fill("1");
  await page.getByRole("button", { name: "Apply ROI" }).click();
  const stale = await exportCsv();
  expect(stale.text).toContain("# ROI X pixels,0–1");
  expect(stale.rows).toEqual(roi.rows);
  await panel.getByRole("button", { name: "Total sum", exact: true }).click();
  expect((await exportCsv()).rows).toEqual(sum.rows);
});

test("shows the completed spectrum when cancellation arrives after completion", async ({
  page,
}) => {
  const owner = `spectrum-cancel-race-${Date.now()}`;
  await page.setExtraHTTPHeaders({ "x-tofscope-user": owner });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  await page.route("**/api/v1/jobs/*", async (route) => {
    const response = await route.fetch();
    const job = await response.json();
    await route.fulfill({ response, json: { ...job, status: "running" } });
  });
  await page.route("**/api/v1/jobs/*/cancel", async (route) => {
    const jobUrl = route
      .request()
      .url()
      .replace(/\/cancel$/, "");
    await expect
      .poll(
        async () =>
          (
            await (
              await page.request.get(jobUrl, {
                headers: { "x-tofscope-user": owner },
              })
            ).json()
          ).status,
      )
      .toBe("succeeded");
    await route.continue();
  });
  const panel = page.getByTestId("panel-spectrum");
  await panel.getByRole("button", { name: "Calculate ROI" }).click();
  await panel.getByRole("button", { name: "Cancel" }).click();
  await expect(
    panel.getByRole("button", { name: "ROI", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    panel.getByText(/Selected spectrum · x 0–1, y 0–0, frames 0–2/),
  ).toBeVisible();
});
