"use client";

import type { Core, ElementDefinition } from "cytoscape";
import { Download, GitCompareArrows, Pin, PinOff, RotateCcw, ScanSearch } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { QueryError } from "@/components/cases/common";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
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
import {
  compareUsers,
  fromUtcInput,
  KIND_LABEL,
  type MergedGraph,
  type MergedNode,
  mergeNeighbourhoods,
  parseKey,
  type Rel,
  RELS,
  type Source,
  toUtcInput,
} from "@/lib/explorer/graph";
import { setPinned, usePinned } from "@/lib/explorer/pinned";
import {
  DEFAULT_PARAMS,
  type NeighbourhoodParams,
  useNeighbourhoods,
} from "@/lib/explorer/queries";

import { entityHref } from "./common";

const REL_LABEL: Record<Rel, string> = {
  device: "Devices",
  card: "Cards",
  ip: "IP addresses",
  transfer: "Transfers",
};
const SHAPE: Record<string, string> = {
  user: "ellipse",
  device: "round-rectangle",
  card: "rectangle",
  ip: "hexagon",
};

function palette() {
  const css = getComputedStyle(document.documentElement);
  const v = (name: string) => css.getPropertyValue(name).trim() || "gray";
  return {
    user: v("--benign"),
    a: v("--node-ip"),
    b: v("--risk-confirmed"),
    both: v("--risk-alert"),
    device: v("--node-device"),
    card: v("--node-card"),
    ip: v("--node-hub"),
    stop: v("--risk-alert"),
    line: v("--border"),
    ink: v("--foreground"),
  };
}

function numberOrNull(v: string): number | null {
  const n = Number(v);
  return v.trim() && Number.isInteger(n) && n > 0 ? n : null;
}

function Controls({
  value,
  onChange,
}: {
  value: NeighbourhoodParams;
  onChange: (p: NeighbourhoodParams) => void;
}) {
  const [maxF, setMaxF] = useState(value.max_fanout?.toString() ?? "");
  const [farF, setFarF] = useState(value.far_fanout?.toString() ?? "");
  const set = <K extends keyof NeighbourhoodParams>(k: K, v: NeighbourhoodParams[K]) =>
    onChange({ ...value, [k]: v });
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <div className="space-y-1">
        <Label htmlFor="nb-k">Hops (k)</Label>
        <Select value={String(value.k)} onValueChange={(v) => set("k", Number(v))}>
          <SelectTrigger id="nb-k" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {[1, 2, 3].map((k) => (
              <SelectItem key={k} value={String(k)}>
                {k}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <fieldset className="space-y-1">
        <legend className="text-sm leading-none font-medium">Follow</legend>
        <div className="flex flex-wrap gap-x-3 gap-y-1 pt-1">
          {RELS.map((r) => (
            <label key={r} className="flex items-center gap-1.5 text-sm">
              <Checkbox
                checked={value.rels.includes(r)}
                onCheckedChange={(on) =>
                  set("rels", on ? [...value.rels, r] : value.rels.filter((x) => x !== r))
                }
              />
              {REL_LABEL[r]}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="space-y-1">
        <Label htmlFor="nb-since">From (UTC, simulated)</Label>
        <Input
          id="nb-since"
          type="datetime-local"
          step={1}
          value={toUtcInput(value.since_t)}
          onChange={(e) => set("since_t", fromUtcInput(e.target.value))}
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="nb-until">To (UTC, simulated)</Label>
        <Input
          id="nb-until"
          type="datetime-local"
          step={1}
          value={toUtcInput(value.until_t)}
          onChange={(e) => set("until_t", fromUtcInput(e.target.value))}
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="nb-max-fanout">First-hop cap</Label>
        <Input
          id="nb-max-fanout"
          inputMode="numeric"
          placeholder="engine default"
          value={maxF}
          onChange={(e) => setMaxF(e.target.value)}
          onBlur={() => set("max_fanout", numberOrNull(maxF))}
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="nb-far-fanout">Later-hop cap</Label>
        <Input
          id="nb-far-fanout"
          inputMode="numeric"
          placeholder="engine default"
          value={farF}
          onChange={(e) => setFarF(e.target.value)}
          onBlur={() => set("far_fanout", numberOrNull(farF))}
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="nb-max-nodes">Node limit</Label>
        <Select value={String(value.max_nodes)} onValueChange={(v) => set("max_nodes", Number(v))}>
          <SelectTrigger id="nb-max-nodes" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {[100, 200, 400, 800].map((n) => (
              <SelectItem key={n} value={String(n)}>
                {n}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}

function GraphCanvas({
  graph,
  compare,
  onTap,
  cyRef,
}: {
  graph: MergedGraph;
  compare: boolean;
  onTap: (key: string) => void;
  cyRef: React.RefObject<Core | null>;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  const tap = useRef(onTap);
  useEffect(() => {
    tap.current = onTap;
  }, [onTap]);

  useEffect(() => {
    let disposed = false;
    void (async () => {
      const [{ default: cytoscape }, { default: svg }] = await Promise.all([
        import("cytoscape"),
        import("cytoscape-svg"),
      ]);
      if (disposed || !box.current) return;
      cytoscape.use(svg);
      const c = cytoscape({ container: box.current, wheelSensitivity: 0.3, minZoom: 0.2 });
      c.on("tap", "node", (e) => tap.current(String(e.target.id())));
      cyRef.current = c;
      setReady(true);
    })();
    return () => {
      disposed = true;
      cyRef.current?.destroy();
      cyRef.current = null;
    };
  }, [cyRef]);

  useEffect(() => {
    const c = cyRef.current;
    if (!c) return;
    const p = palette();
    const userColor = (n: MergedNode) => {
      if (!compare) return n.seed ? p.a : p.user;
      const a = n.from.includes("A");
      const b = n.from.includes("B");
      return a && b ? p.both : b ? p.b : p.a;
    };
    const els: ElementDefinition[] = [
      ...graph.nodes.map((n) => ({
        group: "nodes" as const,
        data: {
          id: n.key,
          label: n.kind === "user" ? n.id : `${n.id} (${n.degree ?? "?"})`,
          color: n.kind === "user" ? userColor(n) : p[n.kind],
          shape: SHAPE[n.kind],
          size: n.kind === "user" ? 16 : Math.min(36, 14 + Math.sqrt(n.degree ?? 1) * 3),
          border: n.seed ? 4 : n.stop?.cap != null ? 3 : 0,
          borderColor: n.seed ? p.ink : p.stop,
          borderStyle: n.stop?.cap != null ? "dashed" : "solid",
        },
      })),
      ...graph.edges.map((e) => ({
        group: "edges" as const,
        data: {
          id: e.id,
          source: e.source,
          target: e.target,
          kind: e.kind,
          width: e.kind === "transfer" ? 1.5 : 0.6 + 2.4 * (e.weight ?? 0.3),
        },
      })),
    ];
    c.batch(() => {
      c.elements().remove();
      c.add(els);
      c.style([
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            shape: "data(shape)" as never,
            width: "data(size)",
            height: "data(size)",
            label: "data(label)",
            "font-size": 8,
            color: p.ink,
            "text-valign": "bottom",
            "text-margin-y": 2,
            "border-width": "data(border)",
            "border-color": "data(borderColor)",
            "border-style": "data(borderStyle)" as never,
          },
        },
        {
          selector: "edge",
          style: { width: "data(width)", "line-color": p.line, "curve-style": "haystack" },
        },
        {
          selector: 'edge[kind = "transfer"]',
          style: {
            "line-color": p.ink,
            "target-arrow-shape": "triangle",
            "target-arrow-color": p.ink,
            "curve-style": "bezier",
            opacity: 0.7,
          },
        },
      ]);
    });
    c.layout({ name: "cose", animate: false, randomize: false }).run();
  }, [graph, compare, cyRef, ready]);

  return (
    <div
      ref={box}
      className="bg-muted/30 h-[480px] w-full rounded-lg border"
      role="img"
      aria-label={`Neighbourhood graph: ${graph.nodes.length} nodes and ${graph.edges.length} edges. The node table below lists the same data.`}
    />
  );
}

function download(href: string, name: string) {
  Object.assign(document.createElement("a"), { href, download: name }).click();
}

/**
 * The k-hop neighbourhood of one entity, with the detector's hub caps. Clicking
 * a node (or Expand in the table) adds its one-hop neighbourhood; a pinned
 * entity can be compared on the same canvas.
 */
export function NeighbourhoodView({ seed, source }: { seed: string; source: Source }) {
  const [params, setParams] = useState<NeighbourhoodParams>(DEFAULT_PARAMS);
  const [expanded, setExpanded] = useState<string[]>([]);
  const [compare, setCompare] = useState(false);
  const [showTable, setShowTable] = useState(false);
  const cy = useRef<Core | null>(null);
  const pinnedRaw = usePinned();
  const [pinSource, pinKey] = pinnedRaw?.split("|") ?? [null, null];
  const pinned = pinSource === source && pinKey && pinKey !== seed ? pinKey : null;
  const comparing = compare && pinned !== null;
  const seeds = comparing ? [seed, pinned] : [seed];

  const results = useNeighbourhoods(source, seeds, expanded, params);
  const error = results.find((r) => r.error)?.error ?? null;
  const pending = results.some((r) => r.isPending);
  const graph = useMemo(() => {
    const parts = results.flatMap((r, i) =>
      r.data ? [{ label: i === 0 ? "A" : i === 1 && comparing ? "B" : `+${i}`, nb: r.data }] : [],
    );
    return mergeNeighbourhoods(parts);
  }, [results, comparing]);
  const params0 = results[0]?.data?.params as Record<string, unknown> | undefined;
  const cmp = comparing ? compareUsers(graph, "A", "B") : null;
  const stops = graph.nodes.filter((n) => n.stop?.cap != null);

  function expand(key: string) {
    if (key === seed || expanded.includes(key)) return;
    setExpanded((x) => [...x, key]);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Neighbourhood</CardTitle>
        <CardDescription>
          The walk the detector makes: one hop is a shared device, card or IP, or a transfer.
          Attributes busier than the cap are shown with a dashed red border but not crossed. Edge
          width is the hub weight. Click a node to expand it by one hop.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Controls
          value={params}
          onChange={(p) => {
            setParams(p);
            setExpanded([]);
          }}
        />
        <div className="flex flex-wrap items-center gap-2">
          {pinnedRaw === `${source}|${seed}` ? (
            <Button variant="outline" size="sm" onClick={() => setPinned(null)}>
              <PinOff aria-hidden /> Unpin
            </Button>
          ) : (
            <Button variant="outline" size="sm" onClick={() => setPinned(`${source}|${seed}`)}>
              <Pin aria-hidden /> Pin to compare
            </Button>
          )}
          {pinned ? (
            <Button
              variant={comparing ? "default" : "outline"}
              size="sm"
              aria-pressed={comparing}
              onClick={() => setCompare((c) => !c)}
            >
              <GitCompareArrows aria-hidden /> Compare with {pinned}
            </Button>
          ) : null}
          {expanded.length ? (
            <Button variant="ghost" size="sm" onClick={() => setExpanded([])}>
              <RotateCcw aria-hidden /> Collapse {expanded.length} expansion
              {expanded.length > 1 ? "s" : ""}
            </Button>
          ) : null}
          <span className="flex-1" />
          <Button
            variant="outline"
            size="sm"
            disabled={!graph.nodes.length}
            onClick={() =>
              cy.current &&
              download(
                cy.current.png({
                  full: true,
                  scale: 2,
                  bg: getComputedStyle(document.body).backgroundColor,
                }),
                `neighbourhood-${seed}.png`,
              )
            }
          >
            <Download aria-hidden /> PNG
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!graph.nodes.length}
            onClick={() => {
              const c = cy.current as unknown as { svg: (o: object) => string } | null;
              if (c)
                download(
                  URL.createObjectURL(new Blob([c.svg({ full: true })], { type: "image/svg+xml" })),
                  `neighbourhood-${seed}.svg`,
                );
            }}
          >
            <Download aria-hidden /> SVG
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!graph.nodes.length}
            onClick={() =>
              download(
                URL.createObjectURL(
                  new Blob(
                    [
                      JSON.stringify(
                        { source, params: params0, expanded, compare: pinned, ...graph },
                        null,
                        2,
                      ),
                    ],
                    { type: "application/json" },
                  ),
                ),
                `neighbourhood-${seed}.json`,
              )
            }
          >
            <Download aria-hidden /> JSON
          </Button>
        </div>

        {error ? (
          <QueryError
            error={error}
            title="Could not load the neighbourhood"
            onRetry={() => results.forEach((r) => void r.refetch())}
          />
        ) : null}
        {graph.truncated ? (
          <Alert>
            <ScanSearch aria-hidden />
            <AlertTitle>Node limit reached</AlertTitle>
            <AlertDescription>
              The walk stopped at {params.max_nodes} nodes. Lower k, follow fewer relationship
              types, narrow the time window or raise the limit.
            </AlertDescription>
          </Alert>
        ) : null}
        {cmp ? (
          <p className="text-sm" aria-live="polite">
            Users reached from both: <strong className="tabular">{cmp.both.length}</strong>
            {cmp.both.length ? ` (${cmp.both.join(", ")})` : ""} · only from {seed}:{" "}
            <span className="tabular">{cmp.onlyA.length}</span> · only from {pinned}:{" "}
            <span className="tabular">{cmp.onlyB.length}</span>
          </p>
        ) : null}

        {pending && !graph.nodes.length ? (
          <Skeleton className="h-[480px] w-full" />
        ) : (
          <GraphCanvas graph={graph} compare={comparing} onTap={expand} cyRef={cy} />
        )}

        <p className="text-muted-foreground text-xs">
          {params0
            ? `Caps: first hop ${String(params0.max_fanout)} users, later hops ${String(
                params0.far_fanout,
              )} (hub weight ${String(params0.hub_weight_method)}). `
            : ""}
          {stops.length
            ? `Stopped at ${stops.length} hub${stops.length > 1 ? "s" : ""}: ${stops
                .map((n) => `${n.id} (${n.stop?.reason})`)
                .join("; ")}.`
            : "No hub stopped the walk."}
        </p>

        <Button
          variant="outline"
          size="sm"
          aria-expanded={showTable}
          aria-controls="nb-table"
          onClick={() => setShowTable((t) => !t)}
        >
          {showTable ? "Hide" : "Show"} the node table ({graph.nodes.length} nodes)
        </Button>
        {showTable ? (
          <div id="nb-table">
            <Table label="Neighbourhood nodes">
              <TableHeader>
                <TableRow>
                  <TableHead>Node</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Hop</TableHead>
                  <TableHead className="text-right">Degree</TableHead>
                  <TableHead className="text-right">Hub weight</TableHead>
                  <TableHead>Walk</TableHead>
                  {comparing ? <TableHead>Reached from</TableHead> : null}
                  <TableHead>
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {graph.nodes.map((n) => {
                  const parsed = parseKey(n.key);
                  return (
                    <TableRow key={n.key}>
                      <TableCell>
                        <Link
                          href={parsed ? entityHref(parsed.kind, parsed.id, source) : "#"}
                          className="font-mono text-xs underline-offset-4 hover:underline"
                        >
                          {n.id}
                        </Link>
                        {n.seed ? (
                          <Badge variant="outline" className="ml-2">
                            seed
                          </Badge>
                        ) : null}
                      </TableCell>
                      <TableCell>{KIND_LABEL[n.kind]}</TableCell>
                      <TableCell className="tabular text-right">{n.hop}</TableCell>
                      <TableCell className="tabular text-right">{n.degree ?? "–"}</TableCell>
                      <TableCell className="tabular text-right">
                        {n.hub_weight?.toFixed(3) ?? "–"}
                      </TableCell>
                      <TableCell className="text-xs whitespace-normal">
                        {n.stop ? (
                          <span className={n.stop.cap != null ? "text-risk-alert" : undefined}>
                            stopped: {n.stop.reason}
                          </span>
                        ) : n.kind === "user" ? (
                          "reached"
                        ) : (
                          "crossed"
                        )}
                      </TableCell>
                      {comparing ? (
                        <TableCell className="text-xs">
                          {n.from
                            .filter((f) => f === "A" || f === "B")
                            .map((f) => (f === "A" ? seed : pinned))
                            .join(", ")}
                        </TableCell>
                      ) : null}
                      <TableCell className="text-right">
                        {n.key !== seed && !expanded.includes(n.key) ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => expand(n.key)}
                            aria-label={`Expand ${n.id} by one hop`}
                          >
                            Expand
                          </Button>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
