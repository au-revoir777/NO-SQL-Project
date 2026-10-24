import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AlertQueue } from "@/components/cases/alert-queue";
import { jsonResponse, renderWithProviders } from "@/test/render";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

// Test fixtures shaped like the /api/v1 responses (not results).
function alert(id: number, status: string, risk: number) {
  return {
    id,
    run_id: "run-fixture",
    alert_ref: `R${String(id).padStart(4, "0")}`,
    kind: "alert",
    status,
    assignee: null,
    ring_type: "shared_device",
    ring_status: "alert",
    risk,
    threshold: 0.8,
    calibration_bucket: "0.8-0.9",
    members_count: 4,
    detectors: ["hub_aware"],
    reason: "fixture",
    first_seen_at: "2026-01-01T00:00:00Z",
    last_seen_at: "2026-01-01T00:01:00Z",
    sim_time_s: 10,
    latest_label: null,
    case_ids: [],
  };
}
const ALERTS = [alert(1, "new", 0.93), alert(2, "new", 0.88), alert(3, "triaged", 0.81)];
const USERS = [{ id: 7, email: "analyst@example.org", display_name: "Ana" }];

let requests: { method: string; url: URL; body: unknown }[] = [];

beforeEach(() => {
  requests = [];
  push.mockReset();
  document.cookie = "fraudsim_csrf=test-token";
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const req = input as Request;
    const url = new URL(req.url);
    const body = req.method === "GET" ? null : await req.clone().json();
    requests.push({ method: req.method, url, body });
    if (url.pathname === "/api/v1/alerts")
      return jsonResponse({ items: ALERTS, next_cursor: null, total: ALERTS.length });
    if (url.pathname === "/api/v1/alerts/views") return jsonResponse([]);
    if (url.pathname === "/api/v1/users") return jsonResponse(USERS);
    if (url.pathname === "/api/v1/alerts/bulk")
      return jsonResponse({ updated: (body as { ids: number[] }).ids, rejected: [] });
    if (url.pathname === "/api/v1/cases") return jsonResponse({ items: [], next_cursor: null });
    return jsonResponse({ error: { code: "not_found", message: "nope" } }, 404);
  });
});

const listCalls = () => requests.filter((r) => r.url.pathname === "/api/v1/alerts");

describe("AlertQueue", () => {
  it("lists alerts and sends the default filters", async () => {
    renderWithProviders(<AlertQueue />);
    expect(await screen.findByRole("link", { name: "R0001" })).toBeInTheDocument();
    const q = listCalls()[0]!.url.searchParams;
    expect(q.getAll("status")).toEqual(["new", "triaged", "escalated"]);
    expect(q.get("sort")).toBe("risk");
  });

  it("validates the risk range and applies only valid filters", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AlertQueue />);
    await screen.findByRole("link", { name: "R0001" });
    const min = screen.getByLabelText("Risk from");
    await user.type(min, "2");
    expect(await screen.findByText("Between 0 and 1")).toBeInTheDocument();
    expect(min).toHaveAttribute("aria-invalid", "true");
    await new Promise((r) => setTimeout(r, 400));
    expect(listCalls().some((r) => r.url.searchParams.get("risk_min") === "1")).toBe(false);
    await user.clear(min);
    await user.type(min, "0.85");
    await waitFor(() =>
      expect(listCalls().some((r) => r.url.searchParams.get("risk_min") === "0.85")).toBe(true),
    );
    await user.click(screen.getByRole("button", { name: "closed", pressed: false }));
    await waitFor(() =>
      expect(listCalls().at(-1)!.url.searchParams.getAll("status")).toContain("closed"),
    );
  });

  it("selects a range with shift-click and sets the status in bulk", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AlertQueue />);
    await screen.findByRole("link", { name: "R0001" });
    await user.click(screen.getByRole("checkbox", { name: "Select alert R0001" }));
    await user.keyboard("{Shift>}");
    await user.click(screen.getByRole("checkbox", { name: "Select alert R0003" }));
    await user.keyboard("{/Shift}");
    const bar = screen.getByRole("region", { name: "Bulk actions" });
    expect(within(bar).getByText("3 selected")).toBeInTheDocument();

    await user.click(within(bar).getByRole("combobox", { name: "Set status of selected alerts" }));
    await user.click(await screen.findByRole("option", { name: "escalated" }));
    await waitFor(() =>
      expect(requests.find((r) => r.url.pathname === "/api/v1/alerts/bulk")?.body).toEqual({
        ids: [1, 2, 3],
        action: "status",
        status: "escalated",
      }),
    );
    expect(screen.queryByRole("region", { name: "Bulk actions" })).not.toBeInTheDocument();
  });

  it("moves with j/k and opens the focused alert with Enter", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AlertQueue />);
    await screen.findByRole("link", { name: "R0001" });
    await user.click(document.body);
    await user.keyboard("j");
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[1]).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(push).toHaveBeenCalledWith("/alerts/2");
  });
});
