"""
Static SVG charts for reports, drawn server-side with matplotlib in the paper's
style (experiments/plotting.py). Output is byte-stable for the same input: no
date metadata, a fixed hash salt for element ids, text kept as text, and a
seeded layout for graphs.

ASSUMPTION: the evidence subgraph is drawn here (networkx layout, matplotlib)
rather than captured from Cytoscape in a browser during the build. It is
deterministic (the golden test needs that) and needs no JavaScript at build time.
"""

from __future__ import annotations

import io
import re
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx  # type: ignore[import-untyped]

from fraudsim.experiments.plotting import COLORS

RC = {
    "font.size": 8,
    "axes.titlesize": 8,
    "axes.labelsize": 8,
    "svg.fonttype": "none",
    "svg.hashsalt": "fraudsim-report",
    "font.family": "sans-serif",
}
KIND_COLOR = {"user": "#b93a31", "device": "#7a5cc7", "card": "#1f9a92", "ip": "#3d6fd6"}


def _svg(fig: Any) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", metadata={"Date": None, "Creator": None}, bbox_inches="tight")
    plt.close(fig)
    text = buf.getvalue()
    # Inline in HTML: drop the XML prolog and DOCTYPE.
    return re.sub(r"^.*?(<svg)", r"\1", text, count=1, flags=re.S)


def contributions_svg(contrib: dict[str, float], top: int = 10) -> str | None:
    """Horizontal bars: feature contribution to the raw log-odds (largest |value| first)."""
    rows = sorted(contrib.items(), key=lambda kv: (-abs(kv[1]), kv[0]))[:top]
    if not rows:
        return None
    with plt.rc_context(RC):
        fig, ax = plt.subplots(figsize=(4.2, 0.28 * len(rows) + 0.6))
        names = [n.replace("_", " ") for n, _ in reversed(rows)]
        vals = [v for _, v in reversed(rows)]
        ax.barh(
            names,
            vals,
            color=[COLORS["cap"] if v >= 0 else COLORS["proposed"] for v in vals],
        )
        ax.axvline(0, color="#6e7781", linewidth=0.6)
        ax.set_xlabel("contribution to log-odds (+ raises risk)")
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        return _svg(fig)


def evidence_svg(evidence: dict[str, Any], max_nodes: int = 80) -> str | None:
    """Members, shared attributes and transfers among members (seeded spring layout)."""
    nodes = evidence.get("nodes") or []
    if not nodes:
        return None
    g = nx.Graph()
    kinds: dict[str, str] = {}
    for n in sorted(nodes, key=lambda n: (n.get("type", ""), str(n["id"])))[:max_nodes]:
        key = f"{n.get('type', 'user')}:{n['id']}"
        kinds[key] = n.get("type", "user")
        g.add_node(key, label=str(n["id"]))
    links: list[tuple[str, str]] = []
    transfers: list[tuple[str, str]] = []
    for e in evidence.get("edges") or []:
        s = f"user:{e['source']}"
        t = (
            f"user:{e['target']}"
            if e.get("type") == "transfer"
            else next(
                (k for k in kinds if k.endswith(f":{e['target']}") and kinds[k] != "user"), ""
            )
        )
        if s in kinds and t in kinds:
            (transfers if e.get("type") == "transfer" else links).append((s, t))
            g.add_edge(s, t)
    pos = nx.spring_layout(g, seed=7, k=0.9)
    with plt.rc_context(RC):
        fig, ax = plt.subplots(figsize=(4.6, 3.2))
        nx.draw_networkx_edges(g, pos, edgelist=links, ax=ax, edge_color="#b3b7bd", width=0.8)
        nx.draw_networkx_edges(
            nx.DiGraph(transfers),
            pos,
            ax=ax,
            edge_color="#222222",
            width=1.0,
            arrows=True,
            arrowsize=8,
        )
        for kind, marker in (("user", "o"), ("device", "s"), ("card", "D"), ("ip", "h")):
            nl = sorted(k for k, v in kinds.items() if v == kind)
            if nl:
                nx.draw_networkx_nodes(
                    g,
                    pos,
                    nodelist=nl,
                    node_color=KIND_COLOR[kind],
                    node_shape=marker,
                    node_size=90,
                    ax=ax,
                    label=kind,
                )
        # Labels just below their node, so they do not cover it.
        ys = [y for _, y in pos.values()]
        dy = 0.07 * ((max(ys) - min(ys)) or 1.0)
        nx.draw_networkx_labels(
            g,
            {k: (x, y - dy) for k, (x, y) in pos.items()},
            labels={k: g.nodes[k]["label"] for k in g.nodes},
            font_size=5,
            ax=ax,
        )
        ax.legend(loc="lower left", fontsize=6, frameon=False, markerscale=0.6)
        ax.set_axis_off()
        return _svg(fig)
