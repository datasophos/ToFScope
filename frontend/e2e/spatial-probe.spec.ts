import { test, expect } from "@playwright/test";
test("compare spatial geometry on the same registered fixture", async ({
  page,
}) => {
  await page.goto("/evaluation/spatial.html");
  await page.waitForFunction(() => !!(window as any).spatialProbe);
  const result = await page.evaluate(() => (window as any).spatialProbe);
  expect(result.plotlyZ).toEqual([0, 10, 30, 60]);
  expect(result.vtkZ).toEqual([0, 20, 40, 60]);
  expect(result.vtkInputClass).toBe("vtkImageData");
  console.log(JSON.stringify(result));
  await page.screenshot({
    path: test.info().outputPath("renderer-comparison.png"),
  });
});
