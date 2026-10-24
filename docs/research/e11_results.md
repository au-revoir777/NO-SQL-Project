# E11 results: early-warning lead time without look-ahead

Protocol: [`e11_protocol.md`](e11_protocol.md) (committed before any result;
no amendments). Data: `results/e11_early_warning/` (run at commit `4d7b082`,
`git_dirty: false`). Tables are generated: [`e11_tables.md`](e11_tables.md)
(`python -m fraudsim.experiments.early_warning_eval --report docs/research/e11_tables.md`).
Synthetic-simulator results for the tuned proposed detector, E1's five
scenarios, test seeds 1001–1010.

## Findings

1. **Early warning is rare.** Of 227 eligible true rings (activated, with a
   forming phase), 30 were warned before activation: 13% (seed-bootstrap
   interval 10–17%). All 30 first warnings were `early_warning` events on
   still-forming candidates, not alerts.
2. **The warnings that do come are early in relative terms.** Median lead time
   is 2.2 s of simulated time (IQR 0.9–4.4). Rings take a median of 3.9 s to
   form in these scenarios, so a warned ring is typically flagged about halfway
   through its forming phase (median lead / forming time 0.54).
3. **It depends strongly on the ring type.** Mixed-attribute rings are warned
   most often (15 of 24). Shared-device rings come next (13 of 57). Shared-IP,
   layered-chain and smurfing rings are never warned. Money cycles (1 of 38)
   and shared-card rings (1 of 26) almost never are: they only become visible
   once they transact.
4. **Early warnings are mostly right.** 84% of tracked rings' first early
   warnings point at a real forming or active ring (37 false out of 231).
   Precision is lowest in drift (0.70) and high_noise (0.79).
5. **Look-ahead did not inflate the old count.** The old final-member
   definition gives 29 rings on the same runs, the new one 30. The single
   difference is a ring the old definition missed (adversarial, seed 1007),
   most likely because the tracked ring later absorbed accounts outside the true
   ring and failed the final-member precision test. Existing E1–E7 values of
   `early_warnings_before_activation` are therefore not overstated by
   look-ahead, but they are a count, not a rate, and the column name hides
   that alerts also count.

## Caveats

- Lead times are in compressed simulated time. Only their relation to the
  forming time is meaningful, not their absolute size.
- The qualifying thresholds (≥ 2 shared members, ≥ 0.66 of the warned set)
  were kept from the existing code, so that removing look-ahead was the only
  change. The protocol did not test other thresholds.
- Seven true rings were spawned at full size and activated immediately, so
  they cannot be warned early and are excluded.
