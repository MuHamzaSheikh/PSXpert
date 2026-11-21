# PSXpert combined_v2 results

Rebuilt 34,780 common eligible rows with fixed 20-market-session targets and inclusive sideways boundaries [-3%, +3%]. All three experiments use identical row keys and partitions.

The v1 eligible cohort contains **343 inconsistent candles**, traced to source primary keys in `audit/v1_cohort_candle_source_trace.csv`. Across all raw source history, 17,493 candles were flagged. OHL fields are masked only in memory; positive closes and volumes are retained. No raw prices were numerically adjusted.

## Audit and limitations

Largest daily moves are traced to original IDs and source names. Large moves below the discontinuity threshold remain in the data. No large move was independently certified as economically genuine: pyPSX credentials/coverage status is recorded in source_audit.json. Unresolved >=35% jumps retain the v1 segment reset and label quarantine. This deliberately avoids guessing split factors, but may exclude genuine moves. The full target-exclusion ledger distinguishes missing endpoints, discontinuity exposure, and provisional announcement windows.

Corporate payouts contain announcement dates but no effective/ex-dates or adjustment factors. The external PSX notice verifies BML revised-price trading from February 2, 2026; this confirms the existing jump quarantine. MARI bonus entitlement, book closure and credit dates were checked, but these do not establish its exact ex-trading date. See verified_action_evidence.json for primary-source URLs. Remaining effective dates have not been independently verified. The v1 announcement +/-5-day quarantine remains provisional. Thus the requested corporate-action validation is incomplete, and these results are conditional on that limitation.

Financial joins were checked against eligible annual-report transmission evidence, with publication availability at or before every prediction. Source financial metrics, announcements, accepted panel and row-level joins are saved. Missingness is broken down by ticker, sector and year, including tickers without eligible filings. Current statement snapshots cannot prove historical accounting vintages; the current roster also introduces survivorship risk.

## Validation protocol

Three expanding market-wide folds use distinct training, calibration and forward validation windows. Target resolution must precede each following window by more than five market sessions. Imputation, scaling, class weights and estimator parameters are fitted using training data only. Candidates cover the training-majority baseline, the raw v1 recipe refitted per fold, regularized logistic regression and a small XGBoost grid. Macro F1 selects the configuration, with log loss breaking ties. Calibration is accepted only if every window improves log loss and no class loses more than two recall percentage points.

Walk-forward scores below are model-selection results, not an unbiased nested assessment. The saved raw v1 model is compared only on its historical test keys. A newly refitted v1 recipe provides the leakage-safe walk-forward comparison.

Fresh eligible rows after the inspected v1 outcomes and embargo: **0**. Fresh held-out performance remains unverified.

## Walk-forward model-selection results

| Experiment | Selected | Accuracy | Balanced accuracy | Macro F1 | Log loss | Majority accuracy | V1 recipe accuracy |
|---|---|---:|---:|---:|---:|---:|---:|
| technical | xgb_d2_n160_extra1_weighted1:raw | 36.96% | 36.97% | 0.3623 | 1.0960 | 47.24% | 43.55% |
| fundamental | xgb_d3_n240_extra1_weighted1:raw | 38.51% | 36.56% | 0.3645 | 1.0903 | 47.24% | 44.79% |
| combined | xgb_d3_n240_extra1_weighted1:raw | 40.00% | 38.05% | 0.3793 | 1.0848 | 47.24% | 45.60% |

## Inspected historical v1 benchmark

These comparisons use identical historical rows and unchanged targets. V2 model selection used overlapping dates, so these are descriptive comparisons.

| Experiment | Rows | V2 accuracy | Training-majority accuracy | Saved raw v1 accuracy | V2 minus v1 |
|---|---:|---:|---:|---:|---:|
| technical | 5515 | 38.86% | 37.41% | 38.06% | +0.80 pp |
| fundamental | 5515 | 38.37% | 37.41% | 39.29% | -0.92 pp |
| combined | 5515 | 41.38% | 37.41% | 40.65% | +0.73 pp |

## What helped

- combined, causal_features: mean paired change in validation macro F1 +0.0066; log loss +0.0080. Individual paired results are in ablations.csv; an average does not imply every candidate improved.
- combined, class_weights: mean paired change in validation macro F1 +0.0498; log loss +0.0042. Individual paired results are in ablations.csv; an average does not imply every candidate improved.
- fundamental, causal_features: mean paired change in validation macro F1 -0.0026; log loss +0.0072. Individual paired results are in ablations.csv; an average does not imply every candidate improved.
- fundamental, class_weights: mean paired change in validation macro F1 +0.0619; log loss +0.0057. Individual paired results are in ablations.csv; an average does not imply every candidate improved.
- technical, causal_features: mean paired change in validation macro F1 +0.0179; log loss +0.0004. Individual paired results are in ablations.csv; an average does not imply every candidate improved.
- technical, class_weights: mean paired change in validation macro F1 +0.0608; log loss +0.0251. Individual paired results are in ablations.csv; an average does not imply every candidate improved.

The audit masking change was not isolated in a separate full model ablation, so its predictive contribution cannot be attributed. It makes the candle treatment explicit. Per-class recall, confusion matrices, predicted class frequencies, log loss and regressor errors are saved in each experiment comparison.json.

## Reproduction

Run from `module 1 technical and fundamental`:

```powershell
python -m pytest -q
python -m m1.v2 --as-of 2026-11-16T14:00:00+05:00
python -m m1.v2_report
python -m m1.v2_verify
```

The training command refuses an existing combined_v2 directory. Reproduce in a separate checkout with the same read-only source snapshot. The PostgreSQL connection enforces read-only transactions. Before/after SHA-256 manifests cover existing CSVs, SQLite data and combined_v1 artifacts. The v1 serving API is preserved; load v2 research classifier/calibrator and regressor using `m1.v2.load_pair`.
