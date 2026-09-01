# Analytic minimum detectable effects

Two-sided alpha = 0.05; power = 0.8. MDE values use finite-sample t quantiles.

The reference QLIKE ratio is `1 + MDE_SD` and assumes `SD(loss difference) / mean(benchmark QLIKE) = 1`. It is a schedule-only reference, not an empirical scale conversion.

| task | h | step | origins | design effect | MDE (SD) | reference QLIKE ratio |
|---|---:|---:|---:|---:|---:|---:|
| price | 1 | 5 | 122 | 1.0000 | 0.2557 | 1.2557 |
| price | 5 | 5 | 121 | 1.0000 | 0.2568 | 1.2568 |
| price | 20 | 5 | 118 | 4.0000 | 0.5345 | 1.5345 |
| rv | 1 | 1 | 607 | 1.0000 | 0.1139 | 1.1139 |
| rv | 5 | 5 | 121 | 1.0000 | 0.2568 | 1.2568 |
| rv | 22 | 22 | 27 | 1.0000 | 0.5603 | 1.5603 |
| volume | 1 | 5 | 122 | 1.0000 | 0.2557 | 1.2557 |
| volume | 5 | 5 | 121 | 1.0000 | 0.2568 | 1.2568 |
