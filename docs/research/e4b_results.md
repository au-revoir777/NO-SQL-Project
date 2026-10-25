# E4b results: latency against timer baselines and growing hubs

Protocol: `docs/research/e4b_protocol.md` (e5546b0). Tables:
`docs/research/e4b_tables.md` (generated). Runs: `results/e4b_timer/` and
`results/e4b_scale_hubs/`. Both were recorded on a clean tree.

## E4b-1: timer-based full recomputation (5 accuracy scenarios × seeds 1001-1005)

| Method | F1 | TTD p50 (s) | Cost (ms per simulated s) | p F1 vs incremental |
|---|---|---|---|---|
| incremental (every batch) | 0.71 | 9.5 | 37 | - |
| full graph every 1 s | 0.69 | 8.8 | 22 | 0.62 |
| full graph every 5 s | 0.68 | 13.8 | 6 | 0.61 |
| full graph every 30 s | 0.01 | 15.0 | 1 | <0.001 |

On graphs of 30 to 200 users, a 1 s timer matches incremental detection in F1
and TTD at lower cost. A 30 s timer fails because rings end before two passes
confirm them.

## E4b-2: scale_sweep with hubs growing with the population (seeds 1001-1003)

| Users | Incremental | 5 s timer | Every batch, full |
|---|---|---|---|
| 1,000 | 323 | 27 | 326 |
| 5,000 | 464 | 371 | 3,807 |
| 20,000 | 173 | 4,170 | 44,907 |

Cost is in ms of detection per simulated second. The incremental region median
is 973, 1,337 and 912 users.

## Reading

- The 623x speed-up of E4 is a worst-case bound. It compares against recomputing
  every 50-event batch, which no deployment would do. The paper now says so.
- Against a timer, incremental detection buys nothing on small graphs. Its
  value is at scale: at 20,000 users the 5 s timer needs about 4 s of compute
  per simulated second and cannot keep up, while the incremental engine needs
  0.17 s.
- Hubs that grow with the population did not blow up the region; it stayed
  near 900-1,300 users. This rests on the fan-out limits of P3.
- TTD is not improved by incremental detection over a 1 s timer (8.8 vs 9.5 s).
  The paper no longer implies otherwise.
