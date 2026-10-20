import { test, expect } from "@playwright/test";

async function openPicker(page: import("@playwright/test").Page) {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `explorer-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file", exact: true })
    .click();
  return page.getByRole("dialog", { name: "Open TOFexplorer file" });
}

test("file explorer uses compact locations, tooltips and explicit file selection", async ({
  page,
}) => {
  const acquisitions = "/a/very/long/server/path/2025-12-05_example_datasets";
  const saved = "/another/long/server/path/Saved copies";
  await page.route("**/api/v1/locations", (route) =>
    route.fulfill({
      json: {
        acquisitions,
        saved_copies: saved,
        save_destination: saved + "/owner",
      },
    }),
  );
  const dialog = await openPicker(page);
  await expect(dialog.getByRole("table", { name: "Files" })).toBeVisible();
  await expect(dialog).not.toContainText("Files remain on this server");
  await expect(dialog).not.toContainText("/a/very/long");
  await expect(page.getByTestId("folder-acquisitions")).toHaveText(
    "2025-12-05_example_datasets",
  );
  await expect(page.getByTestId("folder-acquisitions")).toHaveAttribute(
    "title",
    acquisitions,
  );
  await expect(page.getByTestId("folder-saved-copies")).toHaveText(
    "Saved copies",
  );
  await expect(page.getByTestId("folder-saved-copies")).toHaveAttribute(
    "title",
    saved,
  );
  await dialog.screenshot({
    path: test.info().outputPath("file-explorer-desktop.png"),
  });
  await test.info().attach("file-explorer-desktop", {
    body: await dialog.screenshot(),
    contentType: "image/png",
  });
  await expect(
    dialog.getByRole("button", { name: "Open", exact: true }),
  ).toBeDisabled();
  const openButton = await dialog
    .getByRole("button", { name: "Open", exact: true })
    .boundingBox();
  const cancelButton = await dialog
    .getByRole("button", { name: "Cancel", exact: true })
    .boundingBox();
  expect(openButton!.width).toBeLessThan(140);
  expect(Math.abs(openButton!.y - cancelButton!.y)).toBeLessThan(2);
  await dialog.getByRole("button", { name: "◫ a.h5", exact: true }).click();
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole("row").filter({
      has: page.getByRole("button", { name: "◫ a.h5", exact: true }),
    }),
  ).toHaveAttribute("aria-selected", "true");
  await dialog.getByRole("button", { name: "Open", exact: true }).click();
  await expect(page.getByRole("tab", { name: "1 · a.h5" })).toBeVisible();
});

test("breadcrumbs, search and keyboard opening behave like a file explorer", async ({
  page,
}) => {
  const dialog = await openPicker(page);
  await dialog
    .getByRole("button", { name: "▸ nested", exact: true })
    .dblclick();
  const crumbs = dialog.getByRole("navigation", { name: "Folder path" });
  await expect(
    crumbs.getByRole("button", { name: "nested", exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "◫ c.h5", exact: true }),
  ).toBeVisible();
  await dialog
    .getByRole("button", { name: "Parent folder", exact: true })
    .click();
  await expect(
    dialog.getByRole("button", { name: "Parent folder", exact: true }),
  ).toBeDisabled();
  await dialog
    .getByRole("textbox", { name: "Search files" })
    .fill("no-such-file");
  await expect(
    dialog.getByText("No matching files.", { exact: true }),
  ).toBeVisible();
  await dialog.getByRole("textbox", { name: "Search files" }).fill("");
  await dialog.getByRole("button", { name: "◫ a.h5", exact: true }).focus();
  await page.keyboard.press("ArrowDown");
  await expect(
    dialog.getByRole("button", { name: "◫ b.h5", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("tab", { name: "1 · b.h5" })).toBeVisible();
});

test("file explorer fits a narrow screen and Escape restores focus", async ({
  page,
}) => {
  await page.setViewportSize({ width: 560, height: 700 });
  const dialog = await openPicker(page);
  await expect(dialog.getByRole("table", { name: "Files" })).toBeVisible();
  expect(
    await dialog.evaluate((node) => node.scrollWidth <= node.clientWidth),
  ).toBe(true);
  const box = (await dialog.boundingBox())!;
  expect(box.height).toBeLessThan(700);
  await dialog.screenshot({
    path: test.info().outputPath("file-explorer-narrow.png"),
  });
  await test.info().attach("file-explorer-narrow", {
    body: await dialog.screenshot(),
    contentType: "image/png",
  });
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByRole("button", {
      name: "Open TOFexplorer (.h5) file",
      exact: true,
    }),
  ).toBeFocused();
});
