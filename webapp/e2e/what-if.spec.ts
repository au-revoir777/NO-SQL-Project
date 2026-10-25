import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

import { E2E_USERS } from "../playwright.config";

async function signIn(page: Page) {
  await page.context().clearCookies();
  await page.goto("/login");
  await page.getByLabel("Email").fill(E2E_USERS.analyst.email);
  await page.getByLabel("Password").fill(E2E_USERS.analyst.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}

test("what-if: applying a counterfactual flips the decision", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page);
  const csrf = (await page.context().cookies()).find((c) => c.name === "fraudsim_csrf")?.value;
  await page.request.post("/api/v1/runs", {
    data: { scenario: "baseline", seed: 7, speed_multiplier: 0 },
    headers: { "x-csrf-token": csrf ?? "" },
  });
  await expect
    .poll(
      async () => (await (await page.request.get("/api/v1/runs/current")).json()).status as string,
      { timeout: 90_000 },
    )
    .toBe("finished");
  // An alert that has a model counterfactual (found through the API, not hard-coded).
  const alerts = (await (await page.request.get("/api/v1/alerts?risk_min=0.8")).json()) as {
    items: { id: number }[];
  };
  let target: number | null = null;
  for (const a of alerts.items) {
    const r = await page.request.post(`/api/v1/alerts/${a.id}/what-if`, {
      data: {},
      headers: { "x-csrf-token": csrf ?? "" },
    });
    if (((await r.json()) as { counterfactuals: unknown[] }).counterfactuals.length) {
      target = a.id;
      break;
    }
  }
  test.skip(target === null, "no alert with a model counterfactual in this run");

  await page.goto(`/alerts/${target}`);
  await page.getByRole("tab", { name: "What-if" }).click();
  await expect(page.getByText("Score with your changes")).toBeVisible();
  await expect(page.getByText("alert", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Apply" }).first().click();
  await expect(page.getByText("decision flips")).toBeVisible();
  await expect(page.getByText("below threshold")).toBeVisible();
  await page.waitForFunction(() =>
    document.getAnimations().every((a) => a.playState !== "running"),
  );
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(
    violations
      .filter((v) => v.impact === "serious" || v.impact === "critical")
      .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`),
  ).toEqual([]);
  await page.getByRole("button", { name: "Reset to the scored values" }).click();
  await expect(page.getByText("decision flips")).toHaveCount(0);
});
