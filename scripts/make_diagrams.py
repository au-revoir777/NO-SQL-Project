"""
Method diagrams for the paper, drawn with the primitives of make_architecture.py
so all figures share one style and each has an editable draw.io source:

  docs/paper/figures/training_pipeline.{drawio,pdf,png}  how the ring scorer is trained and used
  docs/paper/figures/simulator_design.{drawio,pdf,png}   what the simulator generates and hides

Numbers on the training figure are read from models/ring_scorer_lr.json, so the
figure follows the shipped model.

    python scripts/make_diagrams.py
"""

# ruff: noqa: RUF001  (figure labels use typographic dashes and signs)

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_architecture as A  # noqa: N812  (drawing primitives and writers)
from make_architecture import BENIGN, BLUE, FRAUD, HUB, LINE, NEUTRAL, PANEL

ROOT = Path(__file__).resolve().parents[1]
GREY = "#9aa0a6"
SOFT = "#e3edf9"


def _reset(w: int, h: int) -> None:
    A.S.clear()
    A.W, A.H = w, h


def _save(name: str) -> None:
    A.write_drawio(A.OUT / f"{name}.drawio", name)
    A.render([A.OUT / f"{name}.pdf", A.OUT / f"{name}.png"])
    print(f"wrote {A.OUT / name}.drawio (+ .pdf, .png)")


def _stage_titles(xs: list[float], titles: list[str], y0: float, y1: float, ty: float) -> None:
    for x in xs:
        A.edge((x, y0), (x, y1), dashed=True, arrow=False, stroke=GREY, lw=0.8)
    for x, t in titles:
        A.text(x, ty, t, 9.5, bold=True)


def training_pipeline() -> None:
    meta = json.loads((ROOT / "models" / "ring_scorer_lr.json").read_text(encoding="utf-8"))
    tr, test = meta["train"], meta["metrics"]["test"]
    rows = tr["rows"]
    seeds = tr["train_seeds"]
    tseeds = tr["test_seeds"]
    n_feat = len(meta["feature_names"])
    _reset(1200, 470)

    A.text(600, 16, "Training (offline, labelled seeds only)", 10.5, bold=True)
    _stage_titles(
        [232, 470, 700, 958],
        [
            (116, "(a) Training runs"),
            (351, "(b) Detect, then label"),
            (585, "(c) Ring rows"),
            (829, "(d) Fit and calibrate"),
            (1080, "(e) Held-out test"),
        ],
        44,
        262,
        56,
    )

    # (a) scenarios x seeds
    A.rect(22, 74, 196, 172, "", stroke=PANEL)
    A.text(120, 90, f"{len(tr['scenarios'])} scenarios", 9, italic=True)
    for i, sc in enumerate(tr["scenarios"]):
        A.rect(
            36 + (i % 2) * 88,
            102 + (i // 2) * 30,
            82,
            24,
            sc.replace("_", " "),
            fill=SOFT,
            stroke=PANEL,
            size=8,
        )
    A.text(120, 208, f"× seeds {seeds[0]}–{seeds[-1]}", 9)
    A.text(120, 228, "simulator + detector", 8.5)
    A.edge((218, 160), (256, 160))

    # (b) detector output joined with the hidden ledger
    A.rect(
        256,
        74,
        190,
        76,
        "ring snapshots\n(every confirmed or\nchanged candidate)",
        stroke=LINE,
        size=8.5,
    )
    A.rect(
        256,
        176,
        190,
        56,
        "ground-truth ledger\n(planted rings)",
        fill="#fbe3d6",
        stroke=FRAUD,
        size=8.5,
    )
    A.node(351, 162, 7, "#ffffff", "+", stroke=LINE, size=11)
    A.edge((351, 150), (351, 155))
    A.edge((351, 176), (351, 169), dashed=True)
    A.edge((358, 162), (494, 162))
    A.text(351, 248, "labels: offline only", 8, italic=True)

    # (c) feature rows
    A.text(585, 82, f"{n_feat} ring features", 9, italic=True)
    palette = [BLUE, "#c9d9ee", "#b6d7a8", "#d9ead3", "#f9cb9c", "#fce5cd", NEUTRAL, "#d0d4d9"]
    for r in range(4):
        for c in range(8):
            A.rect(
                510 + c * 14,
                96 + r * 16,
                12,
                12,
                fill=palette[(c + r) % 8],
                stroke=LINE,
                rounded=False,
                lw=0.5,
            )
        A.rect(
            636,
            96 + r * 16,
            14,
            12,
            "1" if r in (0, 2) else "0",
            fill="#ffffff",
            stroke=LINE,
            rounded=False,
            size=7,
        )
    A.text(643, 170, "y", 8.5, italic=True)
    A.text(585, 196, "y = 1 if Jaccard(members,", 8.5)
    A.text(585, 212, "planted ring) ≥ 0.5", 8.5)
    A.text(585, 240, f"{rows['fit'] + rows['calibration']:,} training rows", 8.5)
    A.edge((660, 130), (722, 130))

    # (d) per-run split
    fit = int(tr["fit_fraction"] * 100)
    A.text(829, 82, "each run, in time order", 8.5, italic=True)
    A.rect(722, 96, 150, 26, f"first {fit}%", fill=BLUE, stroke=LINE, rounded=False, lw=0.6, size=8)
    A.rect(
        872, 96, 64, 26, f"{100 - fit}%", fill="#b6d7a8", stroke=LINE, rounded=False, lw=0.6, size=8
    )
    A.edge((797, 122), (797, 146))
    A.edge((904, 122), (904, 146))
    A.rect(722, 146, 140, 54, f"logistic regression\n{rows['fit']:,} rows", stroke=LINE, size=8.5)
    A.rect(870, 146, 76, 54, f"isotonic\n{rows['calibration']:,}", stroke=LINE, size=8.5)
    A.edge((862, 173), (870, 173))
    A.rect(762, 216, 134, 34, "ring_scorer_lr", fill="#fff4e0", stroke="#d29922", size=8.5)
    A.edge((908, 200), (908, 233), (896, 233))
    A.edge((896, 233), (980, 233))

    # (e) held-out test
    A.rect(980, 74, 200, 176, "", stroke=PANEL)
    A.text(1080, 90, f"seeds {tseeds[0]}–{tseeds[-1]}", 9, italic=True)
    A.text(1080, 108, f"{rows['test']:,} rows", 9, italic=True)
    for i, (k, lab) in enumerate(
        (("roc_auc", "ROC AUC"), ("pr_auc", "PR AUC"), ("ece", "ECE"), ("brier", "Brier"))
    ):
        y = 132 + i * 24
        A.text(1000, y, lab, 9, align="left")
        A.text(1145, y, f"{test[k]:.3f}", 9, bold=True)
    A.text(1080, 236, "no evaluation seed is used", 8, italic=True)

    # Use in detection
    A.text(300, 296, "Use in detection (evaluation seeds 1001+)", 10.5, bold=True)
    steps = [
        (22, "micro-batch\nof 50 events"),
        (190, "rings that\nchanged"),
        (358, f"{n_feat} features\nper ring"),
        (526, "ring_scorer_lr\n+ isotonic"),
        (694, "risk ≥ θa\n(θa from seeds 301–303)"),
        (898, "alert: contributions,\nevidence, counterfactual"),
    ]
    for i, (x, lab) in enumerate(steps):
        w = 180 if i == 4 else (190 if i == 5 else 146)
        A.rect(
            x,
            316,
            w,
            56,
            lab,
            fill=SOFT if i in (3, 4) else "#ffffff",
            stroke=PANEL if i in (3, 4) else LINE,
            size=8.5,
        )
        if i < len(steps) - 1:
            nx = steps[i + 1][0]
            A.edge((x + w, 344), (nx, 344))
    A.edge((829, 250), (829, 280), (599, 280), (599, 316), dashed=True)
    A.text(714, 270, "model file", 8, italic=True)
    A.rect(898, 400, 190, 40, "analyst confirm / dismiss", stroke=LINE, size=8.5)
    A.edge((993, 372), (993, 400))
    A.edge((898, 420), (784, 420), (784, 372), dashed=True)
    A.text(640, 420, "shifts θa per ring type (audited)", 8, italic=True)
    _save("training_pipeline")


def simulator_design() -> None:
    _reset(1200, 470)
    _stage_titles(
        [232, 772],
        [
            (116, "(a) Scenario + seed"),
            (502, "(b) Seeded event generator"),
            (986, "(c) Two outputs"),
        ],
        28,
        410,
        40,
    )

    # (a) scenario file
    A.rect(22, 60, 196, 228, "", stroke=PANEL)
    A.text(120, 76, "configs/scenarios/*.yaml", 8.5, italic=True)
    for i, f in enumerate(
        (
            "users, duration, rate",
            "hubs and their sizes",
            "planted rings",
            "random rings",
            "evasion mix",
            "attribute popularity",
        )
    ):
        A.text(40, 102 + i * 24, "• " + f, 8.2, align="left")
    A.rect(60, 248, 120, 28, "seed", fill="#fff4e0", stroke="#d29922", size=9)
    A.edge((218, 174), (256, 174))
    A.text(120, 308, "same file + seed", 8.5)
    A.text(120, 324, "→ same stream", 8.5)

    # (b) generator blocks
    A.rect(256, 60, 492, 290, "", stroke=LINE)
    blocks = [
        (
            268,
            72,
            "Benign population",
            "join and leave; link devices,\ncards, IPs (heavy-tailed\npopularity); transfer money",
            BENIGN,
        ),
        (
            512,
            72,
            "Benign hubs",
            "office, public wifi,\ncarrier NAT, kiosk,\nfamily device, corporate card",
            HUB,
        ),
        (
            268,
            202,
            "Ring planter",
            "shared device / card / IP,\nmixed attribute, money cycle,\nlayered chain, smurfing",
            FRAUD,
        ),
        (
            512,
            202,
            "Evasion layer",
            "hub hiding, low-and-slow,\nidentity rotation,\ndecoy edges, adaptive",
            "#d29922",
        ),
    ]
    for x, y, title, body, colour in blocks:
        A.rect(x, y, 224, 118, "", stroke=colour, lw=1.2)
        A.node(x + 18, y + 18, 7, colour)
        A.text(x + 32, y + 18, title, 9.5, bold=True, align="left")
        A.text(x + 112, y + 70, body, 8)
    A.edge((380, 190), (380, 202))
    A.edge((624, 190), (624, 202))
    A.edge((492, 261), (512, 261))
    A.text(420, 366, "one seeded RNG drives all four blocks", 8.5, italic=True)

    # (c) outputs
    A.rect(810, 60, 360, 130, "", stroke=PANEL)
    A.text(990, 76, "observable event stream", 9.5, bold=True)
    for i, e in enumerate(
        (
            "user_join, user_leave",
            "device_link, card_link, ip_link",
            "attribute_unlink, transaction",
        )
    ):
        A.text(828, 100 + i * 20, "• " + e, 8.5, align="left")
    A.text(990, 172, "SHA-256 digest recorded with every result", 8, italic=True)
    A.rect(810, 222, 360, 104, "", fill="#fbe3d6", stroke=FRAUD)
    A.text(990, 238, "ground-truth ledger (hidden)", 9, bold=True)
    A.text(828, 264, "• ring_spawn, ring_grow, ring_activate,", 8.5, align="left")
    A.text(828, 284, "  ring_mutate, ring_dissolve; members", 8.5, align="left")
    A.text(990, 310, "never published on the bus", 8, italic=True)
    A.edge((748, 125), (810, 125))
    A.edge((748, 274), (810, 274), dashed=True)
    A.rect(1050, 360, 120, 34, "detector", stroke=LINE, size=9)
    A.rect(850, 360, 150, 34, "evaluation / Oracle", stroke=LINE, size=9)
    A.edge((1110, 190), (1110, 360))
    A.edge((925, 326), (925, 360), dashed=True)
    A.edge((1170, 377), (1188, 377), (1188, 440), (624, 440), (624, 320), dashed=True)
    A.text(905, 452, "closed-loop runs: flags go back to the adaptive attacker", 8, italic=True)

    # ring lifecycle strip
    stages = ["spawn", "grow", "activate", "mutate", "dissolve"]
    for i, s in enumerate(stages):
        x = 40 + i * 92
        A.node(
            x,
            418,
            7,
            FRAUD if s != "dissolve" else NEUTRAL,
            stroke=LINE if s == "dissolve" else "none",
        )
        A.text(x, 400, s, 8.5)
        if i < len(stages) - 1:
            A.edge((x + 9, 418), (x + 83, 418), lw=0.8)
    A.text(232, 446, "ring lifecycle (TTD counts from activate)", 8, italic=True)
    _save("simulator_design")


def main() -> None:
    A.OUT.mkdir(parents=True, exist_ok=True)
    training_pipeline()
    simulator_design()


if __name__ == "__main__":
    main()
