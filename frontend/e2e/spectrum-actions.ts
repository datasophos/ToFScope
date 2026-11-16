import type { Page } from "@playwright/test";

/** Open a spectrum analysis action through the visible toolbar menu. */
export async function openSpectrumAction(
  page: Page,
  name: "Create signal" | "Identify peak" | "Isotope measurements",
) {
  const panel = page.getByTestId("panel-spectrum").filter({ visible: true });
  await panel.locator("summary").filter({ hasText: "Analyze" }).click();
  await panel.getByRole("button", { name, exact: true }).click();
}
