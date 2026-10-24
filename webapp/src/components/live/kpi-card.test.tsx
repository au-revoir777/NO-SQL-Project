import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Activity } from "lucide-react";
import { describe, expect, it } from "vitest";

import type { LiveAlert } from "@/lib/live/use-live-run";

import { AlertFeed } from "./alert-feed";
import { KpiCard } from "./kpi-card";

const base = { title: "Events per second", description: "Achieved rate", icon: Activity };

describe("KpiCard", () => {
  it("shows a skeleton while loading", () => {
    render(<KpiCard {...base} state={{ kind: "loading" }} />);
    expect(screen.getByLabelText("Loading Events per second")).toHaveAttribute("aria-busy", "true");
  });

  it("says why there is no value instead of showing a number", () => {
    render(<KpiCard {...base} state={{ kind: "empty", message: "No live run yet" }} />);
    expect(screen.getByText("No live run yet")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("shows errors as an alert with an icon and text", () => {
    render(
      <KpiCard {...base} state={{ kind: "error", message: "Stream interrupted, retrying" }} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Stream interrupted, retrying");
  });

  it("shows the value, its detail and a labelled trend", () => {
    render(
      <KpiCard
        {...base}
        state={{ kind: "value", value: "42.5", detail: "1,000 events", trend: [1, 3, 2] }}
      />,
    );
    expect(screen.getByText("42.5")).toBeInTheDocument();
    expect(screen.getByText("1,000 events")).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Events per second: trend over the last 3 samples",
    );
  });
});

const alert: LiveAlert = {
  run_id: "run_1",
  ring_id: "R000004",
  kind: "alert",
  ts: "2026-01-01T00:00:27Z",
  sim_time_s: 27,
  risk: 0.92,
  threshold: 0.8,
  ring_type: "shared_device",
  status: "confirmed",
  members_count: 4,
  members: ["u1", "u2", "u3", "u4"],
  detectors: ["hub_aware"],
  top_reason: "4 accounts share one device",
};

describe("AlertFeed", () => {
  it("has an empty state", () => {
    render(<AlertFeed alerts={[]} nowSimS={null} />);
    expect(screen.getByText("No alerts in this run yet")).toBeInTheDocument();
  });

  it("lists risk, type, size, reason and simulated age; a click opens the detail", async () => {
    render(<AlertFeed alerts={[alert]} nowSimS={57} />);
    const item = screen.getByRole("button", { name: /shared device/ });
    expect(item).toHaveTextContent("0.92");
    expect(item).toHaveTextContent("4 members");
    expect(item).toHaveTextContent("4 accounts share one device");
    expect(item).toHaveTextContent("30 s ago");
    await userEvent.click(item);
    expect(await screen.findByRole("dialog")).toHaveTextContent("u1, u2, u3, u4");
    expect(screen.getByRole("dialog")).toHaveTextContent("threshold 0.80");
  });
});
