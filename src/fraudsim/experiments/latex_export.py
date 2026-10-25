"""
LaTeX tables and number macros for the paper, generated only from experiment
results (results/<experiment>/results.csv). Each file records the results it was
built from (path, sha256, row count) so a number in the paper can be traced to
its runs. A table whose results are missing is skipped, never filled in.

    python -m fraudsim.experiments.latex_export --results-dir results --output-dir docs/paper/tables
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import pandas as pd

from fraudsim.experiments.stats import fmt_ci, paired_vs, summarize


def _results(results_dir: Path, experiment: str) -> tuple[pd.DataFrame, str] | None:
    path = Path(results_dir) / experiment / "results.csv"
    if not path.exists():
        print(f"[tables] skip {experiment}: {path} not found")
        return None
    # Line endings are normalised so the digest is the same on Windows (CRLF
    # checkouts) and Linux (LF).
    digest = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]
    df = pd.read_csv(path)
    return df, f"% generated from {path.as_posix()} (sha256 of LF text {digest}, {len(df)} rows)\n"


def _write(output_dir: Path, name: str, body: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / name
    path.write_text(body, encoding="utf-8")
    print(f"[tables] wrote {path}")
    return path


def _esc(s: str) -> str:
    return str(s).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


def _p(p: float) -> str:
    if p is None or math.isnan(p):
        return "--"
    return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def _num(x: float, digits: int = 1) -> str:
    return "--" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{digits}f}"


def _latency(r: pd.Series, family: str | None) -> str:
    """Per-batch latency for incremental methods; one full-graph pass for full-graph baselines."""
    if family in ("baseline", "baseline_scored"):
        return _num(r.get("full_graph_ms_p50_mean")) + r"$^\dagger$"
    return _num(r["detect_ms_p50_mean"])


def generate_baseline_table(output_dir: Path, results_dir: Path = Path("results")) -> Path | None:
    """Table 1: every E1 method, plus the E1b scored baselines when their results exist."""
    got = _results(results_dir, "e1_baselines")
    if got is None:
        return None
    df, header = got
    scored = _results(results_dir, "e1b_scored_baselines")
    if scored is not None:
        sdf, sheader = scored
        # Main table: scored baselines at their validation-selected thresholds only.
        sdf = sdf[~sdf["method"].str.endswith("_apriori")]
        df = pd.concat([df, sdf], ignore_index=True)
        header += sheader
    labels = df.drop_duplicates("method").set_index("method")["method_label"].to_dict()
    for m in list(labels):
        if m.endswith("_scored") and m[: -len("_scored")] in labels:
            labels[m] = labels[m[: -len("_scored")]] + " + scorer"
    families = df.drop_duplicates("method").set_index("method")["family"].to_dict()
    s = summarize(df, ["method"]).set_index("method")
    if "proposed" in set(df["method"]):
        from fraudsim.experiments.scored_baselines import holm

        tests = paired_vs(df, "proposed", "f1").set_index("method")
        adj = holm({m: float(tests.loc[m, "wilcoxon_p"]) for m in tests.index})
    else:
        adj = {}
    best = s["f1_mean"].max()

    def line(method: str) -> str:
        r = s.loc[method]
        f1 = fmt_ci(r["f1_mean"], r["f1_ci95"])
        if r["f1_mean"] == best:
            f1 = r"\textbf{" + f1 + "}"
        return (
            f"{_esc(labels.get(method, method))} & {fmt_ci(r['precision_mean'], r['precision_ci95'])}"
            f" & {fmt_ci(r['recall_mean'], r['recall_ci95'])} & {f1}"
            f" & {_num(r['ttd_p50_s_mean'])} & {_latency(r, families.get(method))}"
            f" & {_p(adj[method]) if method in adj else '--'} \\\\"
        )

    unscored = [m for m in s.index if families.get(m) == "baseline"]
    scored_rows = [f"{m}_scored" for m in unscored if f"{m}_scored" in s.index]
    proposed = [m for m in ("proposed", "proposed_default") if m in s.index]
    if scored_rows:
        lines = [r"\multicolumn{7}{l}{\textit{Without a scorer}} \\"]
        lines += [line(m) for m in unscored]
        lines += [r"\midrule", r"\multicolumn{7}{l}{\textit{With the calibrated scorer}} \\"]
        lines += [line(m) for m in scored_rows + proposed]
        scorer_note = (
            " Scored baselines use the shipped scorer (\\texttt{models/ring\\_scorer\\_lr.json}),"
            " with the alert threshold selected per method on the validation seeds; the proposed"
            " method includes the same scorer, so only rows within a group isolate the candidate"
            " generator. $p$ values are Holm-corrected."
        )
    else:
        lines = [line(m) for m in unscored + proposed]
        scorer_note = ""
    n_scen, n_seed = df["scenario"].nunique(), df["seed"].nunique()
    body = (
        header
        + rf"""\begin{{table*}}[t]
\centering
\caption{{Ring-level detection on {n_scen} scenarios $\times$ {n_seed} test seeds, pooled (mean $\pm$ 95\% CI over runs;
a run with no flags has undefined precision and counts as F1 $=0$). TTD: median time from ring activation to
first flag. Latency: median per-batch detection time on the in-memory store; $^\dagger$full-graph
methods run on a 5\,s timer, not per batch, so their entry is the median time of one full-graph pass. $p$: paired Wilcoxon signed-rank
test of F1 against the proposed method on identical streams.{scorer_note}}}
\label{{tab:baselines}}
\begin{{tabular}}{{lcccccc}}
\toprule
Method & Precision & Recall & F1 & TTD (s) & Latency (ms) & $p$ \\
\midrule
{chr(10).join(lines)}
\bottomrule
\end{{tabular}}
\end{{table*}}
"""
    )
    return _write(output_dir, "tab1_baselines.tex", body)


def generate_scenario_table(output_dir: Path, results_dir: Path = Path("results")) -> Path | None:
    """Table 1b: F1 per scenario and method."""
    got = _results(results_dir, "e1_baselines")
    if got is None:
        return None
    df, header = got
    labels = df.drop_duplicates("method").set_index("method")["method_label"]
    s = summarize(df, ["method", "scenario"], ("f1",))
    scenarios = list(dict.fromkeys(df["scenario"]))
    lines = []
    for method in dict.fromkeys(df["method"]):
        cells = []
        for sc in scenarios:
            row = s[(s["method"] == method) & (s["scenario"] == sc)]
            cells.append(
                fmt_ci(row["f1_mean"].iloc[0], row["f1_ci95"].iloc[0]) if len(row) else "--"
            )
        lines.append(f"{_esc(labels.get(method, method))} & " + " & ".join(cells) + r" \\")
    body = (
        header
        + rf"""\begin{{table*}}[t]
\centering
\caption{{Ring F1 per scenario (mean $\pm$ 95\% CI over {df["seed"].nunique()} test seeds).}}
\label{{tab:scenarios}}
\begin{{tabular}}{{l{"c" * len(scenarios)}}}
\toprule
Method & {" & ".join(_esc(s) for s in scenarios)} \\
\midrule
{chr(10).join(lines)}
\bottomrule
\end{{tabular}}
\end{{table*}}
"""
    )
    return _write(output_dir, "tab1b_scenarios.tex", body)


def generate_ablation_table(output_dir: Path, results_dir: Path = Path("results")) -> Path | None:
    """Table 2: ablations with the paired difference to the full system."""
    got = _results(results_dir, "e2_ablations")
    if got is None:
        return None
    df, header = got
    labels = df.drop_duplicates("method").set_index("method")["method_label"]
    s = summarize(df, ["method"])
    tests = paired_vs(df, "proposed", "f1").set_index("method")
    from fraudsim.experiments.scored_baselines import holm

    adj = holm(
        {
            m: float(tests.loc[m, "wilcoxon_p"])
            for m in tests.index
            if pd.notna(tests.loc[m, "wilcoxon_p"])
        }
    )
    lines = []
    for _, r in s.iterrows():
        m = r["method"]
        if m in tests.index:
            t = tests.loc[m]
            d = -t["mean_diff"]
            delta = "0.00" if abs(d) < 0.005 else f"{d:+.2f}"
            dz = _num(t["cohens_dz"], 2)
            p = _p(t["wilcoxon_p"])
            ph = _p(adj[m]) if m in adj else "--"
        else:
            delta = dz = p = ph = "--"
        lines.append(
            f"{_esc(labels.get(m, m))} & {fmt_ci(r['precision_mean'], r['precision_ci95'])}"
            f" & {fmt_ci(r['recall_mean'], r['recall_ci95'])} & {fmt_ci(r['f1_mean'], r['f1_ci95'])}"
            f" & {delta} & {dz} & {p} & {ph} & {_num(r['detect_ms_p50_mean'])} \\\\"
        )
    body = (
        header
        + rf"""\begin{{table*}}[t]
\centering
\caption{{Ablations on {", ".join(_esc(x) for x in dict.fromkeys(df["scenario"]))}
($\times$ {df["seed"].nunique()} test seeds). $\Delta$F1: paired mean difference to the full system;
$d_z$: paired effect size of the full system over the variant; $p$: Wilcoxon signed-rank,
uncorrected and Holm-corrected over the {len(adj)} tested comparisons.}}
\label{{tab:ablation}}
\begin{{tabular}}{{lcccccccc}}
\toprule
Variant & Precision & Recall & F1 & $\Delta$F1 & $d_z$ & $p$ & $p_{{\mathrm{{Holm}}}}$ & Latency (ms) \\
\midrule
{chr(10).join(lines)}
\bottomrule
\end{{tabular}}
\end{{table*}}
"""
    )
    return _write(output_dir, "tab2_ablation.tex", body)


def generate_scale_table(output_dir: Path, results_dir: Path = Path("results")) -> Path | None:
    """Table 3: incremental vs full recomputation as the graph grows."""
    got = _results(results_dir, "e4_scale")
    if got is None:
        return None
    df, header = got
    lines = []
    for users, g in df.groupby("users"):
        inc = summarize(g[g["mode"] == "incremental"], ["mode"], ("detect_ms_p50", "region_p50"))
        full = summarize(g[g["mode"] == "full"], ["mode"], ("detect_ms_p50", "region_p50"))
        if inc.empty or full.empty:
            continue
        i, f = inc.iloc[0], full.iloc[0]
        speed = (
            f["detect_ms_p50_mean"] / i["detect_ms_p50_mean"]
            if i["detect_ms_p50_mean"]
            else math.nan
        )
        lines.append(
            f"{int(users):,} & {_num(i['region_p50_mean'], 0)} & {fmt_ci(i['detect_ms_p50_mean'], i['detect_ms_p50_ci95'], 1)}"
            f" & {_num(f['region_p50_mean'], 0)} & {fmt_ci(f['detect_ms_p50_mean'], f['detect_ms_p50_ci95'], 1)}"
            f" & {_num(speed, 1)}$\\times$ \\\\"
        )
    body = (
        header
        + rf"""\begin{{table*}}[t]
\centering
\caption{{Per-batch detection latency (median, ms; mean $\pm$ 95\% CI over {df["seed"].nunique()} seeds)
and users examined per batch, incremental vs full recomputation, in-memory store.}}
\label{{tab:scale}}
\begin{{tabular}}{{rccccc}}
\toprule
& \multicolumn{{2}}{{c}}{{Incremental}} & \multicolumn{{2}}{{c}}{{Full}} & \\
Users & Region & ms & Region & ms & Speed-up \\
\midrule
{chr(10).join(lines)}
\bottomrule
\end{{tabular}}
\end{{table*}}
"""
    )
    return _write(output_dir, "tab3_scale.tex", body)


def _slice(value: object) -> str:
    """'2022-09-01T00:00:00 .. 2022-09-05T00:00:00' -> '2022-09-01 to 09-05 (excl.)'; missing -> 'all'."""
    if not isinstance(value, str) or value in ("", "all"):
        return "all"
    lo, _, hi = value.partition(" .. ")
    return f"{lo[:10]} to {hi[5:10]} (excl.)" if hi and hi != "end" else f"from {lo[:10]}"


def generate_public_table(output_dir: Path, results_dir: Path = Path("results")) -> Path | None:
    """Table 4: public datasets (latest run per dataset), with attempt recall by typology."""
    got = _results(results_dir, "public")
    if got is None:
        return None
    df, header = got
    lines = []
    for _, r in df.groupby("dataset", sort=False).tail(1).iterrows():
        by_type = (
            json.loads(r["group_recall_by_type"])
            if isinstance(r.get("group_recall_by_type"), str)
            else {}
        )
        types = ", ".join(f"{_esc(k)} {v:.2f}" for k, v in by_type.items()) or "--"
        gr = r.get("group_recall")
        lines.append(
            f"{_esc(r['dataset'])} & {_slice(r.get('slice'))} & {int(r['rows']):,} & {int(r['groups'])}"
            f" & {_num(r.get('account_precision'), 2)} & {_num(r.get('account_recall'), 2)}"
            f" & {_num(gr, 2) if gr == gr else '--'} \\\\"
            + (
                f"\n\\multicolumn{{7}}{{l}}{{\\quad attempt recall by typology: {types}}} \\\\"
                if by_type
                else ""
            )
        )
    body = (
        header
        + rf"""\begin{{table*}}[t]
\centering
\caption{{Public data, transaction detectors only (no device/card/IP links exist). Account precision/recall:
accounts in confirmed groups vs.\ accounts in laundering transactions. Attempt recall: share of laundering
attempts that lie entirely in the slice and are at least half covered by one flagged group.}}
\label{{tab:public}}
\begin{{tabular}}{{lllrrrr}}
\toprule
Dataset & Slice & Rows & Attempts & Acc.\ precision & Acc.\ recall & Attempt recall \\
\midrule
{chr(10).join(lines)}
\bottomrule
\end{{tabular}}
\end{{table*}}
"""
    )
    return _write(output_dir, "tab4_public.tex", body)


def _public_numbers(results_dir: Path) -> list[str]:
    got = _results(results_dir, "public")
    if not got:
        return []
    df, header = got
    out = [header]
    for _, r in df.groupby("dataset", sort=False).tail(1).iterrows():
        tag = {
            "amlworld": "Aml",
            "elliptic": "Ell",
            "paysim": "Pay",
            "amlsim_20K_cycle200": "SimCycle",
            "amlsim_20K_fanin200": "SimFanin",
            "amlsim_20K_fanin200cycle200": "SimBoth",
        }.get(r["dataset"])
        if tag is None:
            continue
        out.append(_macro(f"Pub{tag}Rows", f"{int(r['rows']):,}"))
        out.append(_macro(f"Pub{tag}Events", f"{int(r['events']):,}"))
        out.append(_macro(f"Pub{tag}Accounts", f"{int(r['accounts']):,}"))
        out.append(_macro(f"Pub{tag}Groups", str(int(r["groups"]))))
        out.append(_macro(f"Pub{tag}Illicit", f"{int(r['illicit_accounts']):,}"))
        out.append(_macro(f"Pub{tag}Flagged", f"{int(r['accounts_flagged']):,}"))
        out.append(_macro(f"Pub{tag}GroupsFlagged", str(int(r["groups_flagged"]))))
        out.append(_macro(f"Pub{tag}Window", f"{float(r['window_s']) / 3600:g}"))
        out.append(_macro(f"Pub{tag}Wall", f"{float(r['wall_s']) / 60:.0f}"))
        for col, mt in (
            ("account_precision", "AccP"),
            ("account_recall", "AccR"),
            ("group_recall", "GroupR"),
        ):
            v = r.get(col)
            out.append(_macro(f"Pub{tag}{mt}", "--" if v is None or v != v else f"{float(v):.2f}"))
    return out


def _macro(name: str, value: str) -> str:
    return f"\\newcommand{{\\{name}}}{{{value}}}\n"


def _evasion_numbers(df: pd.DataFrame, names: dict[str, str]) -> list[str]:
    """Detected/total rings per evasion strategy, e.g. \\EvPropHubHiding = 35/52."""
    out = []
    for m, tag in names.items():
        acc: dict[str, list[int]] = {}
        for cell in df[df["method"] == m]["detected_by_evasion"].dropna():
            for mode, (hit, tot) in json.loads(cell).items():
                a = acc.setdefault(mode, [0, 0])
                a[0] += hit
                a[1] += tot
        for mode, (hit, tot) in sorted(acc.items()):
            mt = "".join(w.title() for w in mode.split("_"))
            out.append(_macro(f"Ev{tag}{mt}", f"{hit}/{tot}"))
    return out


ABLATION_TAGS = {
    "proposed": "Full",
    "no_hub_weight": "NoHubWeight",
    "no_time_decay": "NoTimeDecay",
    "no_incremental": "NoIncremental",
    "no_scoring": "NoScoring",
    "no_hysteresis": "NoHysteresis",
    "no_hub_aware": "NoHubAware",
    "no_cycle": "NoCycle",
    "no_smurfing": "NoSmurfing",
}


def _ablation_numbers(results_dir: Path, f2) -> list[str]:  # type: ignore[no-untyped-def]
    got = _results(results_dir, "e2_ablations")
    if not got:
        return []
    df, header = got
    out = [header]
    s = summarize(df, ["method"]).set_index("method")
    tests = paired_vs(df, "proposed", "f1").set_index("method")
    per = summarize(df, ["method", "scenario"], ("f1",))
    for m, tag in ABLATION_TAGS.items():
        if m not in s.index:
            continue
        out.append(_macro(f"Abl{tag}F", f2(s.loc[m, "f1_mean"])))
        out.append(_macro(f"Abl{tag}P", f2(s.loc[m, "precision_mean"])))
        out.append(_macro(f"Abl{tag}R", f2(s.loc[m, "recall_mean"])))
        if m in tests.index:
            out.append(_macro(f"Abl{tag}Pval", _p(tests.loc[m, "wilcoxon_p"])))
        for sc in ("hub_heavy", "high_noise", "adversarial", "baseline"):
            row = per[(per["method"] == m) & (per["scenario"] == sc)]
            if len(row):
                sc_tag = "".join(w.title() for w in sc.split("_"))
                out.append(_macro(f"Abl{tag}F{sc_tag}", f2(row["f1_mean"].iloc[0])))
    out.append(_macro("AblSeeds", str(df["seed"].nunique())))
    out.append(_macro("AblPairs", str(df.groupby(["scenario", "seed"]).ngroups)))
    return out


def _frontier_numbers(results_dir: Path, f2) -> list[str]:  # type: ignore[no-untyped-def]
    from fraudsim.experiments.plotting import pooled_pr

    got = _results(results_dir, "e3_frontier")
    if not got:
        return []
    df, header = got
    out = [header]
    tags = {"cap": "Cap", "hub": "Hub", "cap_scored": "CapS", "hub_scored": "HubS"}
    for fam, tag in tags.items():
        pts = []
        for method, g in df[df["family"] == fam].groupby("method", sort=False):
            pr, rc = pooled_pr(g)
            if pr is not None and rc is not None:
                f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0.0
                pts.append((rc, pr, f1, method.split("_", 1)[1]))
        if not pts:
            continue
        top_r = max(pts, key=lambda x: (x[0], x[1]))
        best = max(pts, key=lambda x: x[2])
        out.append(_macro(f"Fr{tag}MaxR", f2(top_r[0])))
        out.append(_macro(f"Fr{tag}PAtMaxR", f2(top_r[1])))
        out.append(_macro(f"Fr{tag}BestF", f2(best[2])))
        out.append(_macro(f"Fr{tag}BestFP", f2(best[1])))
        out.append(_macro(f"Fr{tag}BestFR", f2(best[0])))
        out.append(_macro(f"Fr{tag}BestFAt", best[3]))
    out.append(
        _macro(
            "FrTrueRings",
            str(int(df.groupby("run_id")["true_rings"].first().sum() / df["method"].nunique())),
        )
    )
    return out


def _hub_size_numbers(results_dir: Path, f2) -> list[str]:  # type: ignore[no-untyped-def]
    got = _results(results_dir, "e5_hub_size")
    if not got:
        return []
    df, header = got
    out = [
        header,
        _macro("HubSizeMin", str(int(df["hub_size"].min()))),
        _macro("HubSizeMax", str(int(df["hub_size"].max()))),
    ]
    for m, tag in (
        ("proposed", "Prop"),
        ("static_cap10", "CapTen"),
        ("static_cap100", "CapHundred"),
        ("static_cap10_nocycle", "CapTenNoCycle"),
    ):
        g = df[df["method"] == m]
        if g.empty:
            continue
        hit = tot = 0
        for cell in g["detected_by_evasion"].dropna():
            d = json.loads(cell).get("hub_hiding")
            if d:
                hit, tot = hit + d[0], tot + d[1]
        out.append(_macro(f"HubSize{tag}Hidden", f"{hit}/{tot}"))
        out.append(_macro(f"HubSize{tag}F", f2(g["f1"].fillna(0).mean())))
    return out


def _sweep_numbers(results_dir: Path, f2) -> list[str]:  # type: ignore[no-untyped-def]
    got = _results(results_dir, "e6_sweeps")
    if not got:
        return []
    df, header = got
    df = df.assign(f1=df["f1"].fillna(0))
    out = [header]
    prop = df[df["method"].str.startswith("proposed")]
    for sweep, tag in (("event_rate", "Rate"), ("ring_size", "RingSize"), ("window_s", "Window")):
        g = prop[prop["sweep"] == sweep]
        if g.empty:
            continue
        lo, hi = g["value"].min(), g["value"].max()
        out.append(_macro(f"Sw{tag}Lo", f"{lo:g}"))
        out.append(_macro(f"Sw{tag}Hi", f"{hi:g}"))
        for v, vt in ((lo, "Lo"), (hi, "Hi")):
            gg = g[g["value"] == v]
            out.append(_macro(f"Sw{tag}{vt}F", f2(gg["f1"].mean())))
            out.append(_macro(f"Sw{tag}{vt}Lat", _num(gg["detect_ms_p50"].mean())))
    return out


def _adaptivity_numbers(results_dir: Path) -> list[str]:
    got = _results(results_dir, "e7_adaptivity")
    if not got:
        return []
    df, header = got
    out = [header, _macro("AdaptSeeds", str(df["seed"].nunique()))]
    for fb, tag in ((False, "Off"), (True, "On")):
        g = df[df["feedback"] == fb]
        out.append(_macro(f"Adapt{tag}Rings", str(int(g["adaptive_rings"].sum()))))
        out.append(_macro(f"Adapt{tag}Found", str(int(g["adaptive_detected"].sum()))))
        out.append(_macro(f"Adapt{tag}Switches", str(int(g["strategy_switches"].sum()))))
        out.append(_macro(f"Adapt{tag}R", f"{g['recall'].mean():.2f}"))
    return out


def _e4b_numbers(results_dir: Path, f2) -> list[str]:  # type: ignore[no-untyped-def]
    """Macros for E4b (timer-based full recomputation; scale with growing hubs)."""
    out: list[str] = []
    got = _results(results_dir, "e4b_timer")
    if got:
        df, header = got
        out.append(header)
        df["f1"] = df["f1"].fillna(0)
        df["cost"] = df["detect_ms_sum"] / df["sim_s"]
        s = summarize(df, ["method"]).set_index("method")
        t = paired_vs(df, "inc", "f1").set_index("method")
        tags = {"inc": "Inc", "timer_1": "One", "timer_5": "Five", "timer_30": "Thirty"}
        for m, tag in tags.items():
            g = df[df["method"] == m]
            if g.empty:
                continue
            out.append(_macro(f"Tm{tag}F", f2(s.loc[m, "f1_mean"])))
            out.append(_macro(f"Tm{tag}TTD", _num(g["ttd_p50_s"].median())))
            out.append(_macro(f"Tm{tag}Cost", f"{g['cost'].mean():,.0f}"))
            out.append(_macro(f"Tm{tag}Pass", _num(g["detect_ms_p50"].mean())))
            if m in t.index:
                out.append(_macro(f"Tm{tag}Pval", _p(float(t.loc[m, "wilcoxon_p"]))))
        out.append(_macro("TmRuns", str(df[df["method"] == "inc"].shape[0])))
    got = _results(results_dir, "e4b_scale_hubs")
    if got:
        df, header = got
        out.append(header)
        sizes = {1000: "A", 5000: "B", 20000: "C"}
        modes = {"incremental": "Inc", "full": "Full", "timer_5": "Timer"}
        for n, st in sizes.items():
            for mode, mt in modes.items():
                g = df[(df["users"] == n) & (df["mode"] == mode)]
                if g.empty:
                    continue
                out.append(_macro(f"Gh{mt}Ms{st}", _num(g["detect_ms_p50"].mean())))
                out.append(_macro(f"Gh{mt}Region{st}", f"{g['region_p50'].median():,.0f}"))
                out.append(_macro(f"Gh{mt}Cost{st}", f"{g['ms_per_sim_s'].mean():,.0f}"))
        out.append(_macro("GhSeeds", str(df["seed"].nunique())))
    return out


def _e6b_numbers(results_dir: Path, f2) -> list[str]:  # type: ignore[no-untyped-def]
    """Macros for E6b (leave-one-scenario-out scorer, ring-level scorer metrics)."""
    got = _results(results_dir, "e6b_generalisation")
    if not got:
        return []
    df, header = got
    out = [header]
    a = df[df["fold"] == "all"].iloc[0]
    out += [
        _macro("GenSnapAUC", f"{a['snap_roc_auc']:.3f}"),
        _macro("GenSnapPR", f"{a['snap_pr_auc']:.3f}"),
        _macro("GenRingAUC", f"{a['ring_roc_auc']:.3f}"),
        _macro("GenRingPR", f"{a['ring_pr_auc']:.3f}"),
        _macro("GenRingUnits", f"{int(a['ring_n']):,}"),
        _macro("GenSnapUnits", f"{int(a['snap_n']):,}"),
    ]
    ref = df[(df["fold"] != "all") & (df["model"] == "all_scenarios")].set_index("fold")
    loo = df[(df["fold"] != "all") & (df["model"] == "leave_one_out")].set_index("fold")
    for col, tag in (("snap_roc_auc", "SnapAUC"), ("ring_pr_auc", "RingPR")):
        drop = (ref[col] - loo[col]).dropna()
        out.append(_macro(f"GenDrop{tag}", f"{drop.max():.2f}"))
        out.append(_macro(f"GenDrop{tag}Where", _esc(str(drop.idxmax()))))
    return out


def _e5b_numbers(results_dir: Path, f2) -> list[str]:  # type: ignore[no-untyped-def]
    """Macros for E5b (fan-out limit at large hubs). Size tags: A = 500, B = 2,000, C = 10,000."""
    got = _results(results_dir, "e5b_large_hubs")
    if not got:
        return []
    df, header = got
    out = [header]
    df["f1"] = df["f1"].fillna(0)
    sizes = {500: "A", 2000: "B", 10000: "C"}
    tags = {
        "log_fanout": "LogFan",
        "log_bound": "LogBound",
        "log_full": "LogFull",
        "const_fanout": "ConstFan",
        "const_full": "ConstFull",
        "static_cap10": "CapTen",
    }

    def hh(g: pd.DataFrame) -> str:
        det = tot = 0
        for v in g["detected_by_evasion"].dropna():
            x = json.loads(v).get("hub_hiding")
            if x:
                det, tot = det + x[0], tot + x[1]
        return f"{det}/{tot}"

    for size, st in sizes.items():
        for m, tag in tags.items():
            g = df[(df["hub_size"] == size) & (df["method"] == m)]
            if g.empty:
                continue
            out.append(_macro(f"Lh{tag}F{st}", f2(g["f1"].mean())))
            out.append(_macro(f"Lh{tag}HH{st}", hh(g)))
            out.append(_macro(f"Lh{tag}N{st}", str(len(g))))
            out.append(_macro(f"Lh{tag}Wall{st}", f"{g['wall_s'].mean() / 60:.0f}"))
    cols = ["precision", "recall", "f1", "rings_flagged", "region_p50", "region_max"]
    same = total = 0
    for size in sizes:
        a = df[(df["hub_size"] == size) & (df["method"] == "log_fanout")].set_index("seed")
        b = df[(df["hub_size"] == size) & (df["method"] == "log_bound")].set_index("seed")
        for s in sorted(set(a.index) & set(b.index)):
            total += 1
            same += all(
                (pd.isna(a.loc[s, c]) and pd.isna(b.loc[s, c])) or a.loc[s, c] == b.loc[s, c]
                for c in cols
            )
    out.append(_macro("LhBoundSame", f"{same}/{total}"))
    inc = df[(df["hub_size"] >= 2000) & (df["method"] == "log_fanout")]["region_p50"]
    full = df[df["method"] == "log_full"]["region_max"]
    out.append(_macro("LhRegionInc", f"{inc.median():.0f}"))
    out.append(_macro("LhRegionFullMax", f"{full.max():,.0f}"))
    return out


def _e2b_numbers(results_dir: Path, f2) -> list[str]:  # type: ignore[no-untyped-def]
    """Macros for E2b (hub_heavy, 30 seeds) and E2c (weight functions, 5 scenarios)."""
    from fraudsim.experiments.weight_functions import _hub_hiding_recall

    out: list[str] = []
    tags = {
        "inverse_log_degree": "Ship",
        "inverse_degree_plain": "Inv",
        "inverse_sqrt_degree": "Sqrt",
        "soft_cap": "Soft",
        "none": "Const",
    }
    sel_path = Path(results_dir) / "e2b_hub_heavy" / "selected_edge_thresholds.json"
    for exp, prefix in (("e2b_hub_heavy", "Wb"), ("e2c_weight_functions", "Wc")):
        got = _results(results_dir, exp)
        if not got:
            continue
        df, header = got
        out.append(header)
        s = summarize(df, ["method"]).set_index("method")
        t = paired_vs(df, "w_inverse_log_degree", "f1").set_index("method")
        for fn, tag in tags.items():
            m = f"w_{fn}"
            if m not in s.index:
                continue
            for metric, mt in (("precision", "P"), ("recall", "R"), ("f1", "F")):
                out.append(_macro(f"{prefix}{tag}{mt}", f2(s.loc[m, f"{metric}_mean"])))
            hh = _hub_hiding_recall(df[df["method"] == m])
            out.append(_macro(f"{prefix}{tag}HH", f2(hh) if hh is not None else "--"))
            if m in t.index:
                out.append(_macro(f"{prefix}{tag}Pval", _p(float(t.loc[m, "wilcoxon_p"]))))
        out.append(_macro(f"{prefix}Seeds", str(df["seed"].nunique())))
    if sel_path.exists():
        sel = json.loads(sel_path.read_text(encoding="utf-8"))["edge_threshold"]
        for fn, tag in tags.items():
            out.append(_macro(f"W{tag}Edge", f"{float(sel[fn]):g}"))
    return out


def _e1b_numbers(results_dir: Path, f2) -> list[str]:  # type: ignore[no-untyped-def]
    """Macros for E1b (scored baselines) and E3b (frontier intervals)."""
    out: list[str] = []
    got = _results(results_dir, "e1b_scored_baselines")
    if got:
        df, header = got
        out.append(header)
        s = summarize(df, ["method"]).set_index("method")
        sel = Path(results_dir) / "e1b_scored_baselines" / "selected_thresholds.json"
        chosen = json.loads(sel.read_text(encoding="utf-8"))["alert_threshold"]
        alerts = {f"{k}_scored": v for k, v in chosen.items()}
        for m, tag in (
            ("static_cap10_scored", "CapTenS"),
            ("static_cap100_scored", "CapHundredS"),
            ("louvain_scored", "LouvainS"),
        ):
            if m in s.index:
                for metric, mt in (("precision", "P"), ("recall", "R"), ("f1", "F")):
                    out.append(_macro(f"E{tag}{mt}", f2(s.loc[m, f"{metric}_mean"])))
                out.append(_macro(f"E{tag}FCI", f2(s.loc[m, "f1_ci95"])))
                out.append(_macro(f"E{tag}At", f"{float(alerts[m]):g}"))
    ci = Path(results_dir) / "e3b_frontier_ci" / "frontier_ci.json"
    if ci.exists():
        b = json.loads(ci.read_text(encoding="utf-8"))["best_f1"]
        out.append(f"% from {ci.as_posix()}\n")
        out.append(_macro("FrDiff", f"{b['difference']:.2f}"))
        out.append(_macro("FrDiffLo", f"{b['difference_ci'][0]:.2f}"))
        out.append(_macro("FrDiffHi", f"{b['difference_ci'][1]:.2f}"))
        out.append(_macro("FrHubBetterPct", f"{100 * b['share_of_resamples_hub_better']:.0f}"))
    return out


def _phase2_numbers(results_dir: Path) -> list[str]:
    """Macros for the Phase 2 experiments (E8, E10-E14), computed from their CSVs."""
    out: list[str] = []
    r = Path(results_dir)

    def m(name: str, value: str) -> None:
        out.append(_macro(name, value))

    def pct(x: float) -> str:
        return f"{100 * x:.0f}"

    e8 = r / "e8_stack_latency" / "results.csv"
    if e8.exists():
        df = pd.read_csv(e8)
        out.append(f"% from {e8.as_posix()}\n")
        m("EightRuns", str(len(df)))
        m("EightSame", str(int((df["same_updates"] & df["same_flagged"]).sum())))
        paced = df[df["phase"] == "e1_paced"].groupby("scenario").median(numeric_only=True)
        m("EightFlagLo", f"{paced['event_to_flag_ms_p50'].min():.0f}")
        m("EightFlagHi", f"{paced['event_to_flag_ms_p50'].max():.0f}")
        meas = df[df["phase"].isin(["e1_paced", "users_unpaced"])]
        g = meas.groupby(["phase", "scenario", "users"], dropna=False).median(numeric_only=True)
        ratio = g["detect_ms_p50"] / g["memory_detect_ms_p50"]
        m("EightSlowLo", f"{ratio.min():.0f}")
        m("EightSlowHi", f"{ratio.max():.0f}")
        users = df[df["phase"] == "users_unpaced"].groupby("users").median(numeric_only=True)
        m("EightTputLo", f"{users['events_per_s'].min():.0f}")
        m("EightTputHi", f"{users['events_per_s'].max():.0f}")
        m("EightBurstLo", f"{users['event_to_flag_ms_p50'].min() / 1000:.0f}")
        m("EightBurstHi", f"{users['event_to_flag_ms_p50'].max() / 1000:.0f}")

    e10 = r / "e10_ring_alerts"
    if (e10 / "summary.csv").exists():
        sm = pd.read_csv(e10 / "summary.csv").set_index("scope").loc["all"]
        cal = pd.read_csv(e10 / "calibrators.csv")
        cal = cal[cal["scope"] == "all"].set_index("calibrator")
        rel = pd.read_csv(e10 / "reliability.csv")
        rel = rel[(rel["calibrator"] == "shipped") & (rel["binning"] == "width")].set_index("bin")
        out.append(f"% from {(e10 / 'summary.csv').as_posix()}, calibrators.csv, reliability.csv\n")
        m("TenUnits", str(int(sm["units"])))
        m("TenAlerts", str(int(sm["alerts"])))
        m("TenEce", f"{sm['ece_width']:.2f}")
        m("TenBrier", f"{cal.loc['shipped', 'brier']:.3f}")
        best = cal.drop(index=["shipped", "uncalibrated"], errors="ignore")["brier"].min()
        m("TenBrierRefit", f"{best:.3f}")
        m("TenPAtFive", f"{sm['precision_at_5pct']:.2f}")
        m("TenBinEight", pct(rel.loc[8, "positive_rate"]) if 8 in rel.index else "--")
        m("TenBinNine", pct(rel.loc[9, "positive_rate"]) if 9 in rel.index else "--")

    e11 = r / "e11_early_warning" / "summary.csv"
    if e11.exists():
        sm = pd.read_csv(e11).set_index("scope").loc["all"]
        out.append(f"% from {e11.as_posix()}\n")
        m("ElevenEligible", str(int(sm["eligible_rings"])))
        m("ElevenWarned", str(int(sm["warned_before_activation"])))
        m("ElevenShare", pct(sm["share_warned"]))
        m("ElevenLead", f"{sm['lead_median_s']:.1f}")
        m("ElevenPrecision", pct(sm["warning_precision"]))

    e12 = r / "e12_explanations"
    if (e12 / "counterfactuals.csv").exists():
        units = pd.read_csv(e12 / "units.csv")
        cf = pd.read_csv(e12 / "counterfactuals.csv")
        st = pd.read_csv(e12 / "stability.csv")
        co = pd.read_csv(e12 / "consistency.csv")
        alerts = units[units["shipped"] >= 0.8]
        ship, corr = cf[cf["mode"] == "as_shipped"], cf[cf["mode"] == "corrected"]
        with_cf = corr.drop_duplicates(["scenario", "seed", "ring_id"]).shape[0]
        out.append(f"% from {e12.as_posix()}/*.csv\n")
        m("TwelveAlerts", str(len(alerts)))
        m("TwelveCfs", str(len(corr)))
        m("TwelveValidAsShipped", str(int(ship["valid"].sum())))
        m("TwelveValidCorrected", str(int(corr["valid"].sum())))
        m("TwelveNoCfShare", pct(1 - with_cf / len(alerts)))
        m("TwelveCfAlerts", str(with_cf))
        m("TwelveDriftFive", f"{st[st['delta'] == 0.05]['contribution_drift'].median():.3f}")
        m("TwelveSpearman", f"{co['spearman'].median():.2f}")
        m("TwelveCfSame", pct(co["cf_agreement"].mean()))
        m("TwelveStillAlert", pct(co["retrained_alerts"].mean()))
        tp = alerts[alerts["label"] == "tp"]
        m("TwelveFidPrec", f"{tp['evidence_precision'].median():.2f}")
        m("TwelveFidCov", f"{tp['evidence_coverage'].median():.2f}")

    e13 = r / "e13_learned_baselines" / "results.csv"
    if e13.exists():
        from fraudsim.experiments.learned_baselines import paired

        df = pd.read_csv(e13)
        out.append(f"% from {e13.as_posix()}\n")
        prop = df[df["method"] == "proposed"].sort_values(["scenario", "seed"])
        gb = df[df["method"] == "tabular_gb"].sort_values(["scenario", "seed"])
        stat = paired(gb["f1"].fillna(0), prop["f1"].fillna(0))
        m("ThirteenPropF", f"{prop['f1'].mean():.3f}")
        m("ThirteenGbF", f"{gb['f1'].mean():.3f}")
        m("ThirteenPropP", f"{prop['precision'].mean():.2f}")
        m("ThirteenGbP", f"{gb['precision'].mean():.2f}")
        m("ThirteenPropR", f"{prop['recall'].mean():.2f}")
        m("ThirteenGbR", f"{gb['recall'].mean():.2f}")
        m("ThirteenRb", f"{stat['rank_biserial']:.2f}")
        m("ThirteenP", "< 0.001" if stat["p"] == "<0.001" else f"= {stat['p']}")
        for sc, tag in (("hub_heavy", "Hub"), ("adversarial", "Adv")):
            m(f"ThirteenPropF{tag}", f"{prop[prop['scenario'] == sc]['f1'].mean():.2f}")
            m(f"ThirteenGbF{tag}", f"{gb[gb['scenario'] == sc]['f1'].mean():.2f}")

    e14 = r / "e14_evasion_strength" / "results.csv"
    if e14.exists():
        df = pd.read_csv(e14)
        out.append(f"% from {e14.as_posix()}\n")

        def recall(row: pd.Series) -> float:
            v = json.loads(row["recall_by_evasion"]).get(row["sweep_mode"])
            return float("nan") if v is None else float(v)

        df["swept"] = df.apply(recall, axis=1)
        dec = (
            df[df["sweep_mode"] == "decoy_edges"].groupby(["method", "sweep_value"])["swept"].mean()
        )
        m("FourteenDecoyPropLo", f"{dec['proposed'].min():.2f}")
        m("FourteenDecoyPropHi", f"{dec['proposed'].max():.2f}")
        m("FourteenDecoyLouvainMax", f"{dec['louvain'].loc[8]:.2f}")
        m("FourteenDecoyGbMax", f"{dec['tabular_gb'].loc[8]:.2f}")
        slow = (
            df[df["sweep_mode"] == "low_and_slow"]
            .groupby(["method", "sweep_value"])["swept"]
            .mean()
        )
        m("FourteenSlowPropHi", f"{slow['proposed'].max():.2f}")
        m("FourteenSlowCapLo", f"{slow['static_cap10'].min():.2f}")
        m("FourteenSlowCapHi", f"{slow['static_cap10'].max():.2f}")
    return out


def generate_numbers(output_dir: Path, results_dir: Path = Path("results")) -> Path | None:
    """numbers.tex: every number quoted in the prose, as a macro."""
    out = ["% Numbers quoted in the paper text, generated from results/*/results.csv.\n"]

    def f2(x: float) -> str:
        return "--" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.2f}"

    got = _results(results_dir, "e1_baselines")
    if got:
        df, header = got
        out.append(header)
        s = summarize(df, ["method"]).set_index("method")
        names = {
            "proposed": "Prop",
            "proposed_default": "PropDefault",
            "static_cap10": "CapTen",
            "static_cap100": "CapHundred",
            "louvain": "Louvain",
            "plain_cc": "PlainCC",
        }
        for m, tag in names.items():
            if m in s.index:
                for metric, mt in (("precision", "P"), ("recall", "R"), ("f1", "F")):
                    out.append(_macro(f"E{tag}{mt}", f2(s.loc[m, f"{metric}_mean"])))
                out.append(_macro(f"E{tag}FCI", f2(s.loc[m, "f1_ci95"])))
                out.append(_macro(f"E{tag}Lat", _num(s.loc[m, "detect_ms_p50_mean"])))
                out.append(_macro(f"E{tag}FullLat", _num(s.loc[m, "full_graph_ms_p50_mean"])))
                out.append(_macro(f"E{tag}TTD", _num(s.loc[m, "ttd_p50_s_mean"])))
        out += _evasion_numbers(df, names)
        out.append(_macro("ESeeds", str(df["seed"].nunique())))
        out.append(_macro("EScenarios", str(df["scenario"].nunique())))
        out.append(_macro("ERuns", str(len(df))))
    got = _results(results_dir, "e4_scale")
    if got:
        df, header = got
        out.append(header)
        top = df["users"].max()
        g = df[df["users"] == top]
        inc = g[g["mode"] == "incremental"]["detect_ms_p50"].mean()
        full = g[g["mode"] == "full"]["detect_ms_p50"].mean()
        out.append(_macro("ScaleMaxUsers", f"{int(top):,}"))
        out.append(_macro("ScaleIncMs", _num(inc)))
        out.append(_macro("ScaleFullMs", f"{full:,.0f}"))
        out.append(_macro("ScaleSpeedup", f"{full / inc:,.0f}" if inc else "--"))
    out += _ablation_numbers(results_dir, f2)
    out += _frontier_numbers(results_dir, f2)
    out += _hub_size_numbers(results_dir, f2)
    out += _sweep_numbers(results_dir, f2)
    out += _adaptivity_numbers(results_dir)
    out += _public_numbers(results_dir)
    out += _phase2_numbers(results_dir)
    out += _e1b_numbers(results_dir, f2)
    out += _e2b_numbers(results_dir, f2)
    out += _e5b_numbers(results_dir, f2)
    out += _e6b_numbers(results_dir, f2)
    out += _e4b_numbers(results_dir, f2)
    tuned = Path("configs/tuned.json")
    if tuned.exists():
        t = json.loads(tuned.read_text(encoding="utf-8"))
        out.append(f"% from {tuned.as_posix()}\n")
        out.append(_macro("TunedAlert", str(t["alert_threshold"])))
        out.append(_macro("TunedEdge", str(t["edge_threshold"])))
        out.append(_macro("TunedValF", f2(t["mean_f1"])))
        out.append(_macro("TunedDefaultValF", f2(t["grid"].get("tune_a0.5_e0.5", math.nan))))
        out.append(_macro("TunedGridSize", str(len(t["grid"]))))
    return _write(output_dir, "numbers.tex", "".join(out))


TABLES = (
    generate_baseline_table,
    generate_scenario_table,
    generate_ablation_table,
    generate_scale_table,
    generate_public_table,
    generate_numbers,
)


def export_all(results_dir: Path, output_dir: Path) -> list[Path]:
    return [p for fn in TABLES if (p := fn(output_dir, results_dir)) is not None]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    parser.add_argument("--output-dir", type=Path, default=Path("docs/paper/tables"))
    args = parser.parse_args()
    export_all(args.results_dir, args.output_dir)


if __name__ == "__main__":
    main()
