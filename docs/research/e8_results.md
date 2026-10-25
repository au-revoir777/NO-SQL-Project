# E8 results: latency on the real stack

Protocol: [`e8_protocol.md`](e8_protocol.md), committed before any result. All
numbers come from `results/e8_stack_latency/` (52 runs from commit `a53be5f`,
clean tree, 60 minutes) and are tabulated in the generated
[`e8_tables.md`](e8_tables.md). Each cell there is the median over seeds of a
per-run percentile.

Environment: Neo4j 5.26 and Redis 7.4 in Docker Desktop (WSL 2) on the
development laptop, with the Python process on the host. Other containers were
running (the manifest lists them), so these numbers describe this laptop, not
a server.

## Findings

1. **The real stack finds exactly what the in-memory engine finds.** In all 52
   runs the sequence of ring updates and the set of flagged rings equal the
   in-memory engine's on the same events. Neo4j and Redis change the timing,
   never the result.
2. **Paced at real time, a flag follows the event that completes its batch by
   a few hundred milliseconds.** Across the five E1 scenarios, the median event
   to flag is 176–438 ms. The p95 is 0.4–3.2 s, and the high tails are in
   `drift` and `high_noise`, the scenarios with the most events per second.
3. **Detection on Neo4j is 3–19 times slower than in memory on the same
   batches.** The median detect time per batch is 52–183 ms on Neo4j, against
   2.8–30.7 ms in memory (paced runs), and 474–708 ms against 39–199 ms in the
   users sweep. Each detection reads its region through Cypher round trips.
4. **Throughput is bounded by Neo4j at about 35–52 events/s on this laptop.**
   Published as fast as possible (users sweep), events queue in Redis: up to
   about 1,000 events of lag, and medians of 9–19 s from event to flag. So the
   real stack keeps up with the paced scenarios (15–80 events/s offered) but
   not with bursts. The in-memory figures in E4 are not a bound on the
   deployed system's throughput.
5. **Most of the "ingest to write" time in paced runs is batching, not
   Neo4j.** The median ingest-to-write latency in paced baseline runs is about
   1.5 s. At about 15 events/s, a 50-event batch takes about 3 s to fill, so an
   event waits about half of that before its batch is written. Event to flag is
   measured from the batch's last event, so it does not include that wait.
6. **The Redis read settings do not matter at these rates.** Over
   `XREAD COUNT` 10–500 × `BLOCK` 5–500 ms, the medians of every metric stay
   within run-to-run noise (event to flag 109–147 ms, throughput 15 events/s).
   At 15 events/s the consumer is never the bottleneck. A rate where it is was
   not reached on this machine, because Neo4j saturates first.
7. **JVM warm-up is real and excluded.** The first run of the session (seed
   999, unpaced) had a detect p95 of 1.7 s (against a p50 of 130 ms) and a
   median event to flag of 7.9 s. It is reported separately and pooled with
   nothing.

## Limitations

- One laptop, Docker Desktop, other containers sharing the CPU. Absolute
  numbers will differ on a server; the comparisons (Neo4j against in-memory on
  the same batches, paced against unpaced) are the result.
- Engine batches are a fixed 50 events, so the runs can be compared with the
  in-memory engine. The live API also flushes a partial batch after 0.25 s
  without events, which would cut the batching wait in finding 5. That variant
  was not measured.
- Three seeds per cell. Percentiles of short runs (tens of flags) are coarse;
  p99 often equals p95 because few values sit in the tail.
- The 20,000-user cell's throughput (52 events/s) exceeds the 1,000-user cell's
  (43). The bootstrap writes the first 10 s of each stream, so the measured
  tails differ in composition. Read across sizes as "no strong dependence on
  users", not as a trend.
