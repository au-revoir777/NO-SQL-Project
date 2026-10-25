"""
Architecture figure for the paper, in the style of IEEE graph-fraud papers:
white background, Times labels, small coloured node glyphs, mini graph sketches,
stacked feature vectors, dashed stage separators and a legend row.

One list of primitives is written twice, so the two outputs cannot drift apart:
  docs/paper/figures/architecture.drawio   editable source (draw.io / diagrams.net)
  docs/paper/figures/architecture.pdf/.png rendered with matplotlib

With the draw.io desktop app, an exact export of the source is:
    drawio -x -f pdf -o docs/paper/figures/architecture.pdf docs/paper/figures/architecture.drawio

    python scripts/make_architecture.py
"""

from __future__ import annotations

import html
import math
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle

OUT = Path(__file__).resolve().parents[1] / "docs" / "paper" / "figures"
W, H = 1200, 440
FONT = "Times New Roman"

BENIGN = "#2e9e4f"  # green, as in the reference papers
FRAUD = "#ef7d22"  # orange
NEUTRAL = "#9aa0a6"  # grey: attributes / unknown
HUB = "#6b7280"
BLUE = "#8db4e2"
LINE = "#1f2328"
PANEL = "#5b8bd0"


@dataclass
class Shape:
    kind: str  # rect | ellipse | text | edge
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0
    label: str = ""
    fill: str = "none"
    stroke: str = LINE
    dashed: bool = False
    rounded: bool = True
    size: float = 10
    bold: bool = False
    italic: bool = False
    align: str = "center"
    lw: float = 1.0
    arrow: bool = True
    points: list[tuple[float, float]] = field(default_factory=list)


S: list[Shape] = []


def rect(x, y, w, h, label="", fill="#ffffff", stroke=LINE, **kw):  # type: ignore[no-untyped-def]
    S.append(Shape("rect", x, y, w, h, label, fill, stroke, **kw))


def node(cx, cy, r, fill, label="", stroke="none", **kw):  # type: ignore[no-untyped-def]
    S.append(Shape("ellipse", cx - r, cy - r, 2 * r, 2 * r, label, fill, stroke, **kw))


def text(x, y, s, size=10, **kw):  # type: ignore[no-untyped-def]
    S.append(Shape("text", x, y, 0, 0, s, size=size, **kw))


def edge(*pts, dashed=False, arrow=True, lw=1.0, stroke=LINE):  # type: ignore[no-untyped-def]
    S.append(Shape("edge", points=list(pts), dashed=dashed, arrow=arrow, lw=lw, stroke=stroke))


def vector(x, y, colors, cell=9):  # type: ignore[no-untyped-def]
    """A stacked feature vector, as drawn in GNN papers."""
    for i, c in enumerate(colors):
        rect(x, y + i * cell, cell, cell, fill=c, stroke=LINE, rounded=False, lw=0.6)


# ── Layout: five equal-height stage panels, flow left to right at MID ───────
TOP, BOT, MID = 76, 352, 214
PANEL_FILL = "#f6f8fb"
PANELS = [
    (20, 220, "(a) Seeded simulator"),
    (250, 470, "(b) Incremental region"),
    (500, 690, "(c) Hub-aware weighting"),
    (720, 890, "(d) Detect and track"),
    (920, 1180, "(e) Score and explain"),
]
for x0, x1, title in PANELS:
    rect(x0, TOP, x1 - x0, BOT - TOP, fill=PANEL_FILL, stroke=PANEL, lw=1.0)
    text((x0 + x1) / 2, 60, title, 9.5, bold=True)
for x0, x1 in ((220, 250), (470, 500), (690, 720)):
    edge((x0, MID), (x1, MID), lw=1.2)

# ── Closed loop: alerts go back to the adaptive attacker ────────────────────
text(600, 14, "Closed loop (feedback runs): alerts are returned to the attacker", 10.5, bold=True)
edge((1160, TOP), (1160, 30), (10, 30), (10, 320), (36, 320), dashed=True)

# ── (a) Simulator ───────────────────────────────────────────────────────────
text(120, 88, "scenario + seed", 9, italic=True)
pts = {
    "u1": (58, 118),
    "u2": (92, 106),
    "u3": (80, 142),
    "r1": (150, 110),
    "r2": (182, 130),
    "r3": (146, 148),
}
for a, b in (
    ("u1", "u2"),
    ("u2", "u3"),
    ("u1", "u3"),
    ("r1", "r2"),
    ("r2", "r3"),
    ("r1", "r3"),
    ("u2", "r1"),
):
    edge(pts[a], pts[b], arrow=False, lw=0.8)
for k, (x, y) in pts.items():
    node(x, y, 8, BENIGN if k.startswith("u") else FRAUD)
text(120, 166, "users, hubs, planted rings", 8)
text(110, 190, "event stream, 50 / batch", 8, italic=True)
for i in range(8):
    rect(
        34 + i * 19,
        205,
        13,
        18,
        fill=BLUE if i % 3 else "#c9d9ee",
        stroke=LINE,
        rounded=False,
        lw=0.6,
    )
edge((186, MID), (220, MID), arrow=False, lw=1.2)
rect(36, 252, 130, 36, "ground-truth\nledger (hidden)", fill="#fbe3d6", stroke=FRAUD, size=8.5)
edge((44, 130), (28, 130), (28, 270), (36, 270), dashed=True)
rect(36, 302, 168, 38, "adaptive attacker", fill="#fff4e0", stroke="#d29922", size=9)
edge((186, 302), (186, 224))

# ── (b) Graph store and dirty region ────────────────────────────────────────
text(360, 90, "graph store", 9, italic=True)
S.append(Shape("ellipse", 280, 122, 150, 150, "", "none", "#d1242f", dashed=True, lw=1.0))
hub = (355, 197)
for i in range(12):
    xx = hub[0] + 58 * math.cos(i * 0.52)
    yy = hub[1] + 58 * math.sin(i * 0.52)
    edge(hub, (xx, yy), arrow=False, lw=0.6, stroke="#9aa0a6")
    node(xx, yy, 5.5, BENIGN if i % 4 else FRAUD)
node(*hub, 15, HUB, "hub", size=8.5, stroke="none")
node(446, 150, 7, FRAUD, stroke=LINE)
node(454, 184, 7, FRAUD, stroke=LINE)
edge((446, 150), (454, 184), arrow=False, lw=1.0)
edge((454, 184), (413, 197), arrow=False, lw=1.0)
text(360, 300, "touched users + 2 hops", 8.5)
text(360, 320, "fan-out caps 250 / 20", 8.5)

# ── (c) Hub-aware weighting ─────────────────────────────────────────────────
text(595, 92, "device, d = 3: w = 0.72", 8)
node(545, 126, 9, FRAUD)
node(645, 126, 9, FRAUD)
node(595, 108, 7, NEUTRAL, stroke=LINE)
edge((545, 126), (595, 108), arrow=False, lw=2.6)
edge((595, 108), (645, 126), arrow=False, lw=2.6)
node(545, 172, 9, BENIGN)
node(645, 172, 9, BENIGN)
node(595, 154, 9, HUB, stroke=LINE)
edge((545, 172), (595, 154), arrow=False, lw=0.7)
edge((595, 154), (645, 172), arrow=False, lw=0.7)
text(595, 192, "office IP, d = 50: w = 0.25", 8)
text(595, 244, "W = Σ h(d)·δ(t) + β·T", 9, italic=True)
text(595, 264, "h(d) = 1 / ln(1 + d)", 9, italic=True)
text(595, 304, "keep pairs with W ≥ θe,", 8.5)
text(595, 320, "peel dense cores", 8.5)

# ── (d) Detectors, ensemble and tracker ─────────────────────────────────────
for i, label in enumerate(("hub-aware", "money cycle", "smurfing")):
    rect(736, 90 + i * 34, 130, 28, label, fill="#e3edf9", stroke=PANEL, size=9)
    edge((866, 104 + i * 34), (878, 104 + i * 34), arrow=False, lw=0.8)
rect(
    736, 194, 130, 30, "baselines (timer)", fill="#ffffff", stroke="#9aa0a6", dashed=True, size=8.5
)
edge((878, 104), (878, 248), (810, 248), lw=0.8)
node(801, 248, 9, "#ffffff", "+", stroke=LINE, size=12)
edge((801, 224), (801, 239), dashed=True)
text(846, 262, "ensemble", 8, italic=True)
rect(
    736,
    280,
    130,
    56,
    "ring tracker\nconfirm 2 hits\ndrop 3 misses",
    fill="#ffffff",
    stroke=LINE,
    size=8.5,
)
edge((801, 257), (801, 280))
edge((866, 308), (905, 308), (905, 140), (934, 140), lw=1.2)

# ── (e) Scoring, explanations, outputs ──────────────────────────────────────
text(948, 92, "ring features", 9, italic=True, align="left")
vector(938, 104, [BLUE, BLUE, "#b6d7a8", "#b6d7a8", "#f9cb9c", "#f9cb9c", NEUTRAL, NEUTRAL])
vector(950, 104, ["#c9d9ee", BLUE, "#b6d7a8", "#d9ead3", "#f9cb9c", "#fce5cd", NEUTRAL, "#d0d4d9"])
edge((962, 140), (986, 140))
rect(986, 116, 92, 48, "calibrated\nscorer", fill="#ffffff", stroke=LINE, size=8.5)
edge((1078, 140), (1100, 140))
rect(1100, 108, 16, 64, fill="#ffffff", stroke=LINE, rounded=False, lw=0.6)
rect(1100, 128, 16, 44, fill=FRAUD, stroke="none", rounded=False)
edge((1094, 136), (1124, 136), arrow=False, dashed=True, lw=0.8, stroke="#d1242f")
text(1138, 136, "θa", 9, italic=True)
text(1108, 186, "risk", 8.5)
rect(
    938,
    214,
    226,
    44,
    "explanation: contributions,\nevidence, counterfactual",
    fill="#ffffff",
    stroke=PANEL,
    size=8.5,
)
edge((1032, 164), (1032, 214))
for x, w, label in ((932, 76, "dashboard"), (1014, 66, "audit log"), (1086, 80, "evaluation")):
    rect(x, 292, w, 40, label, fill="#ffffff", stroke=LINE, size=8.5)
    if label != "evaluation":
        edge((x + w / 2, 258), (x + w / 2, 292))
edge((1126, 258), (1126, 292))
# labels reach only the evaluation
edge((166, 270), (212, 270), (212, 372), (1170, 372), (1172, 312), (1166, 312), dashed=True)
text(690, 384, "labels reach only the evaluation", 8.5, italic=True)

# ── Legend ──────────────────────────────────────────────────────────────────
ly = 420
items = [
    (BENIGN, "benign user"),
    (FRAUD, "ring member"),
    (NEUTRAL, "device / card / IP"),
    (HUB, "busy hub"),
]
x = 60
for color, label in items:
    node(x, ly, 7, color, stroke=LINE if color == NEUTRAL else "none")
    text(x + 14, ly, label, 10, align="left")
    x += 176
edge((x, ly), (x + 34, ly))
text(x + 42, ly, "data flow", 10, align="left")
x += 150
edge((x, ly), (x + 34, ly), dashed=True)
text(x + 42, ly, "labels / feedback", 10, align="left")
x += 205
rect(x, ly - 8, 22, 16, fill="none", stroke="#d1242f", dashed=True)
text(x + 30, ly, "dirty region", 10, align="left")


# ── Writers ─────────────────────────────────────────────────────────────────
def _style_font(s: Shape) -> str:
    fs = 1 if s.bold else 0
    fs += 2 if s.italic else 0
    return f"fontFamily={FONT};fontSize={s.size};fontStyle={fs};"


def write_drawio(path: Path, name: str = "architecture") -> None:
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    for i, s in enumerate(S):
        cid = f"s{i}"
        value = html.escape(s.label).replace("\n", "&lt;br&gt;")
        if s.kind in ("rect", "ellipse"):
            style = (
                ("ellipse;" if s.kind == "ellipse" else f"rounded={int(s.rounded)};arcSize=12;")
                + f"whiteSpace=wrap;html=1;fillColor={s.fill};strokeColor={s.stroke};"
                + f"strokeWidth={s.lw};{'dashed=1;' if s.dashed else ''}"
                + _style_font(s)
            )
            cells.append(
                f'<mxCell id="{cid}" value="{value}" style="{style}" vertex="1" parent="1">'
                f'<mxGeometry x="{s.x:.1f}" y="{s.y:.1f}" width="{s.w:.1f}" height="{s.h:.1f}" as="geometry"/></mxCell>'
            )
        elif s.kind == "text":
            align = {"center": "center", "left": "left"}[s.align]
            width = 360
            x0 = s.x - width / 2 if s.align == "center" else s.x
            cells.append(
                f'<mxCell id="{cid}" value="{value}" style="text;html=1;align={align};verticalAlign=middle;'
                f'{_style_font(s)}" vertex="1" parent="1">'
                f'<mxGeometry x="{x0:.1f}" y="{s.y - 9:.1f}" width="{width}" height="18" as="geometry"/></mxCell>'
            )
        else:
            (x0, y0), (x1, y1) = s.points[0], s.points[-1]
            mid = "".join(f'<mxPoint x="{x:.1f}" y="{y:.1f}"/>' for x, y in s.points[1:-1])
            style = (
                f"endArrow={'block;endFill=1' if s.arrow else 'none'};html=1;strokeColor={s.stroke};"
                f"strokeWidth={s.lw};{'dashed=1;' if s.dashed else ''}rounded=0;"
            )
            cells.append(
                f'<mxCell id="{cid}" style="{style}" edge="1" parent="1"><mxGeometry relative="1" as="geometry">'
                f'<mxPoint x="{x0:.1f}" y="{y0:.1f}" as="sourcePoint"/><mxPoint x="{x1:.1f}" y="{y1:.1f}" as="targetPoint"/>'
                + (f'<Array as="points">{mid}</Array>' if mid else "")
                + "</mxGeometry></mxCell>"
            )
    xml = (
        f'<mxfile host="fraudsim"><diagram name="{name}">'
        f'<mxGraphModel dx="{W}" dy="{H}" grid="1" gridSize="10" pageWidth="{W}" pageHeight="{H}" background="#ffffff">'
        "<root>" + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>\n"
    )
    path.write_text(xml, encoding="utf-8")


def render(paths: list[Path]) -> None:
    plt.rcParams["font.family"] = FONT
    plt.rcParams["mathtext.fontset"] = "stix"
    scale = 7.16 / W  # inches per unit at full IEEE text width
    fig, ax = plt.subplots(figsize=(W * scale, H * scale))
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    pt = 0.68  # font points per drawio point at this figure size
    for s in S:
        style = "italic" if s.italic else "normal"
        weight = "bold" if s.bold else "normal"
        if s.kind == "rect":
            fc = "none" if s.fill == "none" else s.fill
            ec = "none" if s.stroke == "none" else s.stroke
            if s.rounded:
                patch = FancyBboxPatch(
                    (s.x, s.y),
                    s.w,
                    s.h,
                    boxstyle="round,pad=0,rounding_size=6",
                    fc=fc,
                    ec=ec,
                    lw=s.lw * 0.7,
                    ls="--" if s.dashed else "-",
                )
            else:
                patch = Rectangle(
                    (s.x, s.y), s.w, s.h, fc=fc, ec=ec, lw=s.lw * 0.7, ls="--" if s.dashed else "-"
                )
            ax.add_patch(patch)
            if s.label:
                ax.text(
                    s.x + s.w / 2,
                    s.y + s.h / 2,
                    s.label,
                    ha="center",
                    va="center",
                    fontsize=s.size * pt,
                    linespacing=1.15,
                    style=style,
                    weight=weight,
                )
        elif s.kind == "ellipse":
            fc = "none" if s.fill == "none" else s.fill
            ec = "none" if s.stroke == "none" else s.stroke
            if abs(s.w - s.h) < 1e-6:
                ax.add_patch(
                    Circle(
                        (s.x + s.w / 2, s.y + s.h / 2),
                        s.w / 2,
                        fc=fc,
                        ec=ec,
                        lw=s.lw * 0.7,
                        ls="--" if s.dashed else "-",
                    )
                )
            if s.label:
                ax.text(
                    s.x + s.w / 2,
                    s.y + s.h / 2,
                    s.label,
                    ha="center",
                    va="center",
                    fontsize=s.size * pt,
                    color="white" if s.fill in (HUB,) else LINE,
                )
        elif s.kind == "text":
            ax.text(
                s.x,
                s.y,
                s.label,
                ha=s.align,
                va="center",
                fontsize=s.size * pt,
                style=style,
                weight=weight,
            )
        else:
            ls = "--" if s.dashed else "-"
            for a, b in pairwise(s.points[:-1]):
                ax.plot([a[0], b[0]], [a[1], b[1]], color=s.stroke, lw=s.lw * 0.7, ls=ls)
            a, b = s.points[-2], s.points[-1]
            ax.add_patch(
                FancyArrowPatch(
                    a,
                    b,
                    arrowstyle="-|>" if s.arrow else "-",
                    mutation_scale=7,
                    lw=s.lw * 0.7,
                    ls=ls,
                    color=s.stroke,
                    shrinkA=0,
                    shrinkB=0,
                )
            )
    for p in paths:
        fig.savefig(p, bbox_inches="tight", dpi=300, pad_inches=0.02)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_drawio(OUT / "architecture.drawio")
    render([OUT / "architecture.pdf", OUT / "architecture.png"])
    print(f"wrote {OUT / 'architecture.drawio'} (+ .pdf, .png)")


if __name__ == "__main__":
    main()
