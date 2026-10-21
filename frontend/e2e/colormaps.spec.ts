import { test, expect } from "@playwright/test";

test("colormaps are selectable and restored, image selections have contrasting edges", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-tofscope-user": `colors-${Date.now()}` });
  await page.goto("/");
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "◫ a.h5", exact: true }).dblclick();
  await page
    .getByRole("button", { name: "Image display settings", exact: true })
    .click();
  const selector = page.getByLabel("SIMS colormap", { exact: true });
  await expect(selector).toHaveValue("viridis");
  await expect(selector.locator('option[value="ion"]')).toHaveCount(0);
  await selector.selectOption("cividis");
  await expect(page.getByTestId("panel-ion")).toHaveAttribute(
    "data-palette",
    "cividis",
  );
  await expect(page.getByTestId("panel-front")).toHaveAttribute(
    "data-palette",
    "cividis",
  );
  await selector.selectOption("magma");
  await expect(page.getByTestId("panel-ion")).toHaveAttribute(
    "data-palette",
    "magma",
  );
  const state = await page.evaluate(
    async () => (await (await fetch("/api/v1/analyses")).json())[0],
  );
  expect(state.display.colormap).toBe("magma");
  const values = await page.evaluate(
    async (id) =>
      (
        await (
          await fetch(`/api/v1/analyses/${id}/data?panels=ion,front`)
        ).json()
      ).panels,
    state.id,
  );
  expect(values.ion.palette).toBe("magma");
  expect(values.front.palette).toBe("magma");
  await page
    .getByRole("button", { name: "Close Image display", exact: true })
    .click();
  const front = page
    .getByTestId("panel-front")
    .getByLabel("Front projection selection");
  await front.hover();
  const b = (await front.boundingBox())!;
  await page.mouse.move(b.x + b.width * 0.2, b.y + b.height * 0.2);
  await page.mouse.down();
  await page.mouse.move(b.x + b.width * 0.8, b.y + b.height * 0.8);
  await page.mouse.up();
  await expect(front.locator('[data-action="move"]')).toHaveAttribute(
    "fill",
    "transparent",
  );
  await expect(front.locator("[data-selection-halo]").first()).toHaveAttribute(
    "stroke",
    "#095a63",
  );
  await expect(front.locator("[data-selection-edge]").first()).toHaveAttribute(
    "stroke",
    "#22e6ee",
  );
  await page
    .getByRole("button", { name: "Image display settings", exact: true })
    .click();
  for (const [palette, color, halo] of [
    ["gray", "#00b8a9", "#064d49"],
    ["viridis", "#f02ec4", "#64104e"],
    ["cividis", "#f02ec4", "#64104e"],
    ["magma", "#22e6ee", "#095a63"],
  ]) {
    await selector.selectOption(palette);
    for (const name of ["ion", "front"]) {
      const panel = page.getByTestId(`panel-${name}`);
      await expect(
        panel.locator("[data-selection-edge]").first(),
      ).toHaveAttribute("stroke", color);
      await expect(
        panel.locator("[data-selection-halo]").first(),
      ).toHaveAttribute("stroke", halo);
      await expect(panel.locator('[data-action="move"]')).toHaveAttribute(
        "fill",
        "transparent",
      );
    }
  }
  await page
    .getByRole("button", { name: "Close Image display", exact: true })
    .click();
  await page.screenshot({
    path: test.info().outputPath("colormap-selection.png"),
  });
  await page.getByRole("button", { name: "Save as…", exact: true }).click();
  await page.getByLabel("Saved filename", { exact: true }).fill("colormap.h5");
  await page.getByRole("button", { name: "Save copy", exact: true }).click();
  await expect(page.getByText("Copy saved.", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Close save dialog", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Close analysis 1", exact: true })
    .click();
  await page
    .getByRole("button", { name: /Open TOFexplorer/ })
    .first()
    .click();
  await page.getByRole("button", { name: "Saved files", exact: true }).click();
  await page
    .getByRole("button", { name: "◫ colormap.h5", exact: true })
    .dblclick();
  await page
    .getByRole("button", { name: "Image display settings", exact: true })
    .click();
  await expect(page.getByLabel("SIMS colormap", { exact: true })).toHaveValue(
    "magma",
  );
});
