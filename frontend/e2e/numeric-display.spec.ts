import { test, expect } from "@playwright/test";
test("mass windows and calibration show compact values while submitting exact scientific inputs", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `numeric-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  await page
    .getByRole("button", { name: "Identify peak", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Atomic identification" });
  await dialog.getByLabel("Measured m/z", { exact: true }).fill("2.014");
  await dialog
    .getByRole("button", { name: "Find candidates", exact: true })
    .click();
  await dialog.getByRole("radio", { name: "H-2:+1", exact: true }).check();
  const lower = dialog.getByLabel("Window lower Th", { exact: true });
  const upper = dialog.getByLabel("Window upper Th", { exact: true });
  await lower.fill("1.387507820129395");
  await upper.fill("1.587507820129394");
  await dialog.getByRole("heading").first().click();
  await expect(lower).toHaveValue("1.3875");
  await expect(upper).toHaveValue("1.5875");
  await lower.focus();
  await expect(lower).toHaveValue("1.387507820129395");
  await dialog
    .getByRole("button", { name: "Apply window", exact: true })
    .click();
  const editor = page.getByRole("region", { name: "Signal editor" });
  await expect(editor.getByLabel("Mass lower 1", { exact: true })).toHaveValue(
    "1.39",
  );
  const integration = page.waitForRequest(
    (r) => r.url().endsWith("/jobs") && r.method() === "POST",
  );
  await editor
    .getByRole("button", { name: "Calculate signal", exact: true })
    .click();
  expect((await integration).postDataJSON().spec.intervals).toEqual([
    [1.387507820129395, 1.587507820129394],
  ]);
  await expect(editor).not.toBeVisible();
  await page
    .getByRole("button", { name: "Calibrate depth", exact: true })
    .click();
  const calibration = page.getByRole("dialog", {
    name: "Depth calibration",
    exact: true,
  });
  const known = calibration.getByLabel("Known depth", { exact: true });
  await known.fill("13.387507820129395");
  const anchor = page.waitForRequest(
    (r) =>
      r.url().endsWith("/commands") &&
      r.method() === "POST" &&
      r.postDataJSON().command.type === "set_depth_anchors",
  );
  await calibration
    .getByRole("button", { name: "Add anchor", exact: true })
    .click();
  expect((await anchor).postDataJSON().command.anchors.at(-1).depth_nm).toBe(
    13.387507820129395,
  );
  await expect(known).toHaveValue("13.3875");
  const depth = calibration.getByLabel("Depth at frame 1", { exact: true });
  await expect(depth).toHaveValue("13.3875");
  // Command state can arrive before the follow-up refresh releases the fieldset.
  // focus() does not wait for an input to become enabled.
  await expect(depth).toBeEnabled();
  await depth.focus();
  await expect(depth).toBeFocused();
  await expect(depth).toHaveValue("13.387507820129395");
  await calibration.getByRole("heading").first().click();
  await expect(calibration.locator(".anchor-summary")).toContainText(
    "13.3875 nm",
  );
  await expect(calibration.locator(".anchor-summary")).not.toContainText(
    "13.387507820129395",
  );
});
