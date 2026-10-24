"use client";

import { BellRing, Siren } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { HIGH_RISK, type LiveAlert } from "@/lib/live/use-live-run";

function riskClass(risk: number | null | undefined): string {
  if (risk === null || risk === undefined) return "border-muted-foreground text-muted-foreground";
  if (risk >= HIGH_RISK) return "border-risk-alert text-risk-alert";
  if (risk >= 0.5) return "border-risk-confirmed text-risk-confirmed";
  return "border-risk-candidate text-risk-candidate";
}

function label(kind: string): string {
  return kind === "early_warning" ? "Early warning" : "Alert";
}

/** Live alerts, newest first. Age is in simulated seconds, relative to the latest sample. */
export function AlertFeed({ alerts, nowSimS }: { alerts: LiveAlert[]; nowSimS: number | null }) {
  const [open, setOpen] = useState<LiveAlert | null>(null);
  if (!alerts.length) {
    return (
      <EmptyState icon={BellRing} title="No alerts in this run yet">
        Alerts and early warnings appear here as soon as the detector raises them.
      </EmptyState>
    );
  }
  return (
    <>
      <ul className="divide-y" aria-label="Live alerts, newest first">
        {alerts.map((a) => {
          const age = nowSimS === null ? null : Math.max(0, nowSimS - a.sim_time_s);
          return (
            <li key={`${a.ring_id}:${a.kind}:${a.ts}`}>
              <button
                type="button"
                onClick={() => setOpen(a)}
                className="hover:bg-muted/60 focus-visible:ring-ring flex w-full items-start gap-3 rounded-md px-2 py-2.5 text-left outline-none focus-visible:ring-2"
              >
                <Badge variant="outline" className={`tabular shrink-0 ${riskClass(a.risk)}`}>
                  {a.kind === "alert" ? <Siren aria-hidden /> : <BellRing aria-hidden />}
                  {a.risk === null || a.risk === undefined ? "n/a" : a.risk.toFixed(2)}
                </Badge>
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-baseline gap-x-2 text-sm font-medium">
                    {label(a.kind)} · {a.ring_type?.replaceAll("_", " ") ?? "unknown type"}
                    <span className="text-muted-foreground tabular text-xs font-normal">
                      {a.members_count} members · {a.ring_id}
                    </span>
                  </span>
                  <span className="text-muted-foreground line-clamp-2 text-xs">
                    {a.top_reason ?? "No reason recorded"}
                  </span>
                </span>
                <span className="text-muted-foreground tabular shrink-0 text-xs">
                  {age === null ? "" : `${age.toFixed(0)} s ago`}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      <Dialog open={open !== null} onOpenChange={(o) => !o && setOpen(null)}>
        <DialogContent className="sm:max-w-lg">
          {open ? (
            <>
              <DialogHeader>
                <DialogTitle>
                  {label(open.kind)} {open.ring_id}
                </DialogTitle>
                <DialogDescription>
                  {open.ring_type?.replaceAll("_", " ")} · risk{" "}
                  {open.risk === null || open.risk === undefined ? "n/a" : open.risk.toFixed(2)}
                  {open.threshold !== null && open.threshold !== undefined
                    ? ` (threshold ${open.threshold.toFixed(2)})`
                    : ""}{" "}
                  · simulated t = {open.sim_time_s.toFixed(1)} s
                </DialogDescription>
              </DialogHeader>
              <dl className="grid grid-cols-[8rem_1fr] gap-x-3 gap-y-2 text-sm">
                <dt className="text-muted-foreground">Why</dt>
                <dd>{open.top_reason ?? "No reason recorded"}</dd>
                <dt className="text-muted-foreground">Detectors</dt>
                <dd>{open.detectors.join(", ") || "n/a"}</dd>
                <dt className="text-muted-foreground">Members ({open.members_count})</dt>
                <dd className="font-mono text-xs break-words">
                  {open.members.join(", ")}
                  {open.members_count > open.members.length ? " …" : ""}
                </dd>
                <dt className="text-muted-foreground">Run</dt>
                <dd className="font-mono text-xs">{open.run_id}</dd>
              </dl>
              <p className="text-muted-foreground text-xs">
                Triage, case linkage and the full explanation arrive with the Alerts page (P5).
              </p>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
