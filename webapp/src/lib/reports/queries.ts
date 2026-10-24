import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, toApiError } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type ReportOut = components["schemas"]["ReportOut"];
export type ReportCreate = components["schemas"]["ReportCreate"];

function ok<T>(r: { data?: T; error?: unknown; response: Response }): T {
  if (r.data === undefined) throw toApiError(r.error, r.response);
  return r.data;
}

export function downloadHref(id: string): string {
  return `/api/v1/reports/${encodeURIComponent(id)}/download`;
}

export function useReports() {
  return useQuery({
    queryKey: ["reports"],
    queryFn: async () =>
      ok(await api.GET("/api/v1/reports", { params: { query: { limit: 100 } } })),
  });
}

export function useCreateReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ReportCreate) => ok(await api.POST("/api/v1/reports", { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reports"] }),
  });
}

/** Runs that can go into a report: the current run and the runs recorded on disk. */
export function useReportableRuns() {
  return useQuery({
    queryKey: ["reports", "runs"],
    queryFn: async () => {
      const [cur, rec] = await Promise.all([
        api.GET("/api/v1/runs/current"),
        api.GET("/api/v1/replays"),
      ]);
      const out: { run_id: string; label: string }[] = [];
      const current = cur.data;
      if (current?.run_id)
        out.push({
          run_id: current.run_id,
          label: `${current.run_id} · current run · ${current.scenario ?? ""} seed ${current.seed ?? ""}`,
        });
      for (const r of rec.data ?? []) {
        if (r.kind !== "run" || out.some((o) => o.run_id === r.run_id)) continue;
        out.push({
          run_id: r.run_id,
          label: `${r.run_id} · ${r.scenario ?? "?"} seed ${r.seed ?? "?"}`,
        });
      }
      return out;
    },
  });
}
