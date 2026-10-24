import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

import { E2E_USERS } from "../playwright.config";

async function signIn(page: Page, who: keyof typeof E2E_USERS) {
  await page.context().clearCookies();
  await page.goto("/login");
  await page.getByLabel("Email").fill(E2E_USERS[who].email);
  await page.getByLabel("Password").fill(E2E_USERS[who].password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}

async function noSeriousAxe(page: Page) {
  // A toast measured mid fade-in has low contrast (seen on the CI runner): let
  // running animations and transitions finish first.
  await page.waitForFunction(() =>
    document.getAnimations().every((a) => a.playState !== "running"),
  );
  const { violations } = await new AxeBuilder({ page }).analyze();
  const bad = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(
    bad.map((v) => `${v.id}: ${v.help}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`),
  ).toEqual([]);
}

/** A baseline run (seed 7, as fast as possible) so the queue has recorded alerts. */
async function runBaseline(page: Page) {
  const csrf = (await page.context().cookies()).find((c) => c.name === "fraudsim_csrf")?.value;
  const res = await page.request.post("/api/v1/runs", {
    data: { scenario: "baseline", seed: 7, speed_multiplier: 0 },
    headers: { "x-csrf-token": csrf ?? "" },
  });
  expect(res.status(), await res.text()).toBe(201);
  await expect
    .poll(
      async () => (await (await page.request.get("/api/v1/runs/current")).json()).status as string,
      { timeout: 90_000 },
    )
    .toBe("finished");
}

test("analyst triages an alert into an escalated case; admin sees it in the audit view", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page, "analyst");
  await runBaseline(page);

  // Queue: the highest-risk open alert first.
  await page.goto("/alerts");
  await expect(page.getByRole("heading", { name: "Alerts", level: 1 })).toBeVisible();
  const first = page.getByRole("table").getByRole("link").first();
  await expect(first).toBeVisible();
  await noSeriousAxe(page);
  const ref = (await first.textContent())!.trim();
  await first.click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(ref);

  // Evidence has a table alternative.
  await page.getByRole("tab", { name: "Evidence" }).click();
  await page.getByRole("button", { name: "Show as table" }).click();
  await expect(page.getByText("Shared attributes (degree")).toBeVisible();

  // Note and label.
  await page.getByRole("tab", { name: "Activity" }).click();
  await noSeriousAxe(page);
  await page.getByLabel("Add a note").fill("Checked the shared device: four new accounts.");
  await page.getByRole("button", { name: "Add note" }).click();
  await expect(
    page.getByRole("list", { name: "Notes" }).getByText("four new accounts"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Confirmed fraud" }).click();
  // The run is still the API's current run, so the label feeds its alert policy.
  await expect(
    page.getByText("Feedback applied to the live run's alert policy.").first(),
  ).toBeVisible();
  await expect(page.getByText(/Threshold for .*→/)).toBeVisible();
  await expect(
    page.getByRole("list", { name: "Label history" }).getByText(/Confirmed fraud by/),
  ).toBeVisible();

  // Case from the alert, then escalate it.
  await page.getByRole("button", { name: "Create case" }).click();
  await page.getByLabel("Title").fill(`E2E ring ${ref}`);
  await page.getByRole("dialog").getByRole("button", { name: "Create case" }).click();
  await expect(page).toHaveURL(/\/cases\/\d+$/);
  const caseId = page.url().split("/").pop()!;
  await expect(page.getByRole("heading", { level: 1 })).toContainText(`Case #${caseId}`);
  await expect(page.getByRole("button", { name: `Show frozen evidence of ${ref}` })).toBeVisible();
  await page.getByRole("combobox", { name: "Move to" }).click();
  await page.getByRole("option", { name: "escalated" }).click();
  await page.getByRole("button", { name: "Update status" }).click();
  await expect(page.getByText("Case moved to escalated.")).toBeVisible();
  await noSeriousAxe(page);

  // Closing without a resolution is refused in the form.
  await page.getByRole("combobox", { name: "Move to" }).click();
  await page.getByRole("option", { name: "closed" }).click();
  await page.getByRole("button", { name: "Update status" }).click();
  await expect(page.getByText("Say how the case was resolved before closing it")).toBeVisible();

  // Admin: the case's history is in the audit trail and the chain verifies.
  await signIn(page, "admin");
  await page.goto("/audit");
  await expect(page.getByText("Hash chain intact")).toBeVisible();
  await page.getByLabel("Object").fill(`case:${caseId}`);
  const rows = page.getByRole("table").getByRole("row");
  await expect(rows.filter({ hasText: "CASE_UPDATED" })).toHaveCount(1);
  await expect(rows.filter({ hasText: "CASE_CREATED" })).toHaveCount(1);
  await expect(rows.filter({ hasText: E2E_USERS.analyst.email }).first()).toBeVisible();
  await noSeriousAxe(page);
});

test("audit and alert tables stay accessible when they scroll sideways (narrow window)", async ({
  page,
}) => {
  await page.setViewportSize({ width: 820, height: 900 });
  await signIn(page, "admin");
  await page.goto("/audit");
  await expect(page.getByText("Hash chain intact")).toBeVisible();
  await noSeriousAxe(page);
  await page.goto("/alerts");
  await expect(page.getByRole("heading", { name: "Alerts", level: 1 })).toBeVisible();
  await noSeriousAxe(page);
});

test("the cases list has no serious axe violations", async ({ page }) => {
  await signIn(page, "analyst");
  await page.goto("/cases");
  await expect(page.getByRole("heading", { name: "Cases", level: 1 })).toBeVisible();
  await noSeriousAxe(page);
});
