import { test, expect } from "@playwright/test";

test("tool panel matches plot area height and scrolls its controls independently", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1600, height: 800 });
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `sidebar-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Choose an HDF5 acquisition" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).click();
  const sidebar = page.locator(".sidebar");
  const profile = page.getByTestId("panel-profile");
  await expect(profile).toBeVisible();
  const bottomDifference = async () => {
    const tools = (await sidebar.boundingBox())!;
    const plot = (await profile.boundingBox())!;
    return Math.abs(tools.y + tools.height - plot.y - plot.height);
  };
  await expect.poll(bottomDifference).toBeLessThan(2);
  await profile.evaluate((element) => (element.style.height = "440px"));
  await expect.poll(bottomDifference).toBeLessThan(2);
  expect(
    await sidebar.evaluate(
      (element) => element.scrollHeight > element.clientHeight,
    ),
  ).toBe(true);
  await sidebar.evaluate(
    (element) => (element.scrollTop = element.scrollHeight),
  );
  await page.getByLabel("Log colors", { exact: true }).scrollIntoViewIfNeeded();
  expect(
    await sidebar.evaluate((element) => element.scrollTop),
  ).toBeGreaterThan(0);
  await expect(page.getByLabel("Log colors", { exact: true })).toBeInViewport();
  await expect(
    page.getByLabel("Relative profiles", { exact: true }),
  ).toBeChecked();
  await page.setViewportSize({ width: 600, height: 800 });
  // On a narrow screen the tool panel precedes the plots at its natural height.
  await expect(
    page.getByRole("heading", { name: "Signal", exact: true }),
  ).toBeVisible();
  expect((await sidebar.boundingBox())!.height).toBeGreaterThan(400);
});
