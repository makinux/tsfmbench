English | [日本語](README.ja.md)

# tsfmbench — a financial-practice benchmark for TimesFM 3.0

Benchmarks TimesFM 3.0 (Google's zero-shot time-series foundation model) against the baselines practitioners actually use — Random Walk, EWMA, GARCH/GJR, HAR-RV, implied-volatility (DVOL) regression, LightGBM, AutoETS/Theta — on financial market data deliberately disjoint from the official evaluations (GIFT-Eval / fev-bench / TIME). The design went through two rounds of adversarial review by an independent model panel (Codex gpt-5.6 × Claude Opus) and is frozen in [PREREGISTRATION.md](PREREGISTRATION.md) ([English translation](PREREGISTRATION.en.md)).

**Scope of claims**: this benchmark decides one question only — whether the specified TimesFM 3.0 configuration beats this panel of practical baselines. It says nothing about time-series foundation models in general, nor about production adoption (the weights are under a non-commercial license). The main test window (2025-01 to 2026-08) may overlap TimesFM's training data, so **wins are not reported as evidence of capability** — only losses, calibration quality, and the clean window carry strong information.

## Tasks

| Task | Universe | Benchmark | Primary loss |
|---|---|---|---|
| P — price levels | 8 ECB EUR legs, 6 JGB tenors, Nikkei 225, 8 crypto | Random Walk | MAE ratio vs RW (TOST non-inferiority) |
| V — realized volatility | 8 crypto (5-min RV), Nikkei (Garman-Klass) | EWMA(0.94) | QLIKE (aggregated only as ratio-to-benchmark) |
| U — volume | 8 Coinbase base-volume series | SeasonalNaive(7) | relative MAE vs benchmark |

## Running it

```powershell
uv sync --all-extras
uv run tsfmbench probe                     # data-source reachability
uv run tsfmbench download                  # fetch all sources (--update for increments)
uv run tsfmbench build                     # normalized parquet
uv run tsfmbench audit                     # data audits (exit 1 on violations)
uv run tsfmbench mde                       # pre-run minimum-detectable-effect report
uv run tsfmbench run --task rv --window main
uv run tsfmbench report --task rv --window main
```

## Monthly clean-window reruns (contamination-free evaluation; first meaningful read around 2026-12)

```powershell
uv run tsfmbench download --update
uv run tsfmbench build
uv run tsfmbench audit
uv run tsfmbench run --task rv --window clean
uv run tsfmbench run --task price --window clean
uv run tsfmbench run --task volume --window clean
uv run tsfmbench report --task rv --window clean
```

## Notes for Windows + proxy environments

- uv's default python-build-standalone interpreters can hard-crash on TLS (`OPENSSL_Uplink: no OPENSSL_Applink`) on Windows behind TLS-inspecting proxies → this project pins the python.org 3.12 build (`python-preference = "only-system"` in pyproject)
- Behind a TLS-inspecting proxy, set `system-certs = true` (uv) and rely on runtime `truststore` so the OS certificate store is trusted
- The HF checkpoint is loaded from cache with `HF_HUB_OFFLINE=1` (download it in a torch-free process first)
- Raw Nikkei CSV and the model weights must not be redistributed (both are kept out of git)

## Implementation

Code generation was delegated to Codex (gpt-5.6); Claude (Fable 5) wrote the specifications and did review, execution, and verification. The frozen design and its deviation log live in [PREREGISTRATION.md](PREREGISTRATION.md); the narrative write-up is in [blog/](blog/timesfm3-finance-bench.md) (Japanese). Tests: `uv run pytest -q` (79 + 1 slow).
