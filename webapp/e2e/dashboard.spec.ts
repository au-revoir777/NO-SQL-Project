import { expect, type Page, test } from "@playwright/test";

import { E2E_USERS } from "../playwright.config";

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(E2E_USERS.analyst.email);
  await page.getByLabel("Password").fill(E2E_USERS.analyst.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}

const n0 = (x: number) => x.toLocaleString("en-US", { maximumFractionDigits: 0 });
const n1 = (x: number) => x.toLocaleString("en-US", { maximumFractionDigits: 1 });

test("a baseline run streams alerts and the KPIs equal the run-metrics endpoint", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page);
  const csrf = (await page.context().cookies()).find((c) => c.name === "fraudsim_csrf")?.value;
  const started = await page.request.post("/api/v1/runs", {
    data: { scenario: "baseline", seed: 7, speed_multiplier: 0 },
    headers: { "x-csrf-token": csrf ?? "" },
  });
  expect(started.status()).toBe(201);
  const runId = ((await started.json()) as { run_id: string }).run_id;

  const header = page.getByText(`Run ${runId}`);
  await expect(header).toBeVisible({ timeout: 30_000 });
  const feed = page.getByRole("list", { name: "Live alerts, newest first" });
  await expect(feed.getByRole("listitem").first()).toBeVisible({ timeout: 60_000 });
  // "finished" is published only after the detector has processed every event.
  await expect(header).toContainText("finished", { timeout: 60_000 });

  const m = (await (await page.request.get("/api/v1/runs/current/metrics")).json()) as {
    run_id: string;
    events_per_s: number;
    events_total: number;
    open_alerts: number;
    alerts_total: number;
    graph: { users: number };
    rings_by_status: { candidate: number; confirmed: number };
    detect_ms: { p50: number };
  };
  expect(m.run_id).toBe(runId);
  const card = (title: string) => page.locator('[data-slot="card"]', { hasText: title });
  // The last streamed sample is published when the run ends; it equals the endpoint.
  await expect(card("Events per second")).toContainText(n1(m.events_per_s));
  await expect(card("Events per second")).toContainText(`${n0(m.events_total)} events`);
  await expect(card("Graph size")).toContainText(n0(m.graph.users));
  await expect(card("Open alerts")).toContainText(`${n0(m.alerts_total)} alerts in this run`);
  await expect(card("Rings tracked")).toContainText(
    `${m.rings_by_status.candidate} candidate · ${m.rings_by_status.confirmed} confirmed`,
  );
  await expect(card("Detect latency p50")).toContainText(`${n1(m.detect_ms.p50)} ms`);

  // Oracle metrics only behind the toggle, and labelled.
  await expect(page.getByText("Ring F1 (Oracle)")).toHaveCount(0);
  await page.getByRole("button", { name: "Oracle (simulator ground truth)" }).click();
  await expect(card("Ring F1 (Oracle)")).toContainText("Oracle (simulator ground truth)");
});
