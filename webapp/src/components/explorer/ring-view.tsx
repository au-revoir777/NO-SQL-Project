"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { QueryError, RiskBadge, words } from "@/components/cases/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fmtSimTime, nodeKey } from "@/lib/explorer/graph";
import { useRing } from "@/lib/explorer/queries";

import { EntityLink } from "./common";
import { NeighbourhoodView } from "./neighbourhood-view";

/** Ring size over time as a step line (text alternative: the membership table). */
function SizeChart({ points }: { points: [number, number][] }) {
  if (points.length < 2) return null;
  const w = 600;
  const h = 120;
  const t0 = points[0]![0];
  const t1 = points[points.length - 1]![0];
  const maxS = Math.max(...points.map((p) => p[1]));
  const x = (t: number) => (t1 === t0 ? 0 : ((t - t0) / (t1 - t0)) * (w - 20) + 10);
  const y = (s: number) => h - 10 - (s / maxS) * (h - 30);
  let d = `M ${x(points[0]![0])} ${y(points[0]![1])}`;
  for (let i = 1; i < points.length; i++) {
    d += ` H ${x(points[i]![0])} V ${y(points[i]![1])}`;
  }
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="h-32 w-full"
      role="img"
      aria-label={`Ring size from ${points[0]![1]} to ${points[points.length - 1]![1]} members, peak ${maxS}`}
    >
      <path d={d} fill="none" stroke="var(--risk-alert)" strokeWidth={2} />
      <text x={10} y={14} className="fill-muted-foreground text-[10px]">
        {maxS} members
      </text>
    </svg>
  );
}

export function RingView({ ringId }: { ringId: string }) {
  const q = useRing(ringId);
  if (q.isPending) return <Skeleton className="h-64 w-full" />;
  if (q.error)
    return (
      <QueryError
        error={q.error}
        title="Could not load the ring"
        onRetry={() => void q.refetch()}
      />
    );
  const r = q.data;
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link href="/explorer">
            <ArrowLeft aria-hidden /> Explorer
          </Link>
        </Button>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">
            Ring <span className="font-mono">{r.ring_id}</span>
          </h1>
          <Badge variant="outline">{r.status}</Badge>
          <RiskBadge risk={r.risk ?? null} />
        </div>
        <p className="text-muted-foreground text-sm">
          <span className="capitalize">{words(r.ring_type)}</span> · {r.members.length} members ·
          found by {r.detectors.map(words).join(", ")} · first seen {r.first_seen} · last seen{" "}
          {r.last_seen}
          {r.parent ? ` · split from ${r.parent}` : ""} · run {r.run_id}
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Members now</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-wrap gap-x-4 gap-y-1">
              {r.members.map((m) => (
                <li key={m}>
                  <EntityLink kind="user" id={m} source="run" />
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Size over time</CardTitle>
          </CardHeader>
          <CardContent>
            <SizeChart points={r.size_history as [number, number][]} />
          </CardContent>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <CardHeader>
          <CardTitle>Membership over time</CardTitle>
          <CardDescription>
            Each change the tracker made (created, confirmed, grew, shrank, split, merged,
            dissolved) and the members after it.
          </CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          <Table label="Membership changes">
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Change</TableHead>
                <TableHead>Added</TableHead>
                <TableHead>Removed</TableHead>
                <TableHead className="text-right">Members</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {r.timeline.map((s, i) => (
                <TableRow key={i}>
                  <TableCell className="tabular text-xs">{s.ts}</TableCell>
                  <TableCell>
                    {words(s.change)}
                    {Object.keys(s.details ?? {}).length ? (
                      <span className="text-muted-foreground text-xs">
                        {" "}
                        {Object.entries(s.details ?? {})
                          .map(([k, v]) => `${k} ${String(v)}`)
                          .join(", ")}
                      </span>
                    ) : null}
                  </TableCell>
                  <TableCell className="font-mono text-xs whitespace-normal">
                    {s.added?.join(", ") || "–"}
                  </TableCell>
                  <TableCell className="font-mono text-xs whitespace-normal">
                    {s.removed?.join(", ") || "–"}
                  </TableCell>
                  <TableCell className="tabular text-right">{s.members.length}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card className="overflow-hidden">
        <CardHeader>
          <CardTitle>Shared attributes</CardTitle>
          <CardDescription>Attributes at least two current members link to.</CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          <Table label="Shared attributes">
            <TableHeader>
              <TableRow>
                <TableHead>Attribute</TableHead>
                <TableHead className="text-right">Users</TableHead>
                <TableHead className="text-right">Hub weight</TableHead>
                <TableHead>Members (and when they linked)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {r.shared_attributes.length ? (
                r.shared_attributes.map((a) => (
                  <TableRow key={`${a.kind}:${a.id}`}>
                    <TableCell>
                      <EntityLink kind={a.kind} id={a.id} source="run" />
                    </TableCell>
                    <TableCell className="tabular text-right">{a.degree}</TableCell>
                    <TableCell className="tabular text-right">{a.hub_weight.toFixed(4)}</TableCell>
                    <TableCell className="text-xs whitespace-normal">
                      {a.members.map((m) => `${m.user} (${fmtSimTime(m.t)})`).join(", ")}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={4} className="text-muted-foreground">
                    No attribute is shared by two members (a transfer-pattern ring).
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {r.members[0] ? (
        <NeighbourhoodView seed={nodeKey("user", r.members[0])} source="run" />
      ) : null}
    </div>
  );
}
