import { test, expect } from "@playwright/test";

test("scientific axes are named and line plots show cursor x without changing selection", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `axes-${Date.now()}` });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  for (const name of ["ion", "front", "profile", "spectrum"]) {
    const panel = page.getByTestId(`panel-${name}`);
    await expect(panel).toHaveAttribute("data-x-axis", /\S/);
    await expect(panel).toHaveAttribute("data-y-axis", /\S/);
    await expect(panel.locator("canvas").first()).toBeVisible();
  }
  const revision = await page
    .getByTestId("analysis")
    .getAttribute("data-revision");
  for (const [name, title, label] of [
    ["profile", "Depth profile", "Frame"],
    ["spectrum", "Mass spectrum", "m/z"],
  ]) {
    const panel = page.getByTestId(`panel-${name}`);
    const overlay = panel.getByLabel(`${title} selection`);
    await overlay.scrollIntoViewIfNeeded();
    const b = (await overlay.boundingBox())!;
    await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
    const readout = panel.getByRole("tooltip");
    await expect(readout).toContainText(`${label} =`);
    await page.mouse.move(b.x + b.width * 0.7, b.y + b.height / 2);
    await expect(readout).toBeVisible();
    if (name === "profile") await expect(readout).toHaveText(/^Frame = \d+$/);
  }
  await expect(page.getByTestId("analysis")).toHaveAttribute(
    "data-revision",
    revision!,
  );
  await page
    .getByRole("button", { name: "Calibrate depth", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Depth calibration",
    exact: true,
  });
  await dialog.getByLabel("Anchor frame", { exact: true }).fill("2");
  await dialog.getByLabel("Known depth", { exact: true }).fill("100");
  await dialog.getByRole("button", { name: "Add anchor", exact: true }).click();
  await expect(
    dialog.getByRole("button", { name: "Remove anchor at frame 2" }),
  ).toBeVisible();
  await dialog
    .getByLabel("Depth display unit", { exact: true })
    .selectOption("um");
  await dialog.getByRole("button", { name: "Done", exact: true }).click();
  await page
    .getByRole("button", { name: "Physical depth", exact: true })
    .click();
  const profile = page.getByTestId("panel-profile");
  await expect(profile).toHaveAttribute("data-x-axis", "Depth (µm)");
  const overlay = profile.getByLabel("Depth profile selection");
  await overlay.scrollIntoViewIfNeeded();
  const b = (await overlay.boundingBox())!;
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
  await expect(profile.getByRole("tooltip")).toContainText("Depth = 0.05 µm");
  await expect(profile.getByRole("tooltip")).toContainText("frame 1");
  await page.screenshot({
    path: test.info().outputPath("scientific-axes.png"),
  });
  await page.getByRole("heading", { name: "a.h5", exact: true }).hover();
  await expect(profile.getByRole("tooltip")).toBeHidden();
});
