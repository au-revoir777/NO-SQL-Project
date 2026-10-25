# E5b results: the first-hop fan-out limit at large hubs

Protocol: `docs/research/e5b_protocol.md` (489d59a), with three amendments, all
compute-only:
1. reduced full-recompute arms;
2. one seed for `log_full` at 10,000;
3. a 3.5 h time cap.

Tables: `docs/research/e5b_tables.md` (generated). Runs: `results/e5b_large_hubs/`.
The shipped-weight full-recompute run at 10,000 users (seed 1001) did not finish
within 3.5 h and was stopped at 21:00 UTC. No number is reported for it.

## Findings

1. **The 250-user limit hides nothing for the shipped weight.** The bound
   crossing rule matched the 250 limit exactly in all 15 runs: precision,
   recall, F1, flagged rings and region size. It never added a user, because a
   pair linked only through attributes above 250 users weighs at most about
   0.18 per such attribute, below the edge threshold 0.3.
2. **The test is sensitive.** On the same streams, the constant weight
   (threshold 1.0) found fewer hub-hiding rings with the limit than with full
   recomputation at 500 users: 9/15 vs 12/15, F1 0.74 vs 0.85. It was lower in
   3 of 5 runs; with n = 5 this is not significant (p = 0.25). At 2,000 users
   (3 seeds) the gap is 10/15 vs 7/9.
3. **Full recomputation is not identical run by run** for the shipped weight:
   identical P/R/F1 in 3/5 runs at 500 and 2/5 at 2,000, because it sees groups
   outside the region. It found no more hub-hiding rings (11/15 vs 11/15;
   9/15 vs 10/15), and its F1 was not higher (0.79 vs 0.79; 0.80 vs 0.83).
4. **Cost.** The incremental region has a median of 14 users at 2,000 and
   10,000, against up to 2,076 for full recomputation. One full run took 6.5
   minutes (shipped weight) or 32 minutes (constant weight) at 2,000 users, and
   more than 3.5 h at 10,000.
5. **The static rules stay behind:** F1 0.46, 0.60 and 0.63 at cap 10.

## Wording used in the paper

"For hubs up to 10,000 accounts, the limit did not hide hub-sharing rings for
the hub-aware weight; for a constant weight it can." The equivalence is tested
up to 10,000-user hubs, five seeds per size, on one scenario (Threats: Scale).
