"use client";

import { useQuery } from "@tanstack/react-query";
import type { Core, ElementDefinition } from "cytoscape";
import { Download, Target } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { api, toApiError } from "@/lib/api/client";

interface GNode {
  id: string;
  kind: string;
  status?: string | null;
  risk?: number | null;
  truth?: string | null;
  degree?: number;
  hub?: boolean;
}
interface GEdge {
  id: string;
  source: string;
  target: string;
  kind: string;
  count?: number;
}

/** CSS custom properties as concrete colours (Cytoscape cannot read var()). */
function palette() {
  const css = getComputedStyle(document.documentElement);
  const v = (name: string) => css.getPropertyValue(name).trim() || "gray";
  return {
    alert: v("--risk-alert"),
    confirmed: v("--risk-confirmed"),
    candidate: v("--risk-candidate"),
    benign: v("--benign"),
    device: v("--node-device"),
    card: v("--node-card"),
    ip: v("--node-ip"),
    hub: v("--node-hub"),
    warn: v("--warn"),
    line: v("--border"),
    ink: v("--foreground"),
  };
}

const SHAPE: Record<string, string> = {
  device: "round-rectangle",
  card: "rectangle",
  ip: "hexagon",
};

/**
 * The live run's graph (Cytoscape): users by detection status, devices/cards/IPs
 * by kind and shape, hubs sized by degree, transfers as arrows. Windowed and
 * capped on the server. The Oracle overlay (simulator ground truth) colours
 * true positives, false positives and missed fraud; it is off by default.
 */
export function LiveGraph({ active }: { active: boolean }) {
  const box = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);
  const [oracle, setOracle] = useState(false);
  const [maxUsers, setMaxUsers] = useState(200);
  const [windowS, setWindowS] = useState(60);

  const graph = useQuery({
    queryKey: ["runs", "graph", maxUsers, windowS, oracle],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/runs/current/graph", {
        params: { query: { max_users: maxUsers, window_s: windowS, oracle } },
      });
      if (!data) throw toApiError(error, response);
      return data as unknown as {
        nodes: GNode[];
        edges: GEdge[];
        shown_users: number;
        total_active_users: number;
      };
    },
    enabled: active,
    refetchInterval: active ? 1500 : false,
  });

  useEffect(() => {
    let disposed = false;
    void (async () => {
      const [{ default: cytoscape }, { default: svg }] = await Promise.all([
        import("cytoscape"),
        import("cytoscape-svg"),
      ]);
      if (disposed || !box.current) return;
      cytoscape.use(svg);
      cy.current = cytoscape({
        container: box.current,
        wheelSensitivity: 0.3,
        minZoom: 0.2,
        maxZoom: 4,
      });
    })();
    return () => {
      disposed = true;
      cy.current?.destroy();
      cy.current = null;
    };
  }, []);

  useEffect(() => {
    const c = cy.current;
    const g = graph.data;
    if (!c || !g) return;
    const p = palette();
    const userColor = (n: GNode) => {
      if (oracle) {
        const fraud = !!n.truth;
        if (n.status && fraud) return p.alert; // true positive
        if (n.status) return p.warn; // false positive
        return p.benign;
      }
      if (n.status === "alert") return p.alert;
      if (n.status === "confirmed") return p.confirmed;
      if (n.status === "candidate") return p.candidate;
      return p.benign;
    };
    const els: ElementDefinition[] = [
      ...g.nodes.map((n) => ({
        group: "nodes" as const,
        data: {
          id: n.id,
          label: n.kind === "user" ? "" : n.hub ? `${n.id} (${n.degree})` : "",
          color:
            n.kind === "user" ? userColor(n) : n.hub ? p.hub : (p[n.kind as "device"] ?? p.ink),
          shape: n.kind === "user" ? "ellipse" : (SHAPE[n.kind] ?? "diamond"),
          size: n.kind === "user" ? 10 : Math.min(40, 12 + Math.sqrt(n.degree ?? 1) * 4),
          border: oracle && n.kind === "user" && n.truth && !n.status ? 3 : 0,
        },
      })),
      ...g.edges.map((e) => ({
        group: "edges" as const,
        data: { id: e.id, source: e.source, target: e.target, kind: e.kind },
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
            "font-size": 9,
            color: p.ink,
            "border-width": "data(border)",
            "border-color": p.alert,
          },
        },
        {
          selector: "edge",
          style: { width: 0.6, "line-color": p.line, "curve-style": "haystack" },
        },
        {
          selector: 'edge[kind = "transfer"]',
          style: {
            width: 1.2,
            "line-color": p.ink,
            "target-arrow-shape": "triangle",
            "target-arrow-color": p.ink,
            "curve-style": "bezier",
            opacity: 0.6,
          },
        },
      ]);
    });
    c.layout({
      name: "cose",
      animate: false,
      randomize: false,
      nodeRepulsion: () => 6000,
      idealEdgeLength: () => 40,
    }).run();
  }, [graph.data, oracle]);

  const exportAs = (kind: "png" | "svg") => {
    const c = cy.current;
    if (!c) return;
    const href =
      kind === "png"
        ? c.png({ full: true, scale: 2, bg: getComputedStyle(document.body).backgroundColor })
        : URL.createObjectURL(
            new Blob([(c as unknown as { svg: (o: object) => string }).svg({ full: true })], {
              type: "image/svg+xml",
            }),
          );
    Object.assign(document.createElement("a"), {
      href,
      download: `fraudsim-graph.${kind}`,
    }).click();
  };

  const g = graph.data;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Live graph</CardTitle>
        <CardDescription>
          {g
            ? `${g.shown_users} of ${g.total_active_users} active users shown (window ${windowS} s)`
            : "Starts with a run."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <Label htmlFor="max-users" className="text-xs">
              Max users
            </Label>
            <select
              id="max-users"
              value={maxUsers}
              onChange={(e) => setMaxUsers(Number(e.target.value))}
              className="border-input bg-background h-8 rounded-md border px-2 text-sm"
            >
              {[100, 200, 400, 800].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="window" className="text-xs">
              Window (simulated s)
            </Label>
            <select
              id="window"
              value={windowS}
              onChange={(e) => setWindowS(Number(e.target.value))}
              className="border-input bg-background h-8 rounded-md border px-2 text-sm"
            >
              {[30, 60, 120, 300].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </div>
          <Button
            size="sm"
            variant={oracle ? "default" : "outline"}
            aria-pressed={oracle}
            onClick={() => setOracle((o) => !o)}
          >
            <Target aria-hidden /> Oracle (simulator ground truth)
          </Button>
          <Button size="sm" variant="outline" onClick={() => exportAs("png")} disabled={!g}>
            <Download aria-hidden /> PNG
          </Button>
          <Button size="sm" variant="outline" onClick={() => exportAs("svg")} disabled={!g}>
            <Download aria-hidden /> SVG
          </Button>
        </div>
        <div
          ref={box}
          className="bg-background h-[480px] w-full rounded-md border"
          role="img"
          aria-label="Live transaction graph"
        />
        <ul
          className="text-muted-foreground flex flex-wrap gap-x-4 gap-y-1 text-xs"
          aria-label="Legend"
        >
          {(oracle
            ? [
                ["bg-risk-alert", "fraud, flagged (true positive)"],
                ["bg-warn", "legitimate, flagged (false positive)"],
                ["border-2 border-risk-alert", "fraud, not flagged (missed)"],
                ["bg-benign", "not flagged"],
              ]
            : [
                ["bg-risk-alert", "alert"],
                ["bg-risk-confirmed", "confirmed ring"],
                ["bg-risk-candidate", "candidate ring"],
                ["bg-benign", "not in a ring"],
              ]
          ).map(([cls, l]) => (
            <li key={l} className="flex items-center gap-1.5">
              <span className={`inline-block size-3 rounded-full ${cls}`} aria-hidden />
              {l}
            </li>
          ))}
          <li className="flex items-center gap-1.5">
            <span className="bg-node-device inline-block size-3 rounded-sm" aria-hidden /> device
          </li>
          <li className="flex items-center gap-1.5">
            <span className="bg-node-card inline-block size-3" aria-hidden /> card
          </li>
          <li className="flex items-center gap-1.5">
            <span className="bg-node-ip inline-block size-3" aria-hidden /> IP
          </li>
          <li className="flex items-center gap-1.5">
            <span className="bg-node-hub inline-block size-3 rounded-sm" aria-hidden /> benign hub
          </li>
        </ul>
      </CardContent>
    </Card>
  );
}
