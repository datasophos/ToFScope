import { test, expect } from "@playwright/test";
test.beforeEach(async ({ page }, info) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `races-${info.title}` });
});
async function open(page: import("@playwright/test").Page) {
  const count = await page.getByRole("tab").count();
  await page.getByRole("button", { name: "＋ Open acquisition" }).click();
  await page.getByRole("button", { name: "◫ a.h5" }).click();
  await expect(page.getByRole("tab")).toHaveCount(count + 1);
  await expect(
    page
      .getByTestId("panel-profile")
      .filter({ visible: true })
      .locator("canvas")
      .first(),
  ).toBeVisible();
}
test("keyboard navigation changes only the focused analysis", async ({
  page,
}) => {
  await page.goto("/");
  await open(page);
  await open(page);
  await page.locator("h1").filter({ visible: true }).click();
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByTestId("analysis-revision").filter({ visible: true }),
  ).toHaveText("1");
  await page.getByRole("tab", { name: "1 · a.h5" }).click();
  await expect(
    page.getByTestId("analysis-revision").filter({ visible: true }),
  ).toHaveText("0");
});
test("a newer partial response cannot hide an omitted profile update", async ({
  page,
}) => {
  await page.goto("/");
  await open(page);
  const profile = page.getByTestId("panel-profile");
  const version = await profile.getAttribute("data-content-version");
  let entered!: () => void, release!: () => void;
  const waiting = new Promise<void>((r) => (entered = r)),
    gate = new Promise<void>((r) => (release = r));
  let hold = true;
  await page.route("**/api/v1/analyses/*/data?panels=ion", async (route) => {
    if (hold) {
      hold = false;
      entered();
      await gate;
    }
    await route.continue();
  });
  await page.getByRole("button", { name: "Next frame", exact: true }).click();
  await waiting;
  await page.getByLabel("ROI x first").fill("1");
  await page.getByRole("button", { name: "Apply ROI", exact: true }).click();
  await expect(page.getByTestId("analysis-revision")).toHaveText("2");
  release();
  await expect(profile).not.toHaveAttribute("data-content-version", version!);
});
test("reloading an empty workspace does not exhaust the owner quota", async ({
  page,
}) => {
  await page.goto("/");
  for (let i = 0; i < 10; i++) {
    await expect(
      page.getByRole("button", { name: "Choose an HDF5 acquisition" }),
    ).toBeEnabled();
    await page.reload();
  }
  await expect(
    page.getByRole("button", { name: "Choose an HDF5 acquisition" }),
  ).toBeEnabled();
});

test("an expired view lease is reattached after heartbeat 404", async ({
  page,
}) => {
  await page.clock.install();
  let attaches = 0;
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().endsWith("/views")) attaches++;
  });
  await page.goto("/");
  await open(page);
  await expect.poll(() => attaches).toBe(1);
  let expired = true;
  await page.route("**/views/*/heartbeat", (route) =>
    expired
      ? ((expired = false),
        route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({
            code: "not_found",
            message: "Resource unavailable.",
          }),
        }))
      : route.continue(),
  );
  await page.clock.fastForward(16000);
  await expect.poll(() => attaches).toBe(2);
  await page.getByRole("button", { name: "Next frame" }).click();
  await expect(
    page.getByTestId("analysis-revision").filter({ visible: true }),
  ).toHaveText("1");
});
