import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, toApiError } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

import { type AlertFilters, toQuery } from "./filters";

type S = components["schemas"];
export type AlertSummary = S["AlertSummary"];
export type AlertDetail = S["AlertDetail"];
export type UserRef = S["UserRef"];
export type NoteOut = S["NoteOut"];
export type LabelResult = S["LabelResult"];
export type SavedView = S["SavedViewOut"];
export type CaseSummary = S["CaseSummary"];
export type CaseDetail = S["CaseDetail"];
export type CaseUpdate = S["CaseUpdate"];
export type AuditEntry = S["AuditEntryOut"];
export type LabelKind = S["LabelIn"]["label"];
export type CaseStatus = CaseSummary["status"];
export type Priority = CaseSummary["priority"];

/** Throw the API error envelope as an ApiRequestError, else return the data. */
function ok<T>(r: { data?: T; error?: unknown; response: Response }): T {
  if (r.data === undefined) throw toApiError(r.error, r.response);
  return r.data;
}

export const keys = {
  alerts: ["alerts"] as const,
  alert: (id: number) => ["alerts", id] as const,
  views: ["alerts", "views"] as const,
  cases: ["cases"] as const,
  case: (id: number) => ["cases", id] as const,
  users: ["users", "assignable"] as const,
  audit: ["audit"] as const,
};

export function useAlerts(filters: AlertFilters, cursor: string | null, limit = 50) {
  return useQuery({
    queryKey: [...keys.alerts, "list", filters, cursor, limit],
    queryFn: async () =>
      ok(
        await api.GET("/api/v1/alerts", {
          params: {
            query: { ...toQuery(filters), limit, ...(cursor ? { cursor } : {}) } as never,
          },
        }),
      ),
    placeholderData: keepPreviousData,
    refetchInterval: 10_000,
  });
}

export function useAlert(id: number) {
  return useQuery({
    queryKey: keys.alert(id),
    queryFn: async () =>
      ok(await api.GET("/api/v1/alerts/{alert_id}", { params: { path: { alert_id: id } } })),
  });
}

export function useAssignableUsers() {
  return useQuery({
    queryKey: keys.users,
    queryFn: async () => ok(await api.GET("/api/v1/users")),
    staleTime: 60_000,
  });
}

function useInvalidate() {
  const qc = useQueryClient();
  return (...prefixes: readonly (readonly unknown[])[]) =>
    Promise.all(prefixes.map((queryKey) => qc.invalidateQueries({ queryKey })));
}

export function useUpdateAlert(id: number) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: async (body: S["AlertUpdate"]) =>
      ok(
        await api.PATCH("/api/v1/alerts/{alert_id}", {
          params: { path: { alert_id: id } },
          body,
        }),
      ),
    onSuccess: () => inv(keys.alerts),
  });
}

export function useBulkAlerts() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: async (body: S["BulkAlertAction"]) =>
      ok(await api.POST("/api/v1/alerts/bulk", { body })),
    onSuccess: () => inv(keys.alerts),
  });
}

export function useLabelAlert(id: number) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: async (body: S["LabelIn"]) =>
      ok(
        await api.POST("/api/v1/alerts/{alert_id}/labels", {
          params: { path: { alert_id: id } },
          body,
        }),
      ),
    onSuccess: () => inv(keys.alerts),
  });
}

export function useAddAlertNote(id: number) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: async (body: string) =>
      ok(
        await api.POST("/api/v1/alerts/{alert_id}/notes", {
          params: { path: { alert_id: id } },
          body: { body },
        }),
      ),
    onSuccess: () => inv(keys.alert(id)),
  });
}

export function useAddCaseNote(id: number) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: async (body: string) =>
      ok(
        await api.POST("/api/v1/cases/{case_id}/notes", {
          params: { path: { case_id: id } },
          body: { body },
        }),
      ),
    onSuccess: () => inv(keys.case(id)),
  });
}

/** Edit a note (stored as a new version); refreshes whatever page shows it. */
export function useEditNote() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: string }) =>
      ok(
        await api.PATCH("/api/v1/notes/{note_id}", {
          params: { path: { note_id: id } },
          body: { body },
        }),
      ),
    onSuccess: () => inv(keys.alerts, keys.cases),
  });
}

export function useSavedViews() {
  return useQuery({
    queryKey: keys.views,
    queryFn: async () => ok(await api.GET("/api/v1/alerts/views")),
  });
}

export function useSaveView() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: async (body: S["SavedViewIn"]) =>
      ok(await api.PUT("/api/v1/alerts/views", { body })),
    onSuccess: () => inv(keys.views),
  });
}

export function useDeleteView() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: async (id: number) => {
      const { error, response } = await api.DELETE("/api/v1/alerts/views/{view_id}", {
        params: { path: { view_id: id } },
      });
      if (!response.ok) throw toApiError(error, response);
    },
    onSuccess: () => inv(keys.views),
  });
}

export function useCases(status: CaseStatus[], assignee: string, cursor: string | null) {
  return useQuery({
    queryKey: [...keys.cases, "list", status, assignee, cursor],
    queryFn: async () =>
      ok(
        await api.GET("/api/v1/cases", {
          params: {
            query: {
              ...(status.length ? { status } : {}),
              ...(assignee ? { assignee } : {}),
              ...(cursor ? { cursor } : {}),
              limit: 50,
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useCase(id: number) {
  return useQuery({
    queryKey: keys.case(id),
    queryFn: async () =>
      ok(await api.GET("/api/v1/cases/{case_id}", { params: { path: { case_id: id } } })),
  });
}

export function useCreateCase() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: async (body: S["CaseCreate"]) => ok(await api.POST("/api/v1/cases", { body })),
    onSuccess: () => inv(keys.cases, keys.alerts),
  });
}

export function useAttachToCase() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: async ({ caseId, alertIds }: { caseId: number; alertIds: number[] }) =>
      ok(
        await api.POST("/api/v1/cases/{case_id}/alerts", {
          params: { path: { case_id: caseId } },
          body: { alert_ids: alertIds },
        }),
      ),
    onSuccess: () => inv(keys.cases, keys.alerts),
  });
}

export function useUpdateCase(id: number) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: async (body: CaseUpdate) =>
      ok(
        await api.PATCH("/api/v1/cases/{case_id}", {
          params: { path: { case_id: id } },
          body,
        }),
      ),
    onSuccess: () => inv(keys.cases),
  });
}

export function useSnapshot(caseId: number, alertId: number | null) {
  return useQuery({
    queryKey: [...keys.case(caseId), "snapshot", alertId],
    enabled: alertId !== null,
    queryFn: async () =>
      ok(
        await api.GET("/api/v1/cases/{case_id}/alerts/{alert_id}/snapshot", {
          params: { path: { case_id: caseId, alert_id: alertId ?? 0 } },
        }),
      ),
  });
}

export function useAudit(
  filters: { action: string; actor: string; object: string },
  cursor: string | null,
) {
  return useQuery({
    queryKey: [...keys.audit, filters, cursor],
    queryFn: async () =>
      ok(
        await api.GET("/api/v1/audit", {
          params: {
            query: {
              ...(filters.action ? { action: filters.action } : {}),
              ...(filters.actor ? { actor: filters.actor } : {}),
              ...(filters.object ? { object: filters.object } : {}),
              ...(cursor ? { cursor } : {}),
              limit: 100,
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useAuditVerify() {
  return useQuery({
    queryKey: [...keys.audit, "verify"],
    queryFn: async () => ok(await api.GET("/api/v1/audit/verify")),
  });
}
