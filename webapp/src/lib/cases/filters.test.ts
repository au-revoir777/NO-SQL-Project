import { describe, expect, it } from "vitest";

import {
  bulkStatusOptions,
  DEFAULT_FILTERS,
  filterErrors,
  fromSaved,
  toggleSelection,
  toQuery,
} from "./filters";

describe("alert filters", () => {
  it("send only what is set", () => {
    expect(toQuery(DEFAULT_FILTERS)).toEqual({
      sort: "risk",
      order: "desc",
      status: ["new", "triaged", "escalated"],
    });
    const q = toQuery({
      ...DEFAULT_FILTERS,
      status: [],
      risk_min: "0.8",
      detector: "hub_aware",
      q: "  R0001 ",
    });
    expect(q).toEqual({
      sort: "risk",
      order: "desc",
      risk_min: 0.8,
      detector: "hub_aware",
      q: "R0001",
    });
  });

  it("validate ranges", () => {
    expect(filterErrors({ ...DEFAULT_FILTERS, risk_min: "2" })).toEqual({
      risk_min: "Between 0 and 1",
    });
    expect(filterErrors({ ...DEFAULT_FILTERS, risk_min: "0.9", risk_max: "0.5" })).toEqual({
      risk_max: "Must be at least the minimum",
    });
    expect(
      filterErrors({ ...DEFAULT_FILTERS, since: "2026-01-01T00:01", until: "2026-01-01T00:00" }),
    ).toEqual({ until: "Must be after the start" });
    expect(filterErrors(DEFAULT_FILTERS)).toEqual({});
  });

  it("fill older saved views with defaults", () => {
    expect(fromSaved({ risk_min: "0.8" })).toEqual({ ...DEFAULT_FILTERS, risk_min: "0.8" });
  });
});

describe("bulk selection", () => {
  const ids = [10, 11, 12, 13, 14];

  it("toggles one row, or a range with shift", () => {
    let s = toggleSelection(new Set(), ids, 11, null, false);
    expect([...s]).toEqual([11]);
    s = toggleSelection(s, ids, 14, 11, true);
    expect([...s].sort()).toEqual([11, 12, 13, 14]);
    s = toggleSelection(s, ids, 12, 11, false);
    expect([...s].sort()).toEqual([11, 13, 14]);
  });

  it("offers only the statuses some selected alert can move to", () => {
    expect(bulkStatusOptions(["new"])).toEqual(["triaged", "escalated", "closed"]);
    expect(bulkStatusOptions(["closed"])).toEqual([]);
    expect(bulkStatusOptions(["triaged", "escalated"])).toEqual(["triaged", "escalated", "closed"]);
  });
});
