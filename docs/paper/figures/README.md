# Figures

Generated, never drawn by hand. Each figure is computed from a committed
results file; rows there carry `run_id`, scenario hash, method hash and
event-stream digest.

| Figure | Source | Command |
|---|---|---|
| `fig1_pr_frontier` | `results/e3_frontier/results.csv` | `make figures` |
| `fig2_latency_scaling` | `results/e4_scale/results.csv` | `make figures` |
| `fig3_ablation` | `results/e2_ablations/results.csv` | `make figures` |
| `fig4_hub_size` | `results/e5_hub_size/results.csv` | `make figures` |
| `fig5_evasion` | `results/e1_baselines/results.csv` | `make figures` |
| `fig6_sweeps` | `results/e6_sweeps/results.csv` | `make figures` |
| `fig7_anchor` | `results/anchor_T1..T3/*/results.csv`, `results/anchor/guard_traces.csv` (cached GNN flag rates; delete to recompute) | `python scripts/make_anchor_figures.py` |
| `fig8_contrasts` | the result files of every contrast it shows (R1, round 3, EvidGNN, AnchorPipe) | `python scripts/make_anchor_figures.py` |
| `architecture` | `architecture.drawio` (edit in draw.io / diagrams.net); includes the GraphSAGE detector and the shift guard | `python scripts/make_architecture.py` |
| `anchor_pipeline` | `results/anchor/` (scorer metadata, guard reference, validation selection) | `python scripts/make_diagrams.py` |
| `training_pipeline` | `models/ring_scorer_lr.json` (seeds, row counts, test metrics) | `python scripts/make_diagrams.py` |
| `simulator_design` | `src/fraudsim/simulator/` and `types.py` (event, ring and evasion types) | `python scripts/make_diagrams.py` |

Both method diagrams also write an editable `.drawio` source next to the PDF.

`make figures` is `python -m fraudsim.experiments.plotting --results-dir results/ --output-dir docs/paper/figures/`.
With the draw.io desktop app, an exact export of the diagram is
`drawio -x -f pdf -o architecture.pdf architecture.drawio`.

Diagrams are rendered in Times New Roman, or a metric-compatible substitute (Liberation Serif) where it is not installed.
The result-figure colours are the validated categorical slots of the reference palette (fixed order: AnchorPipe, GraphSAGE, SagePipe, hybrid, pipeline, rules).
