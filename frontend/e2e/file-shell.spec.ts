import { test, expect } from "@playwright/test";
test("file shell has independent tabs without workspace or manual reconnect controls", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `files-${Date.now()}` });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Open TOFexplorer (.h5) file" }),
  ).toBeEnabled();
  await expect(page.getByLabel("Workspace", { exact: true })).toHaveCount(0);
  await expect(
    page.getByText("Reconnect an existing analysis", { exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).dblclick();
  await page.getByRole("button", { name: "Open TOFexplorer file" }).click();
  await page.getByRole("button", { name: "◫ b.h5" }).dblclick();
  await page.getByRole("tab", { name: "1 · a.h5" }).click();
  page.on("dialog", (dialog) => void dialog.accept());
  await page.reload();
  await expect(page.getByRole("tab")).toHaveCount(2);
  await expect(page.getByRole("tab", { name: "1 · a.h5" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
});
