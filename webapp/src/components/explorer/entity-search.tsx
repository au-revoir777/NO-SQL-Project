"use client";

import { Search } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { QueryError } from "@/components/cases/common";
import { EmptyState } from "@/components/empty-state";
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
import { type EntityKind, KIND_LABEL, KINDS, SOURCE_LABEL } from "@/lib/explorer/graph";
import { useEntitySearch } from "@/lib/explorer/queries";

import { EntityLink, SourceSelect, useSource } from "./common";

/** Search by id prefix across users, devices, cards and IPs (?q= in the URL). */
export function EntitySearch() {
  const source = useSource();
  const params = useSearchParams();
  const router = useRouter();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [applied, setApplied] = useState(q);
  const [kinds, setKinds] = useState<EntityKind[]>([]);
  useEffect(() => {
    const t = setTimeout(() => {
      setApplied(q);
      const next = new URLSearchParams(params.toString());
      if (q.trim()) next.set("q", q.trim());
      else next.delete("q");
      router.replace(`/explorer?${next.toString()}`, { scroll: false });
    }, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only the text drives this
  }, [q]);
  const hits = useEntitySearch(applied, source, kinds, 50);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-4">
        <SourceSelect />
        <div className="min-w-64 flex-1 space-y-1">
          <Label htmlFor="entity-q">Id starts with</Label>
          <Input
            id="entity-q"
            type="search"
            placeholder="u01, device_007, card_, ip_00…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            autoFocus
          />
        </div>
        <fieldset className="flex flex-wrap items-center gap-2">
          <legend className="sr-only">Entity types</legend>
          {KINDS.map((k) => {
            const on = kinds.includes(k);
            return (
              <Button
                key={k}
                size="sm"
                variant={on ? "default" : "outline"}
                aria-pressed={on}
                onClick={() => setKinds(on ? kinds.filter((x) => x !== k) : [...kinds, k])}
              >
                {KIND_LABEL[k]}
              </Button>
            );
          })}
        </fieldset>
      </div>
      <Card className="overflow-hidden py-0">
        <CardContent className="px-0">
          {!applied.trim() ? (
            <div className="p-4">
              <EmptyState icon={Search} title="Search the graph">
                Type the start of an id. The {SOURCE_LABEL[source].toLowerCase()} is searched;
                switch graphs above. Press Ctrl+K anywhere to search without leaving the page.
              </EmptyState>
            </div>
          ) : hits.isPending ? (
            <div className="space-y-2 p-4" role="status" aria-busy="true" aria-label="Searching">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-9 w-full" />
              ))}
            </div>
          ) : hits.error ? (
            <div className="p-4">
              <QueryError
                error={hits.error}
                title="Search failed"
                onRetry={() => void hits.refetch()}
              />
            </div>
          ) : hits.data.length === 0 ? (
            <p className="text-muted-foreground p-4 text-sm">
              Nothing in the {SOURCE_LABEL[source].toLowerCase()} starts with “{applied.trim()}”.
            </p>
          ) : (
            <Table label="Search results">
              <TableHeader>
                <TableRow>
                  <TableHead>Entity</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Degree</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {hits.data.map((h) => (
                  <TableRow key={`${h.kind}:${h.id}`}>
                    <TableCell>
                      <EntityLink kind={h.kind} id={h.id} source={source} />
                    </TableCell>
                    <TableCell>{KIND_LABEL[h.kind]}</TableCell>
                    <TableCell className="tabular text-right">
                      {h.degree}{" "}
                      <span className="text-muted-foreground text-xs">
                        {h.kind === "user" ? "attributes" : "users"}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
