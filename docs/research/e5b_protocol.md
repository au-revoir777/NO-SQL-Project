# E5b: the first-hop fan-out limit at large hubs

Committed before any E5b result exists. Motivation: refinement issue P3
(`docs/paper/paper_refinement_prompt.md`). The incremental engine expands each
batch's touched users through attributes with at most 250 active users on the
first hop and at most 20 later. A ring whose members are linked only through a
larger attribute is therefore outside the region, which is a degree cap again.
E5 tested hubs up to 200 users only.

## Analysis stated before running

In the region, a pair (u, v) is reachable through a transfer between them, or
through any shared attribute under the fan-out limit. The fan-out limit can
therefore hide only pairs whose *only* link is one or more attributes above the
limit. For such a pair the attribute part of W is at most the sum of h(d) over
those attributes, and the transfer part is zero. With the shipped h = 1/ln(1+d)
and d > 250, one attribute contributes at most 0.18, below the edge threshold
0.3, so such a pair needs two or more large hubs in common before the full
detector would link it. For the constant weight with edge threshold 1.0 (E2b),
one large hub already reaches the threshold. So we expect the limit to be
harmless for the shipped weight and to change results for the constant weight.

## Alternative crossing rule ("bound")

On the first hop, an attribute above the limit is not ignored. Its co-members v
of each touched user u are counted, and v joins the region if the sum of h(d)
over the large attributes u and v share is at least the hub-aware edge
threshold. Pairs below that bound cannot pass the edge threshold without a
transfer, and with a transfer they are reached through the transfer anyway. For
the hub-aware detector, this rule therefore reaches every pair that a full
recomputation could link, up to time decay, which only lowers weights. Its cost is
one pass over the co-members of every large attribute a touched user holds.

## Design

- Scenario `hub_heavy`, the office gateway resized to 500, 2,000 and 10,000
  users (`simulation.num_users` = size + 50, as in E5). The planted ring
  `ring_behind_office` shares this gateway.
- Seeds 1001-1005 (as E5).
- Methods (alert threshold 0.8, shipped scorer):

| Name | Weight, edge threshold | Engine |
|---|---|---|
| `log_fanout` | 1/ln(1+d), 0.3 | incremental, fan-out 250 / 20 (shipped) |
| `log_bound` | 1/ln(1+d), 0.3 | incremental, bound crossing |
| `log_full` | 1/ln(1+d), 0.3 | full recomputation every batch |
| `const_fanout` | constant, 1.0 | incremental, fan-out 250 / 20 |
| `const_full` | constant, 1.0 | full recomputation every batch |
| `static_cap10`, `static_cap100` | E1 baselines | full graph on a 5 s timer |

- Metrics: ring precision, recall and F1; recall of rings with hub-hiding
  evasion; region size per batch (median, maximum); detection latency per batch
  (median); wall time.
- Comparison: each incremental arm against its full-recomputation arm
  (identical streams). We report whether flagged rings and F1 match, plus a
  paired Wilcoxon on F1 over the 15 runs.
- Contingency, fixed in advance: if a full-recomputation arm at 10,000 users
  takes more than 2 hours in total, it runs on seeds 1001-1003 only, and that is
  stated wherever its numbers appear.

## Outputs

`results/e5b_large_hubs/`, `docs/research/e5b_tables.md` (generated),
`docs/research/e5b_results.md`. The run row gains `region_p50` and `region_max`
(new columns; existing results are unchanged).

Amendments, if any, are appended below with their reason.

## Amendment 1 (2026-10-25, before any result at 10,000 users)

Compute only; no result at 10,000 users existed when this was written. At 2,000
users one full-recomputation run of the constant weight (`const_full`) took
2,116 s, and one of the shipped weight (`log_full`) took 392 s. The constant
weight links all of the hub's co-members at weight 1.0, so every full pass peels
one very large component. On the original schedule the 10,000-user full arms
would take well over ten hours, so the 2-hour contingency would be exceeded by
its own first three seeds. Changes:

- 2,000 users: `log_full` on all five seeds; `const_full` on seeds 1001-1003 only.
- 10,000 users: incremental arms and caps on all five seeds; `log_full` on seeds
  1001-1003, extended to 1004-1005 under the original 2-hour rule; `const_full`
  not run. Its cost at 2,000 users is reported instead, as a result in itself.
- Runs already recorded are kept, not repeated. The process was stopped during
  `const_full` seed 1002 at 2,000 users, and that run is redone.

## Amendment 2 (2026-10-25, before the first 10,000-user `log_full` result)

Compute only, decided by the author. The first `log_full` seed at 10,000 users
had run for more than 45 minutes without finishing. The equivalence question
(bound crossing vs the 250-user limit) was already answered by the incremental
arms at all three sizes; `log_full` at 10,000 users is only a reference point.
`log_full` at 10,000 users is therefore stopped after seed 1001 and reported as
"1 seed, compute-only reference", without an interval. One seed also cannot
show whether the full-recomputation time is stable.

## Amendment 3 (2026-10-25 19:12 UTC, before the 10,000-user `log_full` result)

Compute only. The single `log_full` run at 10,000 users (seed 1001), started at
about 17:20 UTC, was still running after nearly two hours, with the process at
3.5 GB of the machine's 7.7 GB. If it has not finished by 21:00 UTC, it is
stopped and reported as "did not finish within 3.5 h on the test laptop". No
F1 is reported for it in that case. Its timing would be confounded by memory
pressure in any case, as the 50k and 100k points of E4 were.
