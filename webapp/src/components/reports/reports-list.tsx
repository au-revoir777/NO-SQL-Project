"use client";

import { FileDown, FileText } from "lucide-react";

import { fmtTime, QueryError, userName } from "@/components/cases/common";
import { EmptyState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fmtBytes } from "@/lib/reports/form";
import { downloadHref, useReports } from "@/lib/reports/queries";

export function ReportsList() {
  const q = useReports();
  return (
    <Card className="overflow-hidden py-0">
      <CardContent className="px-0">
        {q.isPending ? (
          <div
            className="space-y-2 p-4"
            role="status"
            aria-busy="true"
            aria-label="Loading reports"
          >
            {[0, 1].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : q.error ? (
          <div className="p-4">
            <QueryError
              error={q.error}
              title="Could not load reports"
              onRetry={() => void q.refetch()}
            />
          </div>
        ) : q.data.items.length === 0 ? (
          <div className="p-4">
            <EmptyState icon={FileText} title="No reports yet">
              Build one above, or from a case page.
            </EmptyState>
          </div>
        ) : (
          <Table label="Reports">
            <TableHeader>
              <TableRow>
                <TableHead>Report</TableHead>
                <TableHead>Format</TableHead>
                <TableHead className="text-right">Rings</TableHead>
                <TableHead>Runs</TableHead>
                <TableHead>SHA-256</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>
                  <span className="sr-only">Download</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {q.data.items.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-medium whitespace-normal">{r.title}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{r.format.toUpperCase()}</Badge>{" "}
                    <span className="text-muted-foreground text-xs">{fmtBytes(r.size_bytes)}</span>
                  </TableCell>
                  <TableCell className="tabular text-right">{r.rings}</TableCell>
                  <TableCell className="font-mono text-xs">{r.run_ids.join(", ") || "–"}</TableCell>
                  <TableCell className="font-mono text-xs" title={r.sha256}>
                    {r.sha256.slice(0, 12)}…
                  </TableCell>
                  <TableCell className="text-xs">
                    {fmtTime(r.created_at)}
                    <span className="text-muted-foreground block">{userName(r.created_by)}</span>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="outline" size="sm" asChild>
                      <a href={downloadHref(r.id)} download aria-label={`Download ${r.title}`}>
                        <FileDown aria-hidden /> Download
                      </a>
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
