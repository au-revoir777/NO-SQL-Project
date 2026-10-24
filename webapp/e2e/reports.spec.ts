import { readFileSync } from "node:fs";

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

async function noSeriousAxe(page: Page) {
  await page.waitForFunction(() =>
    document.getAnimations().every((a) => a.playState !== "running"),
  );
  const { violations } = await new AxeBuilder({ page }).analyze();
  const bad = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(
    bad.map((v) => `${v.id}: ${v.help}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`),
  ).toEqual([]);
}

test("generate a PDF report for a case and download it", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page);
  const csrf = async () =>
    (await page.context().cookies()).find((c) => c.name === "fraudsim_csrf")?.value ?? "";
  const run = await page.request.post("/api/v1/runs", {
    data: { scenario: "baseline", seed: 7, speed_multiplier: 0 },
    headers: { "x-csrf-token": await csrf() },
  });
  expect(run.status(), await run.text()).toBe(201);
  await expect
    .poll(
      async () => (await (await page.request.get("/api/v1/runs/current")).json()).status as string,
      { timeout: 90_000 },
    )
    .toBe("finished");
  const alerts = (await (await page.request.get("/api/v1/alerts")).json()) as {
    items: { id: number; alert_ref: string }[];
  };
  const created = await page.request.post("/api/v1/cases", {
    data: { title: "E2E report case", alert_ids: [alerts.items[0]!.id] },
    headers: { "x-csrf-token": await csrf() },
  });
  const caseId = ((await created.json()) as { id: number }).id;

  // From the case page to the builder, with the case already in scope.
  await page.goto(`/cases/${caseId}`);
  await page.getByRole("main").getByRole("link", { name: "Report", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/reports\\?case=${caseId}$`));
  await expect(page.getByLabel("Title")).toHaveValue(`Case #${caseId} investigation report`);
  await expect(page.getByRole("checkbox", { name: `#${caseId} E2E report case` })).toBeChecked();
  await noSeriousAxe(page);

  await page.getByRole("button", { name: "Generate report" }).click();
  const link = page.getByRole("link", {
    name: /^Download “Case #\d+ investigation report” \(PDF\)/,
  });
  await expect(link).toBeVisible({ timeout: 60_000 });

  const [download] = await Promise.all([page.waitForEvent("download"), link.click()]);
  expect(download.suggestedFilename()).toMatch(/\.pdf$/);
  const bytes = readFileSync((await download.path())!);
  expect(bytes.subarray(0, 5).toString()).toBe("%PDF-");
  expect(bytes.length).toBeGreaterThan(10_000);

  const href = (await link.getAttribute("href"))!;
  const res = await page.request.get(href);
  expect(res.headers()["content-type"]).toBe("application/pdf");

  // Listed with its hash; the case's alert is the one ring in the report.
  const list = page.getByRole("region", { name: "Reports" });
  const row = list.getByRole("row", { name: new RegExp(`Case #${caseId} investigation report`) });
  await expect(row).toContainText("PDF");
  await expect(row.getByRole("cell").nth(2)).toHaveText("1");
});
