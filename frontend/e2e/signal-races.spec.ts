import { manageSignals, addSignal } from "./signal-controls";
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
  await page.getByRole("button", { name: "Add signal", exact: true }).click();
  await page
    .getByRole("listbox", { name: "Stored signals" })
    .getByRole("option")
    .first()
    .click();
  await manageSignals(page);
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

test("a stale open draft cannot overwrite a newer completed edit from another view", async ({
  page,
}) => {
  const owner = `draft-conflict-${Date.now()}`;
  await page.setExtraHTTPHeaders({ "x-tofscope-user": owner });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Choose an HDF5 acquisition" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).click();
  await addSignal(page);
  await page
    .getByRole("button", { name: "Create from spectrum", exact: true })
    .click();
  await page.getByLabel("Signal name", { exact: true }).fill("Ti");
  await page.getByLabel("Mass lower 1", { exact: true }).fill("1");
  await page.getByLabel("Mass upper 1", { exact: true }).fill("2");
  await page
    .getByRole("button", { name: "Calculate signal", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Signal editor" }),
  ).toBeHidden();
  await manageSignals(page);
  const row = page.getByTestId("signal-row").filter({ hasText: "Ti" });
  const signalId = await row.getAttribute("data-signal-id");
  await row.getByRole("button", { name: "Details", exact: true }).click();
  await page.getByRole("button", { name: "Edit signal", exact: true }).click();
  await page.getByLabel("Mass lower 1", { exact: true }).fill("1.1");
  const headers = {
    "x-tofscope-user": owner,
    Origin: new URL(page.url()).origin,
  };
  const workspaces = await (
    await page.request.get("/api/v1/workspaces", { headers })
  ).json();
  const id = workspaces[0].analysis_ids[0];
  const state = await (
    await page.request.get(`/api/v1/analyses/${id}`, { headers })
  ).json();
  const response = await page.request.post(`/api/v1/analyses/${id}/jobs`, {
    headers,
    data: {
      request_id: crypto.randomUUID(),
      expected_revision: state.revision,
      dataset_generation: state.dataset.generation,
      spec: {
        name: "Ti external",
        intervals: [[3, 4]],
        frames: [0, 2],
        signal_id: signalId,
        expected_recipe_version: 1,
      },
    },
  });
  expect(response.status()).toBe(202);
  const job = await response.json();
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(`/api/v1/jobs/${job.id}`, { headers })
          ).json()
        ).status,
    )
    .toBe("succeeded");
  await expect(row).toContainText("Ti external");
  await page
    .getByRole("button", { name: "Update signal", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Signal editor" }).getByRole("alert"),
  ).toBeVisible();
  const after = await (
    await page.request.get(`/api/v1/analyses/${id}`, { headers })
  ).json();
  expect(
    after.signals.find((s: { id: string }) => s.id === signalId).recipe
      .intervals,
  ).toEqual([[3, 4]]);
  await expect(page.getByLabel("Mass lower 1", { exact: true })).toHaveValue(
    "1.1",
  );
});
