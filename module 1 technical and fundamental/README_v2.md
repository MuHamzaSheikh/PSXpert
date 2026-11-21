# combined_v2 research workflow

Run from this directory:

```powershell
python -m pytest -q
python -m m1.v2 --as-of 2026-11-16T14:00:00+05:00
python -m m1.v2_report
python -m m1.v2_verify
```

The training command refuses to overwrite `artifacts/combined_v2`. Reproduce in a separate checkout against the same source snapshot. Sources use the existing PostgreSQL read-only transaction guard; SQLite fallback is rejected. Existing project CSVs and combined_v1 artifacts are hashed before and after.

The v2 implementation is isolated in `m1/v2.py`. It preserves the v1 API and its artifact schema. Load v2 research artifacts with `m1.v2.load_pair(experiment)`. The returned classifier bundle includes its feature order and calibrator; use `m1.v2.probabilities` and `m1.v2.calibrate` for probabilities. The second return value is the saved return regressor. Do not pass a v2 version to the v1 prediction endpoint.

Targets remain 20 KSE-100 sessions with BEARISH below -3%, SIDEWAYS from -3% through +3%, and BULLISH above +3%. Every experiment uses the same eligible rows. Three expanding windows separate training, calibration and validation with global target-date purging and a five-market-session embargo. Model selection maximizes mean macro F1, breaking ties by log loss. Probability calibration additionally requires improved log loss in every validation window without any per-class recall decline exceeding two percentage points.

The training-majority baseline uses training class frequencies (Laplace-smoothed probabilities for finite log loss). `v1_recipe` refits the unchanged v1 parameters inside each split to avoid applying future-trained weights to earlier windows. The saved raw v1 classifier is evaluated separately on the common historical v1 test keys. That benchmark has already been inspected, and v2 selection includes overlapping dates; it is not a fresh holdout.

A later assessment requires at least 1,000 rows, 60 eligible signal sessions and all three classes after the last inspected v1 outcome plus the embargo. Otherwise the report explicitly leaves fresh held-out performance unverified. This minimum is a predeclared implementation rule, not a claim of statistical power.

No fabricated action factors are applied. Invalid OHL fields are masked in memory, while valid closes and volumes remain unchanged. Existing unverified jump/announcement quarantines are recorded rather than silently removed. Available PSX action evidence is summarized separately. pyPSX is queried only when its SDK and credentials are configured. Unknown accounting revision vintages and historical roster membership remain limitations.

See `artifacts/combined_v2/REPORT.md` for outcomes, `comparison.json` for complete metrics, `ablations.csv` for paired changes, `splits.json` and `split_*.csv.gz` for exact partitions, and `audit/` for source and row-level evidence.
