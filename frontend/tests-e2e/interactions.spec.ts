import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  (page as unknown as { _consoleErrors: string[] })._consoleErrors = errors;
});

test.afterEach(async ({ page }) => {
  const errors = (page as unknown as { _consoleErrors: string[] })._consoleErrors;
  expect(errors, `Console errors: ${errors.join("\n")}`).toEqual([]);
});

test("Analyze tab: paste an example and get a hawkish result", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("tab", { name: "Analyze" })).toHaveAttribute("aria-selected", "true");

  await page.getByRole("button", { name: "Hawkish" }).click();
  await page.getByRole("button", { name: "Analyze" }).click();

  const label = page.locator(".score-gauge-label");
  await expect(label).toHaveText("HAWKISH", { timeout: 15_000 });
  await expect(label).toHaveClass(/label-hawkish/);
});

test("tabs switch between Analyze and History", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".history-section")).toHaveCount(0);

  await page.getByRole("tab", { name: "History" }).click();
  await expect(page.getByRole("tab", { name: "History" })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".lede")).toBeVisible({ timeout: 15_000 });

  await page.getByRole("tab", { name: "Analyze" }).click();
  await expect(page.locator(".history-section")).toHaveCount(0);
});

test("History chart: clicking a point opens the document drill-down", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("tab", { name: "History" }).click();

  const chart = page.locator(".timeline");
  await expect(chart).toBeVisible({ timeout: 15_000 });
  // Wait for Recharts to actually render the main chart SVG before
  // clicking, not just the wrapper div -- otherwise the click can land
  // before any data point is registered. Scoped to role="application"
  // since .timeline also contains two small legend-icon SVGs.
  await expect(chart.getByRole("application")).toBeVisible({ timeout: 15_000 });

  await expect(page.locator(".drilldown")).toHaveCount(0);

  // Click an actual rendered point -- these are real (transparent-filled)
  // SVG circles, one per document, not a blind click at some pixel
  // coordinate. `force: true` because the fill is intentionally
  // transparent, which Playwright's actionability check can otherwise
  // flag as "not visible" even though it's a real, hit-testable element.
  const point = chart.locator(".timeline-point").nth(300);
  await point.waitFor({ state: "attached", timeout: 15_000 });
  await point.click({ force: true });

  const drilldown = page.locator(".drilldown");
  await expect(drilldown).toBeVisible({ timeout: 15_000 });
  await expect(drilldown.locator(".drilldown-text")).not.toBeEmpty();

  await drilldown.locator(".drilldown-close").click();
  await expect(drilldown).toHaveCount(0);
});
