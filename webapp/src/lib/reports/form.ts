import { z } from "zod";

/** Report sections, in report order, with the builder's labels. */
export const SECTIONS = [
  ["executive_summary", "Executive summary"],
  ["alert_table", "Alert table"],
  ["ring_detail", "Per-ring detail with evidence subgraph"],
  ["contributions", "Contributions chart"],
  ["counterfactuals", "Counterfactuals"],
  ["timeline", "Timeline"],
  ["notes", "Analyst notes and labels"],
  ["sar_summary", "SAR-style summary"],
  ["run_metrics", "Run metrics"],
  ["limitations", "Limitations and uncertainty"],
] as const;
export type Section = (typeof SECTIONS)[number][0];
export const ALL_SECTIONS = SECTIONS.map(([s]) => s) as Section[];

/** Mirrors ReportCreate; the scope must name at least one run, alert or case. */
export const reportSchema = z
  .object({
    title: z.string().trim().min(3, "At least 3 characters").max(300, "At most 300 characters"),
    run_ids: z.array(z.string()),
    case_ids: z.array(z.number().int().positive()),
    alert_ids: z.array(z.number().int().positive()),
    since: z.string(),
    until: z.string(),
    sections: z
      .array(z.enum(ALL_SECTIONS as [Section, ...Section[]]))
      .min(1, "Pick at least one section"),
    oracle: z.boolean(),
    format: z.enum(["html", "pdf"]),
  })
  .superRefine((v, ctx) => {
    if (!v.run_ids.length && !v.case_ids.length && !v.alert_ids.length)
      ctx.addIssue({
        code: "custom",
        path: ["run_ids"],
        message: "Choose at least one run, case or alert",
      });
    if (v.since && v.until && v.since > v.until)
      ctx.addIssue({ code: "custom", path: ["until"], message: "Must be after the start" });
  });
export type ReportValues = z.infer<typeof reportSchema>;

export const DEFAULT_REPORT: ReportValues = {
  title: "",
  run_ids: [],
  case_ids: [],
  alert_ids: [],
  since: "",
  until: "",
  sections: ALL_SECTIONS,
  oracle: false,
  format: "pdf",
};

/** A datetime-local value ("2026-01-01T00:00" or with seconds) as a UTC ISO time. */
export function utc(local: string): string {
  return `${local.length === 16 ? `${local}:00` : local}Z`;
}

/** Form values -> POST /api/v1/reports body (empty times left out; inputs are UTC). */
export function toRequest(v: ReportValues) {
  return {
    title: v.title.trim(),
    run_ids: v.run_ids,
    case_ids: v.case_ids,
    alert_ids: v.alert_ids,
    sections: v.sections,
    oracle: v.oracle,
    format: v.format,
    ...(v.since ? { since: utc(v.since) } : {}),
    ...(v.until ? { until: utc(v.until) } : {}),
  };
}

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
