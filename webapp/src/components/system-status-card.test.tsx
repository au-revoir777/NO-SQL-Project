import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SystemStatusCard } from "@/components/system-status-card";
import { jsonResponse, renderWithProviders } from "@/test/render";

// Test fixture shaped like GET /api/v1/health (not a result).
const HEALTH_FIXTURE = {
  status: "degraded",
  version: "0.2.0",
  api_version: "v1",
  db_revision: "0001",
  components: [
    { name: "api", status: "ok", detail: null },
    { name: "app_db", status: "ok", detail: null },
    { name: "neo4j", status: "unavailable", detail: null },
    { name: "redis", status: "not_configured", detail: null },
  ],
};

describe("SystemStatusCard", () => {
  it("shows a skeleton while loading", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise(() => {}));
    renderWithProviders(<SystemStatusCard />);
    expect(screen.getByLabelText("Loading system status")).toHaveAttribute("aria-busy", "true");
  });

  it("lists each component with an icon-and-text status", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(HEALTH_FIXTURE));
    renderWithProviders(<SystemStatusCard />);
    expect(await screen.findByText("App database")).toBeInTheDocument();
    expect(screen.getAllByText("OK")).toHaveLength(2);
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.getByText("Not configured")).toBeInTheDocument();
    expect(screen.getByText("0001")).toBeInTheDocument();
  });

  it("shows the error envelope's message and request id, and retries", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: "internal_error",
              message: "Internal server error",
              request_id: "req-123",
            },
          },
          500,
          { "x-request-id": "req-123" },
        ),
      )
      .mockResolvedValueOnce(jsonResponse(HEALTH_FIXTURE));
    renderWithProviders(<SystemStatusCard />);
    expect(await screen.findByText("Cannot reach the API")).toBeInTheDocument();
    expect(screen.getByText("Internal server error")).toBeInTheDocument();
    expect(screen.getByText("Request id: req-123")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("App database")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
