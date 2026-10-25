# E4b tables (generated)

## E4b-1: timer-based full recomputation (5 scenarios × seeds 1001-1005)

| Method | F1 | TTD p50 (s) | Cost (ms per simulated s) | p F1 | p TTD |
|---|---|---|---|---|---|
| inc | 0.71 | 9.5 | 36.7 | – | – |
| timer_1 | 0.69 | 8.8 | 21.9 | 1.0 | 0.4609 |
| timer_5 | 0.68 | 13.8 | 6.3 | 0.6012 | <0.001 |
| timer_30 | 0.01 | 15.0 | 0.7 | <0.001 | 1.0 |

## E4b-2: scale_sweep with hubs growing with the population (seeds 1001-1003)

| Users | Mode | n | Region p50 | ms per batch/pass p50 (mean; min–max) | Cost (ms per simulated s) |
|---|---|---|---|---|---|
| 1,000 | full | 3 | 1015 | 139.4 (125.5–158.7) | 325.9 |
| 1,000 | incremental | 3 | 973 | 136.9 (123.4–145.2) | 323.0 |
| 1,000 | timer_5 | 3 | 1017 | 150.4 (131.2–168.7) | 27.0 |
| 5,000 | full | 3 | 5009 | 1525.6 (1442.7–1583.7) | 3807.3 |
| 5,000 | incremental | 3 | 1337 | 186.4 (103.9–310.9) | 463.7 |
| 5,000 | timer_5 | 3 | 5009 | 1981.8 (1364.6–2403.0) | 370.9 |
| 20,000 | full | 3 | 20012 | 20275.1 (19421.9–20869.0) | 44907.0 |
| 20,000 | incremental | 3 | 912 | 97.5 (38.5–210.8) | 172.8 |
| 20,000 | timer_5 | 3 | 20014 | 21226.1 (20209.0–22142.4) | 4170.3 |
