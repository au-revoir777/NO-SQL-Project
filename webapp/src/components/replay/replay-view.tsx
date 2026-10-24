"use client";

import { useQuery } from "@tanstack/react-query";
import { History, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { EmptyState } from "@/components/empty-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, toApiError } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { layout, type Story } from "@/lib/replay/story";

import { ReplayPlayer } from "./replay-player";

type ReplaySummary = components["schemas"]["ReplaySummary"];

function useStory(runId: string) {
  return useQuery({
    queryKey: ["replay", runId],
    queryFn: async (): Promise<Story> => {
      const { data, error, response } = await api.GET("/api/v1/replays/{run_id}", {
        params: { path: { run_id: runId } },
      });
      if (!data) throw toApiError(error, response);
      return data as unknown as Story;
    },
    staleTime: Infinity, // a recorded run never changes
  });
}

function Failed({ message }: { message: string }) {
  return (
    <Alert variant="destructive">
      <TriangleAlert aria-hidden />
      <AlertTitle>Could not load the replay</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}

export function ReplayView({ runId }: { runId: string }) {
  const { data, error, isPending } = useStory(runId);
  const placed = useMemo(() => (data ? layout(data) : null), [data]);
  if (isPending)
    return (
      <div className="space-y-4" role="status" aria-busy="true" aria-label="Loading the replay">
        <Skeleton className="h-8 w-80" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  if (error) return <Failed message={error.message} />;
  return <ReplayPlayer story={data} layout={placed!} />;
}

export function ReplayList() {
  const { data, error, isPending } = useQuery({
    queryKey: ["replays"],
    queryFn: async (): Promise<ReplaySummary[]> => {
      const { data, error, response } = await api.GET("/api/v1/replays");
      if (!data) throw toApiError(error, response);
      return data;
    },
  });
  if (isPending) return <Skeleton className="h-48 w-full" aria-label="Loading replays" />;
  if (error) return <Failed message={error.message} />;
  if (!data.length)
    return (
      <EmptyState icon={History} title="No recorded runs yet">
        Run <code>fraudsim demo-story --seed 7</code> to record a story replay, or start a run from
        the Simulator page.
      </EmptyState>
    );
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Run</TableHead>
          <TableHead>Kind</TableHead>
          <TableHead>Scenario</TableHead>
          <TableHead className="text-right">Seed</TableHead>
          <TableHead className="text-right">Events</TableHead>
          <TableHead>Source</TableHead>
          <TableHead />
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.map((r) => (
          <TableRow key={`${r.kind}:${r.run_id}`}>
            <TableCell className="font-mono">{r.run_id}</TableCell>
            <TableCell>
              <Badge variant="outline">
                {r.kind === "story" ? "story replay" : "recorded run"}
              </Badge>
            </TableCell>
            <TableCell>{r.scenario ?? "n/a"}</TableCell>
            <TableCell className="tabular text-right">{r.seed ?? "n/a"}</TableCell>
            <TableCell className="tabular text-right">
              {r.events?.toLocaleString("en-US") ?? "n/a"}
            </TableCell>
            <TableCell className="text-muted-foreground font-mono text-xs">{r.source}</TableCell>
            <TableCell className="text-right">
              {r.replayable ? (
                <Button asChild size="sm" variant="outline">
                  <Link href={`/replays/${r.run_id}`}>Open replay</Link>
                </Button>
              ) : (
                <span className="text-muted-foreground text-xs">no story recorded</span>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
