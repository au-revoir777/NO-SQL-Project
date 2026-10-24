import type { LucideIcon } from "lucide-react";
import { TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

import { Sparkline } from "./sparkline";

export type KpiState =
  | { kind: "loading" }
  | { kind: "empty"; message: string }
  | { kind: "error"; message: string }
  | { kind: "value"; value: ReactNode; detail?: ReactNode; trend?: number[] };

/** One KPI with its trend; explicit loading, empty and error states (never a made-up value). */
export function KpiCard({
  title,
  description,
  icon: Icon,
  state,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
  state: KpiState;
}) {
  return (
    <Card className="gap-3">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Icon className="text-muted-foreground size-4" aria-hidden />
          {title}
        </CardTitle>
        <CardDescription className="text-xs">{description}</CardDescription>
      </CardHeader>
      <CardContent className="flex items-end justify-between gap-3">
        {state.kind === "loading" ? (
          <div
            className="w-full space-y-2"
            role="status"
            aria-busy="true"
            aria-label={`Loading ${title}`}
          >
            <Skeleton className="h-7 w-24" />
            <Skeleton className="h-4 w-32" />
          </div>
        ) : state.kind === "empty" ? (
          <p className="text-muted-foreground text-sm">{state.message}</p>
        ) : state.kind === "error" ? (
          <p className="text-risk-alert flex items-center gap-1.5 text-sm" role="alert">
            <TriangleAlert className="size-4" aria-hidden />
            {state.message}
          </p>
        ) : (
          <>
            <div className="min-w-0">
              <div className="tabular text-2xl font-semibold">{state.value}</div>
              {state.detail ? (
                <div className="text-muted-foreground tabular text-xs">{state.detail}</div>
              ) : null}
            </div>
            {state.trend ? <Sparkline values={state.trend} label={title} /> : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}
