import { test, expect } from "@playwright/test";
test("old image data keeps its own label during a delayed signal switch", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `signal-race-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Choose an HDF5 acquisition" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).click();
  const ion = page.getByTestId("panel-ion");
  await expect(ion.locator("canvas").first()).toBeVisible();
  const before = await ion.locator(".plot-status").innerText();
  await page
    .getByRole("button", { name: "Add stored signal", exact: true })
    .click();
  await page
    .getByRole("listbox", { name: "Stored signals" })
    .getByRole("option")
    .first()
    .click();
  await expect(page.getByTestId("signal-row")).toHaveCount(2);
  const row = page.getByTestId("signal-row").last();
  let entered!: () => void, release!: () => void;
  const waiting = new Promise<void>((r) => (entered = r)),
    gate = new Promise<void>((r) => (release = r));
  let hold = true;
  await page.route("**/analyses/*/data?*", async (route) => {
    if (
      hold &&
      new URL(route.request().url()).searchParams.get("panels")?.includes("ion")
    ) {
      hold = false;
      entered();
      await gate;
    }
    await route.continue();
  });
  await row.getByRole("radio").click();
  await waiting;
  await expect(ion.locator(".plot-status")).toContainText(before);
  await expect(ion.locator(".plot-status")).toContainText("Updating");
  release();
  await expect(ion.locator(".plot-status")).not.toContainText("Updating");
  await expect(row.getByRole("radio")).toBeChecked();
  expect(await ion.locator(".plot-status").innerText()).not.toEqual(before);
});
