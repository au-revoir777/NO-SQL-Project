import { z } from "zod";

export const PRIORITIES = ["low", "medium", "high", "critical"] as const;
export const CASE_STATUSES = ["open", "in_review", "escalated", "closed"] as const;

/** Mirrors CaseCreate (title 3–300 characters) for the alerts already chosen. */
export const createCaseSchema = z.object({
  title: z.string().trim().min(3, "At least 3 characters").max(300, "At most 300 characters"),
  priority: z.enum(PRIORITIES),
});
export type CreateCaseValues = z.infer<typeof createCaseSchema>;

/** Closing a case needs a resolution (the API answers 422 without one). */
export const caseStatusSchema = z
  .object({
    status: z.enum(CASE_STATUSES),
    resolution: z.string().trim().max(5000, "At most 5,000 characters"),
  })
  .refine((v) => v.status !== "closed" || v.resolution.length > 0, {
    path: ["resolution"],
    message: "Say how the case was resolved before closing it",
  });
export type CaseStatusValues = z.infer<typeof caseStatusSchema>;

export const savedViewSchema = z.object({
  name: z.string().trim().min(1, "Give the view a name").max(80, "At most 80 characters"),
});

/** Case transitions as enforced by the API (admins may also reopen a closed case). */
export const CASE_NEXT: Record<(typeof CASE_STATUSES)[number], (typeof CASE_STATUSES)[number][]> = {
  open: ["in_review", "escalated", "closed"],
  in_review: ["open", "escalated", "closed"],
  escalated: ["in_review", "closed"],
  closed: [],
};

export function caseTargets(
  status: (typeof CASE_STATUSES)[number],
  isAdmin: boolean,
): (typeof CASE_STATUSES)[number][] {
  return status === "closed" && isAdmin ? ["in_review"] : CASE_NEXT[status];
}
