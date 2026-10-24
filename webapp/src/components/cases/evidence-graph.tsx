"use client";

import type { Core, ElementDefinition } from "cytoscape";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { words } from "./common";

export interface EvidenceNode {
  id: string;
  type: string;
  joined_t?: number | null;
  degree?: number;
  hub_weight?: number;
}
export interface EvidenceEdge {
  source: string;
  target: string;
  type: "link" | "transfer";
  t?: number;
  amount?: number;
  txn_id?: string;
}
export interface Evidence {
  nodes: EvidenceNode[];
  edges: EvidenceEdge[];
}

function palette() {
  const css = getComputedStyle(document.documentElement);
  const v = (name: string) => css.getPropertyValue(name).trim() || "gray";
  return {
    user: v("--risk-alert"),
    device: v("--node-device"),
    card: v("--node-card"),
    ip: v("--node-ip"),
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
 * The evidence subgraph of one ring: its members, the attributes at least two
 * of them share, and the transfers among them. Cytoscape for the picture, and
 * the same data as tables (the accessible alternative).
 */
export function EvidenceGraph({ evidence }: { evidence: Evidence }) {
  const box = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);
  const [asTable, setAsTable] = useState(false);

  useEffect(() => {
    if (asTable) return;
    let disposed = false;
    void (async () => {
      const { default: cytoscape } = await import("cytoscape");
      if (disposed || !box.current) return;
      const p = palette();
      const els: ElementDefinition[] = [
        ...evidence.nodes.map((n) => ({
          group: "nodes" as const,
          data: {
            id: `${n.type}:${n.id}`,
            label: n.type === "user" ? n.id : `${n.id} (${n.degree ?? "?"})`,
            color: n.type === "user" ? p.user : (p[n.type as "device"] ?? p.ink),
            shape: n.type === "user" ? "ellipse" : (SHAPE[n.type] ?? "diamond"),
          },
        })),
        ...evidence.edges.map((e, i) => {
          const targetType =
            e.type === "transfer"
              ? "user"
              : (evidence.nodes.find((n) => n.id === e.target && n.type !== "user")?.type ?? "");
          return {
            group: "edges" as const,
            data: {
              id: `e${i}`,
              source: `user:${e.source}`,
              target: `${targetType}:${e.target}`,
              kind: e.type,
            },
          };
        }),
      ];
      cy.current = cytoscape({
        container: box.current,
        elements: els,
        wheelSensitivity: 0.3,
        minZoom: 0.3,
        maxZoom: 3,
        style: [
          {
            selector: "node",
            style: {
              "background-color": "data(color)",
              shape: "data(shape)" as never,
              width: 18,
              height: 18,
              label: "data(label)",
              "font-size": 8,
              color: p.ink,
              "text-valign": "bottom",
              "text-margin-y": 3,
            },
          },
          {
            selector: "edge",
            style: { width: 1, "line-color": p.line, "curve-style": "haystack" },
          },
          {
            selector: 'edge[kind = "transfer"]',
            style: {
              width: 1.5,
              "line-color": p.ink,
              "target-arrow-shape": "triangle",
              "target-arrow-color": p.ink,
              "curve-style": "bezier",
              opacity: 0.7,
            },
          },
        ],
        layout: { name: "cose", animate: false, randomize: false },
      });
    })();
    return () => {
      disposed = true;
      cy.current?.destroy();
      cy.current = null;
    };
  }, [evidence, asTable]);

  const members = evidence.nodes.filter((n) => n.type === "user");
  const shared = evidence.nodes.filter((n) => n.type !== "user");
  const transfers = evidence.edges.filter((e) => e.type === "transfer");
  const links = evidence.edges.filter((e) => e.type === "link");

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-muted-foreground text-sm">
          {members.length} members, {shared.length} shared attributes, {transfers.length} transfers
          among members.
        </p>
        <Button
          variant="outline"
          size="sm"
          aria-pressed={asTable}
          onClick={() => setAsTable((t) => !t)}
        >
          {asTable ? "Show as graph" : "Show as table"}
        </Button>
      </div>
      {asTable ? (
        <div key="table" className="space-y-4">
          <Table label="Shared attributes">
            <caption className="text-muted-foreground mb-2 text-left text-sm">
              Shared attributes (degree = accounts using it in the whole graph)
            </caption>
            <TableHeader>
              <TableRow>
                <TableHead>Attribute</TableHead>
                <TableHead>Kind</TableHead>
                <TableHead className="text-right">Degree</TableHead>
                <TableHead>Members using it</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {shared.map((n) => (
                <TableRow key={`${n.type}:${n.id}`}>
                  <TableCell className="font-mono text-xs">{n.id}</TableCell>
                  <TableCell>{words(n.type)}</TableCell>
                  <TableCell className="tabular text-right">{n.degree ?? "–"}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {links
                      .filter((l) => l.target === n.id)
                      .map((l) => l.source)
                      .join(", ")}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Table label="Transfers among members">
            <caption className="text-muted-foreground mb-2 text-left text-sm">
              Transfers among members (simulated time in seconds)
            </caption>
            <TableHeader>
              <TableRow>
                <TableHead>From</TableHead>
                <TableHead>To</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead className="text-right">Time (s)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {transfers.length ? (
                transfers.map((t, i) => (
                  <TableRow key={t.txn_id ?? i}>
                    <TableCell className="font-mono text-xs">{t.source}</TableCell>
                    <TableCell className="font-mono text-xs">{t.target}</TableCell>
                    <TableCell className="tabular text-right">{t.amount?.toFixed(2)}</TableCell>
                    <TableCell className="tabular text-right">{t.t?.toFixed(1)}</TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={4} className="text-muted-foreground">
                    No transfers among members.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      ) : (
        <div
          key="graph"
          ref={box}
          className="bg-muted/30 h-[420px] w-full rounded-lg border"
          role="img"
          aria-label={`Evidence graph: ${members.length} members linked by ${shared.length} shared attributes and ${transfers.length} transfers. Use "Show as table" for the data.`}
        />
      )}
    </div>
  );
}
