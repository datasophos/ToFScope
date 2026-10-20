import { test, expect } from "@playwright/test";

test("save a copy restores signal and display state and downloads only on request", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `saved-${Date.now()}` });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).dblclick();
  await page
    .getByTestId("panel-spectrum")
    .getByRole("button", { name: "Use linear y scale", exact: true })
    .click();
  await page
    .getByTestId("profile-chip")
    .first()
    .getByRole("button")
    .first()
    .click();
  await page.getByLabel("Rename signal", { exact: true }).fill("Aluminium");
  await page
    .getByRole("button", { name: "Save signal name", exact: true })
    .click();
  const downloads: string[] = [];
  page.on("download", (d) => downloads.push(d.suggestedFilename()));
  await page.getByRole("button", { name: "Save as…", exact: true }).click();
  await page.getByLabel("Saved filename", { exact: true }).fill("aluminium.h5");
  await page.getByRole("button", { name: "Save copy", exact: true }).click();
  await expect(page.getByText("Copy saved.", { exact: true })).toBeVisible();
  expect(downloads).toEqual([]);
  await expect(
    page.getByText(/Large files may take a long time to download/),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download copy", exact: true }).click();
  expect((await download).suggestedFilename()).toBe("aluminium.h5");
  await page
    .getByRole("button", { name: "Close save dialog", exact: true })
    .click();
  await expect(page.getByTestId("save-state")).toHaveText("Saved");
  await page
    .getByRole("button", { name: "Close analysis 1", exact: true })
    .click();
  await expect(page.getByRole("tab")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await page.getByRole("button", { name: "Saved files", exact: true }).click();
  await page
    .getByRole("button", { name: "◫ aluminium.h5", exact: true })
    .dblclick();
  await expect(page.getByTestId("profile-chip")).toContainText("Aluminium");
  await expect(page.getByTestId("panel-spectrum")).toHaveAttribute(
    "data-y-scale",
    "linear",
  );
  await expect(page.getByTestId("save-state")).toHaveText("Saved");
});

test("a clean saved analysis still protects an uncommitted draft on close", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `close-${Date.now()}` });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).dblclick();
  await page.getByRole("button", { name: "Save as…", exact: true }).click();
  await page.getByRole("button", { name: "Save copy", exact: true }).click();
  await expect(page.getByText("Copy saved.", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Close save dialog", exact: true })
    .click();
  await page
    .getByTestId("panel-spectrum")
    .getByRole("button", { name: "Create signal", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Save as…", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Close analysis 1", exact: true })
    .click();
  const prompt = page.getByRole("dialog", {
    name: "Unsaved changes",
    exact: true,
  });
  await expect(prompt).toBeVisible();
  await prompt.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("tab")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Close analysis 1", exact: true })
    .click();
  await prompt.getByRole("button", { name: "Discard", exact: true }).click();
  await expect(page.getByRole("tab")).toHaveCount(0);
});

test("close can save a new copy and filename collisions retain the unsaved analysis", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `save-close-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).dblclick();
  await page
    .getByRole("button", { name: "Close analysis 1", exact: true })
    .click();
  await page
    .getByRole("dialog", { name: "Unsaved changes", exact: true })
    .getByRole("button", { name: "Save as…", exact: true })
    .click();
  await page.getByLabel("Saved filename", { exact: true }).fill("closed.h5");
  await page.getByRole("button", { name: "Save copy", exact: true }).click();
  await expect(page.getByRole("tab")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).dblclick();
  await page.getByRole("button", { name: "Save as…", exact: true }).click();
  await page.getByLabel("Saved filename", { exact: true }).fill("closed.h5");
  await page.getByRole("button", { name: "Save copy", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "Save a copy" }).getByRole("alert"),
  ).toBeVisible();
  await expect(page.getByLabel("Saved filename", { exact: true })).toHaveValue(
    "closed.h5",
  );
  await expect(page.getByTestId("save-state")).toHaveText("Unsaved changes");
  await expect(page.getByText("Copy saved.", { exact: true })).toHaveCount(0);
  await page.getByLabel("Saved filename", { exact: true }).fill("another.h5");
  await page.getByRole("button", { name: "Save copy", exact: true }).click();
  await expect(page.getByText("Copy saved.", { exact: true })).toBeVisible();
});

test("hidden union results reopen with exact profiles and no new integration", async ({
  page,
}) => {
  const owner = `union-save-${Date.now()}`;
  await page.setExtraHTTPHeaders({ "x-tofscope-user": owner });
  let integrations = 0;
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().endsWith("/jobs")) integrations++;
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).dblclick();
  await page
    .getByTestId("panel-spectrum")
    .getByRole("button", { name: "Create signal", exact: true })
    .click();
  await page.getByLabel("Signal name", { exact: true }).fill("Union");
  await page.getByLabel("Mass lower 1", { exact: true }).fill("1");
  await page.getByLabel("Mass upper 1", { exact: true }).fill("2");
  await page.getByRole("button", { name: "Add interval", exact: true }).click();
  await page.getByLabel("Mass lower 2", { exact: true }).fill("3");
  await page.getByLabel("Mass upper 2", { exact: true }).fill("4");
  await page.getByLabel("Calculation first", { exact: true }).fill("1");
  await page
    .getByRole("button", { name: "Calculate signal", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Signal editor" }),
  ).toBeHidden();
  const profiles = async () => {
    const states = await (
      await page.request.get("/api/v1/analyses", {
        headers: { "x-tofscope-user": owner },
      })
    ).json();
    const data = await (
      await page.request.get(
        `/api/v1/analyses/${states[0].id}/data?panels=profile`,
        { headers: { "x-tofscope-user": owner } },
      )
    ).json();
    return data.panels.profile.series.map(
      (s: { label: string; values: unknown }) => ({
        label: s.label,
        values: s.values,
      }),
    );
  };
  const before = await profiles();
  await page
    .getByTestId("profile-chip")
    .filter({ hasText: "Union" })
    .getByRole("button", { name: "Hide Union profile", exact: true })
    .click();
  await expect(page.getByTestId("profile-chip")).toHaveCount(1);
  await page.getByRole("button", { name: "Save as…", exact: true }).click();
  await page.getByLabel("Saved filename", { exact: true }).fill("union.h5");
  await page.getByRole("button", { name: "Save copy", exact: true }).click();
  await expect(page.getByText("Copy saved.", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Close save dialog", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Close analysis 1", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await page.getByRole("button", { name: "Saved files", exact: true }).click();
  await page
    .getByRole("button", { name: "◫ union.h5", exact: true })
    .dblclick();
  await expect(page.getByTestId("profile-chip")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Manage signals", exact: true })
    .click();
  const row = page.getByTestId("signal-row").filter({ hasText: "Union" });
  await expect(row).toContainText("frames 1–2");
  await expect(row.getByRole("checkbox")).not.toBeChecked();
  await row.getByRole("checkbox").click();
  await expect(row.getByRole("checkbox")).toBeChecked();
  expect(await profiles()).toEqual(before);
  expect(integrations).toBe(1);
});

test("file picker and save dialog show configured folders and exact save destination", async ({
  page,
}) => {
  const owner = `folders-${Date.now()}`;
  await page.setExtraHTTPHeaders({ "x-tofscope-user": owner });
  await page.goto("/");
  const response = await page.request.get("/api/v1/locations", {
    headers: { "x-tofscope-user": owner },
  });
  expect(response.ok()).toBeTruthy();
  const folders = await response.json();
  await page
    .getByRole("button", { name: "Open TOFexplorer (.h5) file" })
    .click();
  await expect(page.getByTestId("folder-acquisitions")).toHaveAttribute(
    "title",
    folders.acquisitions,
  );
  await expect(page.getByTestId("folder-saved-copies")).toHaveAttribute(
    "title",
    folders.saved_copies,
  );
  await page.getByRole("button", { name: "◫ a.h5" }).dblclick();
  await page.getByRole("button", { name: "Save as…", exact: true }).click();
  await expect(page.getByTestId("folder-saved-copies")).toHaveAttribute(
    "title",
    folders.saved_copies,
  );
  await expect(page.getByTestId("save-destination")).toHaveAttribute(
    "title",
    `${folders.save_destination}/a_analysis.h5`,
  );
});
