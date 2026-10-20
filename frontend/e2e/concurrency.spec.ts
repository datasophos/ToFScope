import { test, expect } from "@playwright/test";
test("two users, A/B/A tabs, automatic tab recovery and denied foreign downloads", async ({
  browser,
}) => {
  const a = await browser.newContext({
      extraHTTPHeaders: { "x-tofscope-user": "concurrent-a" },
    }),
    b = await browser.newContext({
      extraHTTPHeaders: { "x-tofscope-user": "concurrent-b" },
    });
  const p = await a.newPage(),
    q = await b.newPage();
  await p.goto("/");
  const open = async (page: typeof p, name: string) => {
    await page.getByRole("button", { name: "＋ Open acquisition" }).click();
    await page.getByRole("button", { name: "◫ " + name, exact: true }).click();
    await expect(page.getByRole("tab").last()).toHaveAttribute(
      "aria-selected",
      "true",
    );
  };
  await open(p, "a.h5");
  await open(p, "b.h5");
  await open(p, "a.h5");
  await expect(p.getByRole("tab")).toHaveCount(3);
  await p
    .getByRole("button", { name: /^ROI:/ })
    .filter({ visible: true })
    .click();
  await p.getByLabel("ROI x first").filter({ visible: true }).fill("1");
  await p
    .getByRole("button", { name: "Apply ROI", exact: true })
    .filter({ visible: true })
    .click();
  await expect(
    p.getByTestId("analysis-revision").filter({ visible: true }),
  ).toHaveText("1");
  await p.getByRole("tab", { name: "1 · a.h5" }).click();
  await expect(
    p
      .getByRole("button", { name: "ROI: Full field", exact: true })
      .filter({ visible: true }),
  ).toBeVisible();
  await q.goto("/");
  await open(q, "a.h5");
  await expect(
    q.getByRole("button", { name: "ROI: Full field", exact: true }),
  ).toBeVisible();
  const analyses = await (await p.request.get("/api/v1/analyses")).json();
  const id = analyses[0].id;
  expect(
    (await q.request.get(`/api/v1/analyses/${id}/exports/csv`)).status(),
  ).toBe(404);
  const view = await a.newPage();
  await view.goto("/");
  await expect(view.getByRole("tab")).toHaveCount(3);
  await expect(
    view
      .getByRole("region", { name: "Signals", exact: true })
      .filter({ visible: true }),
  ).toBeVisible();
  await view.getByRole("tab", { name: "1 · a.h5" }).click();
  await expect(
    view
      .getByRole("button", { name: "ROI: Full field", exact: true })
      .filter({ visible: true }),
  ).toBeVisible();
  await p.getByRole("button", { name: "Close analysis 1" }).click();
  await p
    .getByRole("dialog", { name: "Unsaved changes" })
    .getByRole("button", { name: "Discard", exact: true })
    .click();
  await expect(view.getByRole("alert")).toContainText("Resource unavailable");
  await a.close();
  await b.close();
});
