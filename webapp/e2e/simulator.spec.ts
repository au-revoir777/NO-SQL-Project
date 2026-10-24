import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

import { E2E_USERS } from "../playwright.config";

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(E2E_USERS.analyst.email);
  await page.getByLabel("Password").fill(E2E_USERS.analyst.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}

test("demo_story seed 7 started from the UI gives the CLI's stream digest", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  // `fraudsim demo-story --seed 7` recorded this run; its digest is in the story JSON.
  const story = (await (await page.request.get("/api/v1/replays/00434da7845b")).json()) as {
    meta: { stream_digest: string };
  };
  await page.goto("/simulator");
  await page.getByLabel("Preset").selectOption("demo_story");
  await expect(page.getByLabel("Name", { exact: true })).toHaveValue("demo_story");
  await page.getByLabel("Seed").fill("7");
  await page.getByLabel(/^Speed \(simulated/).fill("0");
  await page.getByRole("button", { name: "Start run" }).click();
  await expect(page.getByText(/Run [0-9a-f]{12} started/)).toBeVisible();

  await expect
    .poll(
      async () => (await (await page.request.get("/api/v1/runs/current")).json()).status as string,
      { timeout: 90_000 },
    )
    .toBe("finished");
  const run = (await (await page.request.get("/api/v1/runs/current")).json()) as {
    stream_digest: string;
    scenario: string;
  };
  expect(run.scenario).toBe("demo_story");
  expect(run.stream_digest).toBe(story.meta.stream_digest);
});

test("the builder shows field errors and the page has no serious axe violations", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/simulator");
  await page.getByLabel("Preset").selectOption("baseline");
  await expect(page.getByLabel("Users", { exact: true })).not.toHaveValue("");
  await page.getByLabel("Users", { exact: true }).fill("1");
  await page.getByRole("button", { name: "Validate" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "At least 2" })).toBeVisible();
  await page.getByLabel("Users", { exact: true }).fill("120");
  // The error clears while typing, so the next click is not lost to a layout shift.
  await expect(page.getByRole("alert").filter({ hasText: "At least 2" })).toHaveCount(0);
  const [resp] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/api/v1/scenarios/validate")),
    page.getByRole("button", { name: "Validate" }).click(),
  ]);
  expect(resp.status(), await resp.text()).toBe(200);
  await expect(page.getByText(/valid · config hash [0-9a-f]{16}/)).toBeVisible();

  const { violations } = await new AxeBuilder({ page }).analyze();
  const bad = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(
    bad.map((v) => `${v.id}: ${v.help}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`),
  ).toEqual([]);
});
