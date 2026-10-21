import { test, expect, type Page } from "@playwright/test";

async function open(page: Page) {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `depth-${Date.now()}` });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  await page
    .getByRole("button", { name: "Calibrate depth", exact: true })
    .click();
  return page.getByRole("dialog", { name: "Depth calibration", exact: true });
}

test("graphical and exact calibration edits, units and original-frame navigation", async ({
  page,
}) => {
  const dialog = await open(page);
  const dialogBox = (await dialog.boundingBox())!;
  const viewport = page.viewportSize()!;
  expect(
    Math.abs(dialogBox.x + dialogBox.width / 2 - viewport.width / 2),
  ).toBeLessThan(2);
  expect(
    Math.abs(dialogBox.y + dialogBox.height / 2 - viewport.height / 2),
  ).toBeLessThan(2);
  const add = (await dialog
    .getByRole("button", { name: "Add anchor", exact: true })
    .boundingBox())!;
  for (const label of ["Anchor frame", "Known depth"]) {
    const input = (await dialog
      .getByLabel(label, { exact: true })
      .boundingBox())!;
    expect(Math.abs(input.y + input.height - add.y - add.height)).toBeLessThan(
      2,
    );
  }
  const overlay = dialog.getByLabel("Calibration profiles selection");
  await expect(overlay).toBeVisible();
  const box = (await overlay.boundingBox())!;
  await overlay.click({
    position: { x: box.width * 0.5, y: box.height * 0.5 },
  });
  await expect(dialog.getByLabel("Anchor frame", { exact: true })).toHaveValue(
    "1",
  );
  await dialog.getByLabel("Known depth", { exact: true }).fill("100");
  await dialog.getByRole("button", { name: "Add anchor", exact: true }).click();
  await expect(
    dialog.getByText("Calibrated frames 0–1", { exact: false }),
  ).toBeVisible();
  await dialog
    .getByLabel("Depth display unit", { exact: true })
    .selectOption("um");
  await dialog.getByLabel("Anchor frame", { exact: true }).fill("2");
  await dialog.getByLabel("Known depth", { exact: true }).fill("0.05");
  await dialog.getByRole("button", { name: "Add anchor", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("increase");
  await expect(dialog.getByRole("alert")).toHaveCSS(
    "color",
    "rgb(159, 27, 27)",
  );
  await expect(dialog.getByLabel("Known depth", { exact: true })).toHaveCSS(
    "border-top-color",
    "rgb(113, 138, 152)",
  );
  await expect(
    dialog.getByLabel("Depth display unit", { exact: true }),
  ).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await page.screenshot({
    path: test.info().outputPath("calibration-rejection.png"),
  });
  await dialog.getByLabel("Known depth", { exact: true }).fill("0.3");
  await dialog.getByRole("button", { name: "Add anchor", exact: true }).click();
  await expect(
    dialog.getByRole("button", { name: "Remove anchor at frame 2" }),
  ).toBeVisible();
  await dialog.getByLabel("Depth at frame 1", { exact: true }).fill("0.12");
  await dialog
    .locator("tr")
    .filter({ has: page.getByLabel("Depth at frame 1", { exact: true }) })
    .getByRole("button", { name: "Update", exact: true })
    .click();
  await expect(
    dialog.getByLabel("Depth at frame 1", { exact: true }),
  ).toHaveValue("0.12");
  await expect(dialog.locator(".anchor-summary")).toContainText(
    "frame 1: 0.12",
  );
  await page.screenshot({
    path: test.info().outputPath("calibration-editor.png"),
  });
  await dialog.getByRole("button", { name: "Done", exact: true }).click();
  await page
    .getByRole("button", { name: "Physical depth", exact: true })
    .click();
  const panel = page.getByTestId("panel-profile");
  await expect(panel.locator("footer")).toContainText("depth · µm");
  const selection = panel.getByLabel("Depth profile selection");
  const bounds = (await selection.boundingBox())!;
  await selection.click({
    position: { x: bounds.width / 3, y: bounds.height / 2 },
  });
  await expect(page.getByLabel("Frame", { exact: true })).toHaveValue("1");
  await page.getByRole("heading", { name: "a.h5", exact: true }).click();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByLabel("Frame", { exact: true })).toHaveValue("2");
  const front = page
    .getByTestId("panel-front")
    .getByLabel("Front projection selection");
  const frontBox = (await front.boundingBox())!;
  await front.click({
    position: { x: frontBox.width / 2, y: frontBox.height / 3 },
  });
  await expect(page.getByLabel("Frame", { exact: true })).toHaveValue("1");
  await page
    .getByRole("button", { name: "Calibrate depth", exact: true })
    .click();
  await dialog
    .getByLabel("Depth display unit", { exact: true })
    .selectOption("mm");
  await expect(
    dialog.getByLabel("Depth at frame 2", { exact: true }),
  ).toHaveValue("0.0003");
  await dialog
    .getByRole("button", { name: "Remove anchor at frame 2" })
    .click();
  await dialog
    .getByRole("button", { name: "Remove anchor at frame 1" })
    .click();
  await expect(
    page.getByRole("button", { name: "Frames", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await dialog.getByRole("button", { name: "Done", exact: true }).click();
  await expect(panel.locator("footer")).toContainText("frame · frame");
});

test("partial calibration survives save/reopen and remains independent between same-file tabs", async ({
  page,
}) => {
  const dialog = await open(page);
  await dialog.getByLabel("Anchor frame", { exact: true }).fill("1");
  await dialog.getByLabel("Known depth", { exact: true }).fill("100");
  await dialog.getByRole("button", { name: "Add anchor", exact: true }).click();
  await expect(
    dialog.getByRole("button", { name: "Remove anchor at frame 1" }),
  ).toBeVisible();
  await dialog
    .getByLabel("Depth display unit", { exact: true })
    .selectOption("um");
  await dialog.getByRole("button", { name: "Done", exact: true }).click();
  await page
    .getByRole("button", { name: "Physical depth", exact: true })
    .click();
  await expect(page.getByTestId("panel-front")).toContainText(
    "1 frame with unknown depth omitted",
  );
  await page.getByRole("button", { name: "Save as…", exact: true }).click();
  await page.getByLabel("Saved filename", { exact: true }).fill("depth.h5");
  await page.getByRole("button", { name: "Save copy", exact: true }).click();
  await expect(page.getByText("Copy saved.", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Close save dialog", exact: true })
    .click();
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  await expect(
    page.locator("main:visible").getByTestId("panel-profile").locator("footer"),
  ).toContainText("frame · frame");
  await page
    .getByRole("button", { name: "Close analysis 2", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Close analysis 1", exact: true })
    .click();
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "Saved files", exact: true }).click();
  await page
    .getByRole("button", { name: "◫ depth.h5", exact: true })
    .dblclick();
  await expect(
    page.getByTestId("panel-profile").locator("footer"),
  ).toContainText("depth · µm");
  await page
    .getByRole("button", { name: "Calibrate depth", exact: true })
    .click();
  await expect(
    dialog.getByLabel("Depth at frame 1", { exact: true }),
  ).toHaveValue("0.1");
});

test("partial physical profiles stay visible while viewing an uncalibrated frame", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const dialog = await open(page);
  await dialog.getByLabel("Anchor frame", { exact: true }).fill("1");
  await dialog.getByLabel("Known depth", { exact: true }).fill("100");
  await dialog.getByRole("button", { name: "Add anchor", exact: true }).click();
  await expect(
    dialog.getByRole("button", { name: "Remove anchor at frame 1" }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Done", exact: true }).click();
  await page
    .getByRole("button", { name: "Physical depth", exact: true })
    .click();
  const profile = page.getByTestId("panel-profile");
  await expect(profile).toContainText("1 frame with unknown depth omitted");
  await page.getByRole("button", { name: "Single frame", exact: true }).click();
  await page.getByLabel("Frame", { exact: true }).fill("2");
  await expect(page.getByLabel("Frame", { exact: true })).toHaveValue("2");
  await expect(profile).toContainText("1 frame with unknown depth omitted");
  const data = await page.evaluate(async () => {
    const [state] = await (await fetch("/api/v1/analyses")).json();
    return (
      await fetch(`/api/v1/analyses/${state.id}/data?panels=front,profile`)
    ).json();
  });
  expect(data.panels.profile.acquisition_frames).toEqual([0, 1]);
  expect(data.panels.profile.series[0].values).toHaveLength(2);
  expect(data.panels.front.acquisition_frames).toEqual([0, 1]);
  expect(errors).toEqual([]);
});
