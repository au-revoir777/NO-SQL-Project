import { describe, expect, it } from "vitest";

import { DEFAULT_REPORT, fmtBytes, reportSchema, toRequest, utc } from "./form";

describe("report form", () => {
  it("needs a title and some scope", () => {
    const r = reportSchema.safeParse({ ...DEFAULT_REPORT, title: "Case 3" });
    expect(r.success).toBe(false);
    expect(r.error?.issues.map((i) => i.path.join("."))).toEqual(["run_ids"]);
    expect(reportSchema.safeParse({ ...DEFAULT_REPORT, title: "x", case_ids: [3] }).success).toBe(
      false,
    );
    expect(
      reportSchema.safeParse({ ...DEFAULT_REPORT, title: "Case 3", case_ids: [3] }).success,
    ).toBe(true);
  });

  it("checks sections and the time window", () => {
    const base = { ...DEFAULT_REPORT, title: "Run report", run_ids: ["abc"] };
    expect(reportSchema.safeParse({ ...base, sections: [] }).success).toBe(false);
    const r = reportSchema.safeParse({
      ...base,
      since: "2026-01-01T00:02",
      until: "2026-01-01T00:01",
    });
    expect(r.error?.issues[0]?.path).toEqual(["until"]);
  });

  it("sends UTC times and leaves empty ones out", () => {
    expect(utc("2026-01-01T00:01")).toBe("2026-01-01T00:01:00Z");
    expect(utc("2026-01-01T00:01:30")).toBe("2026-01-01T00:01:30Z");
    const body = toRequest({
      ...DEFAULT_REPORT,
      title: " T ",
      run_ids: ["r"],
      since: "2026-01-01T00:00",
    });
    expect(body).toMatchObject({ title: "T", since: "2026-01-01T00:00:00Z", format: "pdf" });
    expect("until" in body).toBe(false);
    expect(fmtBytes(2048)).toBe("2.0 KB");
  });
});
