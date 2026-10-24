# E11: early-warning lead time without look-ahead (protocol)

Workstream F of `master_prompt2.md`, finding R4 of the M0 audit. Committed
**before** any E11 result is computed; later changes go under "Amendments".

## Why

The existing column `early_warnings_before_activation` (E1–E7) counts unique
true rings whose first early warning **or** alert came before activation. It
matches a tracked ring to a true ring using the **final** members of both, so a
warning can be credited because of members who joined after the warning. Per-ring
lead times are not stored. E11 re-runs the E1 configuration of the proposed
method and logs every warning with the members shown at that moment.

## Configuration

Same as E10: the tuned proposed detector (`tuned_proposed()`, threshold 0.8),
the shipped scorer, E1's five scenarios, test seeds 1001–1010. E1 and E10 files
are not touched.

## Simulator semantics used

A ring spawns with some members, recruits until it reaches its target size,
and is then **activated** (`activate_ts`; it starts its fraudulent actions).
Rings spawned at full size activate at spawn.

## Definitions (fixed before results)

- **Eligible true ring**: activated during the run, with `activate_ts > spawn_ts`
  (it had a forming phase). Others are counted but not eligible.
- **Warning event**: an `early_warning` (ring still a candidate) or `alert`
  (ring confirmed) update raised by the scoring stage at time *t* for tracked
  ring *R*, with members *M_t* exactly as shown at that moment.
- **Members known by t**: *J_t(G)* = every account that joined true ring *G* at
  or before *t* (from the ledger's member history).
- **Qualifying warning for G**: |*M_t* ∩ *J_t(G)*| ≥ 2 and
  |*M_t* ∩ *J_t(G)*| / |*M_t*| ≥ 0.66. These are the thresholds of the existing
  `lead_times`, kept so the only change is removing look-ahead.
- **Warned before activation**: G's first qualifying warning has *t* <
  `activate_ts`. **Lead time** = `activate_ts` − *t* (seconds of simulated time).
  It is reported both for warnings of either kind and for `early_warning` events
  only.
- **Warning precision**: the unit is a tracked ring's **first** `early_warning`
  event. It is correct if it qualifies for any true ring spawned by *t*. False
  early warnings = units that qualify for none. They are reported as counts and
  per simulated hour; simulated time is compressed, so the hourly rate is not an
  operational rate.
- **Old metric, for comparison**: the existing final-member definition, computed
  on the same runs, to measure how much look-ahead changed the count.

## Reporting

Per scenario and pooled: eligible rings, warned before activation (share, with
95% seed-cluster bootstrap interval, 2,000 resamples), lead-time median and
quartiles among warned rings, warning precision, and false early warnings. Per
ring type where ≥ 10 eligible rings, otherwise counts only. Seeds are the
resampling unit; rings within a run are not treated as independent.

## Outputs

`results/e11_early_warning/`: `rings.csv` (one row per true ring),
`warnings.csv` (one row per first early warning of a tracked ring),
`results.csv` (one row per run), `manifest.json`, and the generated
`summary.csv`, `by_type.csv`, and `docs/research/e11_tables.md`.

## Amendments

None yet.
