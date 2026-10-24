"use client";

import { ChevronLeft, ChevronRight, ShieldAlert, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAudit, useAuditVerify } from "@/lib/cases/queries";

import { fmtTime, QueryError } from "./common";

function Verify() {
  const v = useAuditVerify();
  if (v.isPending) return <Skeleton className="h-16 w-full" />;
  if (v.error)
    return <QueryError error={v.error} title="Could not verify" onRetry={() => void v.refetch()} />;
  return v.data.ok ? (
    <Alert>
      <ShieldCheck aria-hidden className="text-ok" />
      <AlertTitle>Hash chain intact</AlertTitle>
      <AlertDescription>
        <p>
          All {v.data.entries} entries verify (the same check as <code>fraudsim audit-verify</code>
          ).
        </p>
        <Button variant="outline" size="sm" className="mt-2 w-fit" onClick={() => void v.refetch()}>
          Verify again
        </Button>
      </AlertDescription>
    </Alert>
  ) : (
    <Alert variant="destructive">
      <ShieldAlert aria-hidden />
      <AlertTitle>Hash chain broken</AlertTitle>
      <AlertDescription>{v.data.problem}</AlertDescription>
    </Alert>
  );
}

/** Admin view of the app audit trail (newest first) and its hash-chain check. */
export function AuditView() {
  const [draft, setDraft] = useState({ action: "", actor: "", object: "" });
  const [filters, setFilters] = useState(draft);
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  useEffect(() => {
    const t = setTimeout(() => {
      setFilters(draft);
      setCursors([null]);
    }, 300);
    return () => clearTimeout(t);
  }, [draft]);
  const q = useAudit(filters, cursors[cursors.length - 1] ?? null);
  const items = q.data?.items ?? [];

  return (
    <div className="space-y-4">
      <Verify />
      <div className="grid gap-3 sm:grid-cols-3">
        {(
          [
            ["action", "Action", "e.g. ALERT_LABELED"],
            ["actor", "Actor", "e.g. analyst@example.org"],
            ["object", "Object", "e.g. case:3 or alert:12"],
          ] as const
        ).map(([k, label, ph]) => (
          <div key={k} className="space-y-1">
            <Label htmlFor={`audit-${k}`}>{label}</Label>
            <Input
              id={`audit-${k}`}
              placeholder={ph}
              value={draft[k]}
              onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}
            />
          </div>
        ))}
      </div>
      <Card className="overflow-hidden py-0">
        <CardContent className="px-0">
          {q.isPending ? (
            <div className="space-y-2 p-4" aria-busy="true" aria-label="Loading audit entries">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : q.error ? (
            <div className="p-4">
              <QueryError
                error={q.error}
                title="Could not load the audit trail"
                onRetry={() => void q.refetch()}
              />
            </div>
          ) : items.length === 0 ? (
            <p className="text-muted-foreground p-4 text-sm">No entries match.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-right">#</TableHead>
                  <TableHead>Time</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Object</TableHead>
                  <TableHead>Details</TableHead>
                  <TableHead>Hash</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((e) => (
                  <TableRow key={e.seq}>
                    <TableCell className="tabular text-right">{e.seq}</TableCell>
                    <TableCell className="tabular text-xs">{fmtTime(e.ts)}</TableCell>
                    <TableCell className="font-mono text-xs">{e.action_type}</TableCell>
                    <TableCell className="text-xs">{e.actor}</TableCell>
                    <TableCell className="font-mono text-xs">{e.object}</TableCell>
                    <TableCell className="max-w-sm min-w-48 whitespace-normal">
                      <code className="line-clamp-2 text-xs break-all">
                        {JSON.stringify(e.details)}
                      </code>
                    </TableCell>
                    <TableCell className="font-mono text-xs" title={e.hash}>
                      {e.hash.slice(0, 10)}…
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      {q.data && (q.data.total ?? 0) > 0 ? (
        <nav className="flex items-center justify-between" aria-label="Pages">
          <p className="text-muted-foreground tabular text-sm">{q.data.total} entries</p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={cursors.length < 2}
              onClick={() => setCursors((c) => c.slice(0, -1))}
            >
              <ChevronLeft aria-hidden /> Newer
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!q.data.next_cursor}
              onClick={() => setCursors((c) => [...c, q.data.next_cursor ?? null])}
            >
              Older <ChevronRight aria-hidden />
            </Button>
          </div>
        </nav>
      ) : null}
    </div>
  );
}
