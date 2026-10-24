"use client";

import { Briefcase, ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { CASE_STATUSES } from "@/lib/cases/forms";
import { type CaseStatus, useCases } from "@/lib/cases/queries";

import { CaseStatusBadge, fmtTime, PriorityBadge, QueryError, userName, words } from "./common";

export function CaseList() {
  const [status, setStatus] = useState<CaseStatus[]>(["open", "in_review", "escalated"]);
  const [assignee, setAssignee] = useState("");
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const q = useCases(status, assignee, cursors[cursors.length - 1] ?? null);
  const items = q.data?.items ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-4">
        <fieldset className="flex flex-wrap items-center gap-2">
          <legend className="sr-only">Status</legend>
          <span className="text-muted-foreground mr-1 text-sm">Status</span>
          {CASE_STATUSES.map((s) => {
            const on = status.includes(s);
            return (
              <Button
                key={s}
                size="sm"
                variant={on ? "default" : "outline"}
                aria-pressed={on}
                onClick={() => {
                  setStatus(on ? status.filter((x) => x !== s) : [...status, s]);
                  setCursors([null]);
                }}
              >
                {words(s)}
              </Button>
            );
          })}
        </fieldset>
        <div className="space-y-1">
          <Label htmlFor="case-assignee">Assignee</Label>
          <Select
            value={assignee || "any"}
            onValueChange={(v) => {
              setAssignee(v === "any" ? "" : v);
              setCursors([null]);
            }}
          >
            <SelectTrigger id="case-assignee" className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Anyone</SelectItem>
              <SelectItem value="me">Assigned to me</SelectItem>
              <SelectItem value="none">Unassigned</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <Card className="overflow-hidden py-0">
        <CardContent className="px-0">
          {q.isPending ? (
            <div className="space-y-2 p-4" aria-busy="true" aria-label="Loading cases">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : q.error ? (
            <div className="p-4">
              <QueryError
                error={q.error}
                title="Could not load cases"
                onRetry={() => void q.refetch()}
              />
            </div>
          ) : items.length === 0 ? (
            <div className="p-4">
              <EmptyState icon={Briefcase} title="No cases match">
                Create a case from one or more alerts in the alert queue.
              </EmptyState>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Case</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead className="text-right">Alerts</TableHead>
                  <TableHead>Assignee</TableHead>
                  <TableHead>Updated</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((c) => (
                  <TableRow key={c.id} className="h-11">
                    <TableCell>
                      <Link
                        href={`/cases/${c.id}`}
                        className="font-medium underline-offset-4 hover:underline"
                      >
                        #{c.id} {c.title}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <CaseStatusBadge status={c.status} />
                    </TableCell>
                    <TableCell>
                      <PriorityBadge priority={c.priority} />
                    </TableCell>
                    <TableCell className="tabular text-right">{c.alerts_count}</TableCell>
                    <TableCell>{userName(c.assignee)}</TableCell>
                    <TableCell className="tabular text-xs">{fmtTime(c.updated_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      {q.data && (q.data.total ?? 0) > 0 ? (
        <nav className="flex items-center justify-between" aria-label="Pages">
          <p className="text-muted-foreground tabular text-sm">{q.data.total} cases</p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={cursors.length < 2}
              onClick={() => setCursors((c) => c.slice(0, -1))}
            >
              <ChevronLeft aria-hidden /> Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!q.data.next_cursor}
              onClick={() => setCursors((c) => [...c, q.data.next_cursor ?? null])}
            >
              Next <ChevronRight aria-hidden />
            </Button>
          </div>
        </nav>
      ) : null}
    </div>
  );
}
