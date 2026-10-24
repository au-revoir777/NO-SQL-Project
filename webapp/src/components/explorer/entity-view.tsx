"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { AlertStatusBadge, QueryError, RiskBadge, words } from "@/components/cases/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { AlertStatus } from "@/lib/cases/filters";
import {
  type EntityKind,
  fmtSimTime,
  KIND_LABEL,
  nodeKey,
  SOURCE_LABEL,
  type Source,
} from "@/lib/explorer/graph";
import { type EntityDetail, useEntity } from "@/lib/explorer/queries";

import { EntityLink, KIND_ICON, SourceSelect, useSource } from "./common";
import { NeighbourhoodView } from "./neighbourhood-view";

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-0.5">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="text-sm font-medium">{children}</dd>
    </div>
  );
}

function money(v: number): string {
  return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function Summary({ e }: { e: EntityDetail }) {
  return (
    <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <Stat label="Type">{KIND_LABEL[e.kind]}</Stat>
      {e.kind === "user" ? (
        <>
          <Stat label="Status">{e.active ? "active" : "left"}</Stat>
          <Stat label="Joined">{fmtSimTime(e.joined_t)}</Stat>
          <Stat label="Linked attributes">
            <span className="tabular">{e.degree}</span>
          </Stat>
          <Stat label="Sent">
            <span className="tabular">
              {e.transactions?.sent ?? 0} · {money(e.transactions?.amount_sent ?? 0)}
            </span>
          </Stat>
          <Stat label="Received">
            <span className="tabular">
              {e.transactions?.received ?? 0} · {money(e.transactions?.amount_received ?? 0)}
            </span>
          </Stat>
        </>
      ) : (
        <>
          <Stat label="Active users (degree)">
            <span className="tabular">{e.degree}</span>
          </Stat>
          <Stat label={`Hub weight (${e.hub_weight_method ?? "–"})`}>
            <span className="tabular">{e.hub_weight?.toFixed(4) ?? "–"}</span>
          </Stat>
          <Stat label="Hub">
            {e.is_hub ? (
              <Badge variant="outline" className="border-risk-alert text-risk-alert">
                yes: above the later-hop cap
              </Badge>
            ) : (
              "no"
            )}
          </Stat>
        </>
      )}
    </dl>
  );
}

function Links({ e, source }: { e: EntityDetail; source: Source }) {
  if (e.kind === "user") {
    return (
      <Table label="Linked attributes">
        <TableHeader>
          <TableRow>
            <TableHead>Attribute</TableHead>
            <TableHead>Type</TableHead>
            <TableHead className="text-right">Users</TableHead>
            <TableHead className="text-right">Hub weight</TableHead>
            <TableHead>Linked</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(e.attributes ?? []).map((a) => (
            <TableRow key={`${a.kind}:${a.id}`}>
              <TableCell>
                <EntityLink kind={a.kind} id={a.id} source={source} />
              </TableCell>
              <TableCell>{KIND_LABEL[a.kind]}</TableCell>
              <TableCell className="tabular text-right">{a.degree}</TableCell>
              <TableCell className="tabular text-right">{a.hub_weight.toFixed(4)}</TableCell>
              <TableCell className="tabular text-xs">{fmtSimTime(a.t)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  }
  return (
    <Table label="Users linked to this attribute">
      <TableHeader>
        <TableRow>
          <TableHead>User</TableHead>
          <TableHead>Linked</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {(e.users ?? []).map((u) => (
          <TableRow key={u.id}>
            <TableCell>
              <EntityLink kind="user" id={u.id} source={source} />
            </TableCell>
            <TableCell className="tabular text-xs">{fmtSimTime(u.t)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function Transfers({ e, source }: { e: EntityDetail; source: Source }) {
  const t = e.transactions;
  if (!t || !t.items.length) return <p className="text-muted-foreground text-sm">No transfers.</p>;
  return (
    <div className="space-y-2">
      {t.truncated ? (
        <p className="text-muted-foreground text-xs">Showing the latest {t.items.length}.</p>
      ) : null}
      <Table label="Transfers in and out">
        <TableHeader>
          <TableRow>
            <TableHead>Time</TableHead>
            <TableHead>Direction</TableHead>
            <TableHead>Counterparty</TableHead>
            <TableHead className="text-right">Amount</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {t.items.map((x) => (
            <TableRow key={x.txn_id}>
              <TableCell className="tabular text-xs">{fmtSimTime(x.t)}</TableCell>
              <TableCell>{x.direction === "out" ? "sent" : "received"}</TableCell>
              <TableCell>
                <EntityLink kind="user" id={x.counterparty} source={source} />
              </TableCell>
              <TableCell className="tabular text-right">{money(x.amount)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function Timeline({ e }: { e: EntityDetail }) {
  if (!e.timeline.length) return <p className="text-muted-foreground text-sm">No activity.</p>;
  return (
    <ol className="divide-y" aria-label="Activity, newest first">
      {[...e.timeline].reverse().map((x, i) => (
        <li key={i} className="flex flex-wrap gap-x-3 py-1.5 text-sm">
          <span className="tabular text-muted-foreground text-xs">{fmtSimTime(x.t)}</span>
          <span>
            {x.type === "joined"
              ? "joined"
              : x.type === "linked"
                ? `linked ${x.kind === "user" ? "user" : (x.kind ?? "")} ${x.id ?? ""}`
                : `${x.type} ${money(x.amount ?? 0)} ${x.type === "sent" ? "to" : "from"} ${x.counterparty ?? ""}`}
          </span>
        </li>
      ))}
    </ol>
  );
}

function AlertsAndRings({ e }: { e: EntityDetail }) {
  if (!(e.alerts ?? []).length && !(e.rings ?? []).length)
    return (
      <p className="text-muted-foreground text-sm">
        No alerts or tracked rings involve this entity in the current run.
      </p>
    );
  return (
    <div className="space-y-4">
      {(e.alerts ?? []).length ? (
        <ul className="space-y-1.5" aria-label="Alerts">
          {(e.alerts ?? []).map((a) => (
            <li key={a.id} className="flex flex-wrap items-center gap-2 text-sm">
              <Link
                href={`/alerts/${a.id}`}
                className="font-mono underline-offset-4 hover:underline"
              >
                Alert {a.alert_ref}
              </Link>
              <RiskBadge risk={a.risk ?? null} />
              <AlertStatusBadge status={a.status as AlertStatus} />
              <span className="text-muted-foreground capitalize">{words(a.ring_type)}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {(e.rings ?? []).length ? (
        <ul className="space-y-1.5" aria-label="Tracked rings">
          {(e.rings ?? []).map((r) => (
            <li key={r.ring_id} className="flex flex-wrap items-center gap-2 text-sm">
              <Link
                href={`/explorer/rings/${r.ring_id}`}
                className="font-mono underline-offset-4 hover:underline"
              >
                Ring {r.ring_id}
              </Link>
              <Badge variant="outline">{r.status}</Badge>
              <span className="text-muted-foreground">
                <span className="capitalize">{words(r.ring_type)}</span> · {r.members} members
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function EntityView({ kind, id }: { kind: EntityKind; id: string }) {
  const source = useSource();
  const q = useEntity(kind, id, source);
  const Icon = KIND_ICON[kind];

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link href={source === "run" ? "/explorer" : `/explorer?source=${source}`}>
            <ArrowLeft aria-hidden /> Explorer
          </Link>
        </Button>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <Icon className="size-6" aria-hidden />
            <span className="font-mono">{id}</span>
          </h1>
          <SourceSelect />
        </div>
      </div>
      {q.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : q.error ? (
        <QueryError
          error={q.error}
          title={`Could not load this ${KIND_LABEL[kind].toLowerCase()} from the ${SOURCE_LABEL[source].toLowerCase()}`}
          onRetry={() => void q.refetch()}
        />
      ) : (
        <>
          <Card>
            <CardContent>
              <Summary e={q.data} />
            </CardContent>
          </Card>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card className="overflow-hidden">
              <CardHeader>
                <CardTitle>{kind === "user" ? "Attributes" : "Users"}</CardTitle>
              </CardHeader>
              <CardContent className="px-0">
                <Links e={q.data} source={source} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Alerts and rings</CardTitle>
              </CardHeader>
              <CardContent>
                <AlertsAndRings e={q.data} />
              </CardContent>
            </Card>
          </div>
          <NeighbourhoodView
            key={`${source}:${kind}:${id}`}
            seed={nodeKey(kind, id)}
            source={source}
          />
          <div className="grid gap-6 lg:grid-cols-2">
            {kind === "user" ? (
              <Card className="overflow-hidden">
                <CardHeader>
                  <CardTitle>Transfers</CardTitle>
                </CardHeader>
                <CardContent className="px-0">
                  <Transfers e={q.data} source={source} />
                </CardContent>
              </Card>
            ) : null}
            <Card>
              <CardHeader>
                <CardTitle>Timeline</CardTitle>
              </CardHeader>
              <CardContent>
                <Timeline e={q.data} />
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
