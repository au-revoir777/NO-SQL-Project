"use client";

import { CircleCheck, CircleMinus, CircleX, RefreshCw, TriangleAlert } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiRequestError, type ComponentHealth } from "@/lib/api/client";
import { useHealth } from "@/lib/api/queries";

const NAMES: Record<ComponentHealth["name"], string> = {
  api: "API",
  app_db: "App database",
  neo4j: "Neo4j",
  redis: "Redis",
};

const STATUS = {
  ok: { label: "OK", Icon: CircleCheck, className: "text-ok" },
  unavailable: { label: "Unavailable", Icon: CircleX, className: "text-risk-alert" },
  not_configured: {
    label: "Not configured",
    Icon: CircleMinus,
    className: "text-muted-foreground",
  },
} as const;

/** System status from GET /api/v1/health, with loading, error and data states. */
export function SystemStatusCard() {
  const { data, error, isPending, refetch, isFetching } = useHealth();

  return (
    <Card>
      <CardHeader>
        <CardTitle>System status</CardTitle>
        <CardDescription>Live from GET /api/v1/health, refreshed every 15 s.</CardDescription>
        <CardAction>
          <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={isFetching}>
            <RefreshCw className={isFetching ? "animate-spin" : undefined} aria-hidden />
            Refresh
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <div className="space-y-3" aria-busy="true" aria-label="Loading system status">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="flex items-center justify-between">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-5 w-24" />
              </div>
            ))}
          </div>
        ) : error ? (
          <Alert variant="destructive">
            <TriangleAlert aria-hidden />
            <AlertTitle>Cannot reach the API</AlertTitle>
            <AlertDescription>
              <p>{error.message}</p>
              {error instanceof ApiRequestError && error.requestId ? (
                <p className="font-mono text-xs">Request id: {error.requestId}</p>
              ) : null}
              <Button variant="outline" size="sm" className="mt-2" onClick={() => void refetch()}>
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        ) : (
          <dl className="divide-y">
            {data.components.map((c) => {
              const s = STATUS[c.status];
              return (
                <div key={c.name} className="flex items-center justify-between gap-4 py-2.5">
                  <dt className="font-medium">{NAMES[c.name]}</dt>
                  <dd className="flex flex-col items-end gap-0.5 text-right">
                    <Badge variant="outline" className={s.className}>
                      <s.Icon aria-hidden />
                      {s.label}
                    </Badge>
                    {c.detail ? (
                      <span className="text-muted-foreground text-xs">{c.detail}</span>
                    ) : null}
                  </dd>
                </div>
              );
            })}
            <div className="text-muted-foreground flex justify-between pt-2.5 text-xs">
              <span>
                API <span className="font-mono">{data.version}</span>
              </span>
              <span>
                App DB revision <span className="font-mono">{data.db_revision ?? "none"}</span>
              </span>
            </div>
          </dl>
        )}
      </CardContent>
    </Card>
  );
}
