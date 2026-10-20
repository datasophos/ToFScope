import { test, expect } from "@playwright/test";
test("signals are created independently, chosen for images, and hidden without losing identity", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({
    "x-tofscope-user": `signals-${Date.now()}`,
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Choose an HDF5 acquisition" })
    .click();
  await page.getByRole("button", { name: "◫ a.h5" }).click();
  await expect(page.getByRole("region", { name: "Signals" })).toBeVisible();
  const original = await page
    .getByRole("radio", { checked: true })
    .getAttribute("data-signal-id");
  await page
    .getByRole("button", { name: "Create from spectrum", exact: true })
    .click();
  await page.getByLabel("Signal name", { exact: true }).fill("Titanium");
  await page.getByLabel("Mass lower 1", { exact: true }).fill("1");
  await page.getByLabel("Mass upper 1", { exact: true }).fill("2");
  await page
    .getByRole("button", { name: "Calculate signal", exact: true })
    .click();
  const row = page.getByTestId("signal-row").filter({ hasText: "Titanium" });
  await expect(row.getByRole("radio")).toBeEnabled();
  await expect(page.getByRole("radio", { checked: true })).toHaveAttribute(
    "data-signal-id",
    original!,
  );
  const swatch = await row.locator(".curve-marker").getAttribute("style");
  await row.getByRole("radio").click();
  await expect(row.getByRole("radio")).toBeChecked();
  await expect(page.getByTestId("panel-ion")).toContainText("Titanium");
  await expect(row.locator(".curve-marker")).toHaveAttribute("style", swatch!);
  const first = page.getByTestId("signal-row").first();
  await first.getByRole("checkbox").click();
  await expect(first.getByRole("checkbox")).not.toBeChecked();
  await first.getByRole("checkbox").click();
  await expect(first.getByRole("checkbox")).toBeChecked();
  await row.getByRole("button", { name: "Details", exact: true }).click();
  await page.getByLabel("Rename signal", { exact: true }).fill("Ti renamed");
  await page.getByRole("button", { name: "Rename", exact: true }).click();
  await expect(page.getByTestId("panel-ion")).toContainText("Ti renamed");
});

test('stored adds deduplicate, custom edits retain identity, and duplicate starts a separate draft', async ({page})=>{
  await page.setExtraHTTPHeaders({'x-tofscope-user':`edit-flow-${Date.now()}`});
  await page.goto('/');await page.getByRole('button',{name:'Choose an HDF5 acquisition'}).click();await page.getByRole('button',{name:'◫ a.h5'}).click();
  for(let i=0;i<2;i++){await page.getByRole('button',{name:'Add stored signal',exact:true}).click();await page.getByRole('listbox',{name:'Stored signals'}).getByRole('option').first().click();await expect(page.getByTestId('signal-row')).toHaveCount(2);}
  await page.getByRole('button',{name:'Create from spectrum',exact:true}).click();await page.getByLabel('Signal name',{exact:true}).fill('Ti');await page.getByLabel('Mass lower 1',{exact:true}).fill('1');await page.getByLabel('Mass upper 1',{exact:true}).fill('2');await page.getByRole('button',{name:'Calculate signal',exact:true}).click();
  await expect(page.getByRole('region',{name:'Signal editor'})).toBeHidden();
  const row=page.getByTestId('signal-row').filter({hasText:'Ti'});const id=await row.getAttribute('data-signal-id');const style=await row.locator('.curve-marker').getAttribute('style');
  await row.getByRole('button',{name:'Details',exact:true}).click();await page.getByRole('button',{name:'Edit signal',exact:true}).click();await expect(page.getByLabel('Mass lower 1',{exact:true})).toHaveValue('1');await page.getByLabel('Signal name',{exact:true}).fill('Ti updated');await page.getByLabel('Mass lower 1',{exact:true}).fill('2');await page.getByLabel('Mass upper 1',{exact:true}).fill('3');await page.getByRole('button',{name:'Update signal',exact:true}).click();
  await expect(page.getByRole('region',{name:'Signal editor'})).toBeHidden();await expect(row).toContainText('Ti updated');await expect(row).toHaveAttribute('data-signal-id',id!);await expect(row.locator('.curve-marker')).toHaveAttribute('style',style!);
  await row.getByRole('button',{name:'Details',exact:true}).click();await page.getByRole('button',{name:'Duplicate',exact:true}).click();await expect(page.getByLabel('Signal name',{exact:true})).toHaveValue('Ti updated copy');await expect(page.getByRole('button',{name:'Calculate signal',exact:true})).toBeVisible();await page.getByRole('button',{name:'Discard',exact:true}).click();await expect(page.getByTestId('signal-row')).toHaveCount(3);
});
