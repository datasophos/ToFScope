import { test, expect, type Locator, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { createHash } from "node:crypto";

const output = process.env.TOFSCOPE_DOC_OUTPUT;
if (!output)
  throw new Error("Set TOFSCOPE_DOC_OUTPUT via scripts/capture_docs.py.");
mkdirSync(output, { recursive: true });

async function capture(page: Page, name: string) {
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: join(output!, name), animations: "disabled" });
}

async function settleCanvas(canvas: Locator) {
  let previous = "";
  let stable = 0;
  await expect
    .poll(
      async () => {
        const digest = createHash("sha256")
          .update(await canvas.screenshot())
          .digest("hex");
        stable = digest === previous ? stable + 1 : 0;
        previous = digest;
        return stable;
      },
      { intervals: [250], timeout: 15000 },
    )
    .toBeGreaterThanOrEqual(2);
}

async function captureDialog(dialog: Locator, name: string) {
  // Temporary paths and owner hashes vary by machine and must not enter docs.
  await dialog.evaluate((root) => {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const edits: [Text, string][] = [];
    while (walker.nextNode()) {
      const node = walker.currentNode as Text;
      const original = node.data;
      const cleaned = (
        original.includes("tofscope-doc-capture-")
          ? "/example/tofscope/saved/mosfet-demo_analysis.h5"
          : original
      ).replace(/\b[a-f0-9]{64}\b/g, "demo");
      if (cleaned !== original) {
        edits.push([node, original]);
        node.data = cleaned;
      }
    }
    (
      window as Window & { docsCaptureRestore?: [Text, string][] }
    ).docsCaptureRestore = edits;
  });
  try {
    await dialog.screenshot({
      path: join(output!, name),
      animations: "disabled",
    });
  } finally {
    await dialog.evaluate(() => {
      const win = window as Window & { docsCaptureRestore?: [Text, string][] };
      for (const [node, original] of win.docsCaptureRestore ?? [])
        node.data = original;
      delete win.docsCaptureRestore;
    });
  }
}

test("capture documentation views using the synthetic demo", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": "documentation" });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page
    .getByRole("button", { name: "◫ mosfet-demo.h5", exact: true })
    .dblclick();
  await page.getByRole("button", { name: "Add signal", exact: true }).click();
  await page
    .getByRole("listbox", { name: "Stored signals" })
    .getByRole("option", { name: /^Al ·/ })
    .click();
  const al = page
    .getByLabel("Image signal")
    .locator("option")
    .filter({ hasText: /^Al ·/ });
  await expect(al).toHaveCount(1);
  await page
    .getByLabel("Image signal")
    .selectOption((await al.getAttribute("value"))!);
  await expect(page.getByTestId("panel-ion")).toContainText("Al");
  await expect(
    page.getByTestId("panel-spectrum").locator("canvas").first(),
  ).toBeVisible();
  await expect(
    page.getByTestId("panel-ion").locator("canvas").first(),
  ).toBeVisible();
  await expect(
    page.getByTestId("panel-front").locator("canvas").first(),
  ).toBeVisible();
  await expect(
    page.getByTestId("panel-profile").locator("canvas").first(),
  ).toBeVisible();
  await page.waitForLoadState("networkidle");
  await settleCanvas(
    page.getByTestId("panel-spectrum").locator("canvas").first(),
  );
  await settleCanvas(page.getByTestId("panel-ion").locator("canvas").first());
  await capture(page, "tofscope-explore.png");
  await page.getByTestId("panel-profile").screenshot({
    path: join(output!, "profile-relative.png"),
    animations: "disabled",
  });
  await page.getByLabel("Relative profiles").click();
  await expect(page.getByLabel("Relative profiles")).not.toBeChecked();
  await page.getByTestId("panel-profile").screenshot({
    path: join(output!, "profile-mean.png"),
    animations: "disabled",
  });
  await page.getByLabel("Relative profiles").click();
  await expect(page.getByLabel("Relative profiles")).toBeChecked();
  await page.getByRole("button", { name: "Calibrate depth" }).click();
  const calibration = page.getByRole("dialog", { name: "Depth calibration" });
  await expect(calibration).toBeVisible();
  await calibration.getByLabel("Anchor frame", { exact: true }).fill("25");
  await calibration.getByLabel("Known depth", { exact: true }).fill("50");
  await calibration
    .getByRole("button", { name: "Add anchor", exact: true })
    .click();
  await calibration.screenshot({
    path: join(output!, "depth-calibration.png"),
    animations: "disabled",
  });
  await calibration.getByRole("button", { name: "Done", exact: true }).click();
  await page
    .getByTestId("panel-spectrum")
    .locator("summary")
    .filter({ hasText: "Analyze" })
    .click();
  await page
    .getByRole("button", { name: "Create signal", exact: true })
    .click();
  await page.getByLabel("Signal name", { exact: true }).fill("Titanium");
  await page.getByLabel("Mass lower 1", { exact: true }).fill("46");
  await page.getByLabel("Mass upper 1", { exact: true }).fill("50");
  await page.getByRole("button", { name: "Zoom to draft" }).click();
  await page.getByLabel("Mass lower 1", { exact: true }).fill("47.75");
  await page.getByLabel("Mass upper 1", { exact: true }).fill("48.15");
  await page.locator(".spectrum-workbench").screenshot({
    path: join(output!, "signal-editor.png"),
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Discard", exact: true }).click();
  await page
    .getByRole("button", { name: "Discard and continue", exact: true })
    .click();
  await page.setViewportSize({ width: 2400, height: 1100 });
  await page.getByTestId("panel-front").screenshot({
    path: join(output!, "tofscope-front-projection-xz.png"),
    animations: "disabled",
  });
  await page
    .getByTestId("panel-front")
    .getByRole("button", { name: "Switch to Y-Z projection" })
    .click();
  await expect(
    page
      .getByTestId("panel-front")
      .getByRole("button", { name: "Switch to X-Z projection" }),
  ).toBeVisible();
  await page.getByTestId("panel-front").screenshot({
    path: join(output!, "tofscope-front-projection-yz.png"),
    animations: "disabled",
  });
  await page.setViewportSize({ width: 1660, height: 1100 });
  await page
    .getByTestId("panel-spectrum")
    .locator("summary")
    .filter({ hasText: "Analyze" })
    .click();
  await page
    .getByRole("button", { name: "Identify peak", exact: true })
    .click();
  const identification = page.getByRole("dialog", {
    name: "Atomic identification",
  });
  await expect(identification).toBeVisible();
  await identification
    .getByLabel("Measured m/z", { exact: true })
    .fill("26.9815");
  await identification
    .getByRole("button", { name: "Find candidates", exact: true })
    .click();
  await expect(
    identification.getByRole("radio", { name: "Al-27:+1" }),
  ).toBeVisible();
  await identification.getByRole("radio", { name: "Al-27:+1" }).check();
  await page.evaluate(() => (document.activeElement as HTMLElement)?.blur());
  await identification.screenshot({
    path: join(output!, "tofscope-isotope-identification.png"),
    animations: "disabled",
  });
  await identification
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await page.getByRole("button", { name: "Save as…", exact: true }).click();
  const save = page.getByRole("dialog", { name: /Save/ });
  await expect(save).toBeVisible();
  await expect(save.locator(".folder-paths")).toContainText(
    "tofscope-doc-capture-",
  );
  await captureDialog(save, "tofscope-save-copy.png");
  await save.getByRole("button", { name: "Save copy", exact: true }).click();
  await expect(save.getByText("Copy saved.", { exact: true })).toBeVisible({
    timeout: 120_000,
  });
  await captureDialog(save, "tofscope-download-copy.png");
  await page
    .getByRole("button", { name: "Close save dialog", exact: true })
    .click();
  await page
    .getByTestId("panel-spectrum")
    .locator("summary")
    .filter({ hasText: "Analyze" })
    .click();
  await page
    .getByRole("button", { name: "Isotope measurements", exact: true })
    .click();
  const measurements = page.getByRole("dialog", {
    name: "Isotope measurements",
  });
  await measurements.getByRole("checkbox").first().check();
  await measurements.getByRole("checkbox").nth(1).check();
  await measurements
    .getByRole("button", { name: "Measure", exact: true })
    .click();
  await expect(measurements.getByTestId("isotope-results")).toContainText(
    "Measured",
    { timeout: 120_000 },
  );
  await measurements.screenshot({
    path: join(output!, "tofscope-isotope-measurements.png"),
    animations: "disabled",
  });
  await measurements
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await page.getByRole("tab", { name: "3D volume", exact: true }).click();
  await page.getByRole("checkbox", { name: /Show Si .* in 3D/ }).check();
  await expect(
    page.getByTestId("volume-canvas").locator("canvas").first(),
  ).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("volume-status")).toContainText(/layer/, {
    timeout: 120_000,
  });
  await expect(page.getByTestId("volume-status")).toContainText("2 layers", {
    timeout: 120_000,
  });
  for (const [prefix, colorscale] of [
    ["Al", "Reds"],
    ["Si", "Blues"],
  ]) {
    const settings = page.getByRole("button", {
      name: new RegExp(`^3D settings for ${prefix} `),
    });
    await settings.click();
    const dialog = page.getByRole("dialog", {
      name: new RegExp(`^3D settings for ${prefix} `),
    });
    await dialog.getByRole("combobox").click();
    await page.getByRole("option", { name: colorscale, exact: true }).click();
    await dialog.getByLabel(/^3D opacity/).fill("0.65");
    await dialog
      .getByRole("button", { name: "Close 3D signal settings" })
      .click();
  }
  await page.getByRole("button", { name: "Maximize 3D" }).click();
  // Let the maximized WebGL view finish its resize and render.
  await page.waitForTimeout(1000);
  await page.locator(".volume-workspace").screenshot({
    path: join(output!, "tofscope-3d.png"),
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Restore 3D" }).click();
  await page.getByText("Display settings", { exact: true }).click();
  await page
    .locator("details.volume-sidebar-section")
    .filter({ hasText: "Display settings" })
    .screenshot({
      path: join(output!, "3d-display-settings.png"),
      animations: "disabled",
    });
  await page.getByRole("checkbox", { name: "Show SE in 3D" }).check();
  await page.getByRole("button", { name: "3D settings for SE" }).click();
  await expect(page.getByLabel("Preview intensity histogram")).toBeVisible();
  await page.getByRole("dialog", { name: "3D settings for SE" }).screenshot({
    path: join(output!, "tofscope-3d-signal-settings.png"),
    animations: "disabled",
  });
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", { name: "Open TOFexplorer file", exact: true })
    .click();
  await page
    .getByRole("button", { name: "◫ mosfet-raw.h5", exact: true })
    .dblclick();
  const raw = page.getByRole("dialog", { name: "Prepare raw acquisition" });
  await expect(raw).toBeVisible({ timeout: 30_000 });
  await captureDialog(raw, "tofscope-raw-preparation.png");
});
