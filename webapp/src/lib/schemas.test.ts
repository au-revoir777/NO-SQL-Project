import { describe, expect, it } from "vitest";

import { createUserSchema, loginSchema, safeNext } from "@/lib/schemas";

describe("form schemas", () => {
  it("rejects malformed login input", () => {
    expect(loginSchema.safeParse({ email: "x", password: "" }).success).toBe(false);
    expect(loginSchema.safeParse({ email: "a@example.test", password: "p" }).success).toBe(true);
  });

  it("requires a 12-character password and a known role for new users", () => {
    const base = {
      email: "a@example.test",
      display_name: "",
      role: "analyst",
      password: "x".repeat(12),
    };
    expect(createUserSchema.safeParse(base).success).toBe(true);
    expect(createUserSchema.safeParse({ ...base, password: "short" }).success).toBe(false);
    expect(createUserSchema.safeParse({ ...base, role: "root" }).success).toBe(false);
  });
});

describe("safeNext", () => {
  it.each([
    ["/cases", "/cases"],
    ["/users?x=1", "/users?x=1"],
    [null, "/"],
    ["https://evil.example", "/"],
    ["//evil.example", "/"],
    ["/\\evil.example", "/"],
    ["/login?next=/x", "/"],
  ])("%s -> %s", (input, expected) => {
    expect(safeNext(input)).toBe(expected);
  });
});
