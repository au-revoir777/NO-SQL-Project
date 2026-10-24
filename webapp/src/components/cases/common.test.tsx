import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ActivityList, parseTime } from "./common";

describe("parseTime", () => {
  it("reads naive API times as UTC and keeps explicit offsets", () => {
    expect(parseTime("2026-10-25T00:24:45.123").toISOString()).toBe("2026-10-25T00:24:45.123Z");
    expect(parseTime("2026-10-25T00:24:45Z").toISOString()).toBe("2026-10-25T00:24:45.000Z");
    expect(parseTime("2026-10-25T05:54:45+05:30").toISOString()).toBe("2026-10-25T00:24:45.000Z");
  });
});

describe("ActivityList", () => {
  it("describes case changes, newest first", () => {
    render(
      <ActivityList
        entries={[
          {
            seq: 1,
            ts: "2026-10-25T00:00:00",
            action_type: "CASE_CREATED",
            actor: "a@x",
            details: { title: "T" },
          },
          {
            seq: 2,
            ts: "2026-10-25T00:01:00",
            action_type: "CASE_UPDATED",
            actor: "a@x",
            details: {
              changes: { status: { from: "open", to: "closed" }, resolution: "Mule ring" },
              ip: "::1",
            },
          },
        ]}
      />,
    );
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("updated the case");
    expect(items[0]).toHaveTextContent("status: open → closed · resolution: Mule ring");
    expect(items[0]).not.toHaveTextContent("::1");
    expect(items[1]).toHaveTextContent("created the case");
  });
});
