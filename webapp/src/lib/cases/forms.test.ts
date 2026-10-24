import { describe, expect, it } from "vitest";

import { caseStatusSchema, caseTargets, createCaseSchema, savedViewSchema } from "./forms";

describe("case forms", () => {
  it("need a title of at least 3 characters", () => {
    expect(createCaseSchema.safeParse({ title: "  ab ", priority: "high" }).success).toBe(false);
    expect(createCaseSchema.safeParse({ title: "Ring R0007", priority: "high" }).success).toBe(
      true,
    );
    expect(createCaseSchema.safeParse({ title: "Ring R0007", priority: "urgent" }).success).toBe(
      false,
    );
  });

  it("need a resolution only when closing", () => {
    const close = caseStatusSchema.safeParse({ status: "closed", resolution: "  " });
    expect(close.success).toBe(false);
    expect(close.error?.issues[0]?.path).toEqual(["resolution"]);
    expect(caseStatusSchema.safeParse({ status: "escalated", resolution: "" }).success).toBe(true);
    expect(
      caseStatusSchema.safeParse({ status: "closed", resolution: "Confirmed mule ring" }).success,
    ).toBe(true);
  });

  it("name saved views", () => {
    expect(savedViewSchema.safeParse({ name: " " }).success).toBe(false);
    expect(savedViewSchema.safeParse({ name: "High risk, mine" }).success).toBe(true);
  });

  it("offer the API's transitions; only admins reopen", () => {
    expect(caseTargets("open", false)).toEqual(["in_review", "escalated", "closed"]);
    expect(caseTargets("closed", false)).toEqual([]);
    expect(caseTargets("closed", true)).toEqual(["in_review"]);
  });
});
