import { test, expect } from "@playwright/test";

test("signal rename uses a spaced label and a confirmation only for edited names", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `rename-${Date.now()}` });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).dblclick();
  const chip = page.getByTestId("profile-chip").first();
  await chip.getByRole("button").first().click();
  const input = page.getByLabel("Rename signal", { exact: true });
  const original = await input.inputValue();
  const save = page.getByRole("button", {
    name: "Save signal name",
    exact: true,
  });
  await expect(
    page.getByRole("button", { name: "Rename", exact: true }),
  ).toHaveCount(0);
  await expect(save).toHaveCount(0);
  const labelBox = (await page
    .locator(".signal-rename > label")
    .boundingBox())!;
  const inputBox = (await input.boundingBox())!;
  expect(inputBox.y - labelBox.y - labelBox.height).toBeGreaterThanOrEqual(6);
  await input.fill("Renamed channel");
  await expect(save).toBeVisible();
  await input.fill(original);
  await expect(save).toHaveCount(0);
  await input.fill("   ");
  await expect(save).toBeDisabled();
  await input.fill("Renamed channel");
  await save.click();
  await expect(input).toHaveCount(0);
  await expect(chip).toContainText("Renamed channel");
  await chip.getByRole("button").first().click();
  await input.fill("Saved with Enter");
  await input.press("Enter");
  await expect(input).toHaveCount(0);
  await expect(chip).toContainText("Saved with Enter");
});
