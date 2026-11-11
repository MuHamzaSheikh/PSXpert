# Chronological Split Definitions & Overlapping-Label Purge Policy

## 1. Primary Full-History Chronological Splits (2002–2026)
- **Calendar**: `PSX KSE-100 Exchange Trading Days (market_indices)` (6,127 trading sessions from `2002-01-01` to `2026-10-13`).
- **Purge Policy**: **25 trading days** (`25`-session buffer covering max `<=23`-session calendar span of `20d` targets) purged strictly before Validation and before Test so ZERO future-return targets overlap into subsequent splits.

| Split Name | Start Date | End Date | Trading Days | Purpose |
| :--- | :--- | :--- | ---: | :--- |
| `TRAIN` | `2002-01-01` | `2021-11-26` | 4,923 | Model fitting, scaler/feature-selector estimation, HMM parameter training |
| `PURGE_TRAIN_VAL` | `2021-11-29` | `2021-12-31` | 25 | 25-session purge buffer separating Train 20d targets (<=23 cal span) from Val |
| `VAL` | `2022-01-03` | `2024-05-20` | 586 | Hyperparameter tuning, ensemble calibration, early stopping |
| `PURGE_VAL_TEST` | `2024-05-21` | `2024-06-28` | 25 | 25-session purge buffer separating Val 20d targets (<=23 cal span) from Test |
| `TEST` | `2024-07-01` | `2026-10-13` | 568 | Strictly unseen out-of-sample final generalization benchmark |

## 2. Fundamentals-Dense Sub-Regime Splits (2022–2026)
For forecasting models requiring audited IFRS accounting ratios (`fin_*`, populated 2022–2026):

| Sub-Split | Start Date | End Date | Trading Days |
| :--- | :--- | :--- | ---: |
| `FUND_TRAIN` | `2022-01-03` | `2024-05-20` | 586 |
| `FUND_PURGE_TRAIN_VAL` | `2024-05-21` | `2024-06-28` | 25 |
| `FUND_VAL` | `2024-07-01` | `2025-05-20` | 220 |
| `FUND_PURGE_VAL_TEST` | `2025-05-21` | `2025-06-30` | 25 |
| `FUND_TEST` | `2025-07-01` | `2026-10-13` | 323 |

## 3. Rolling Expanding Walk-Forward Validation Folds (With 25-Day Purge)
| Fold | Effective Train Window | Purged Buffer | Out-of-Sample Test Window |
| :--- | :--- | :--- | :--- |
| Fold 1 | `2002-01-01..2021-11-26` (4,923d) | `2021-11-29..2021-12-31` (25d) | `2022-01-03..2022-12-30` (247d) |
| Fold 2 | `2002-01-01..2022-11-25` (5,170d) | `2022-11-28..2022-12-30` (25d) | `2023-01-02..2023-12-29` (245d) |
| Fold 3 | `2002-01-01..2023-11-23` (5,415d) | `2023-11-24..2023-12-29` (25d) | `2024-01-01..2024-12-31` (246d) |
| Fold 4 | `2002-01-01..2024-11-25` (5,661d) | `2024-11-26..2024-12-31` (25d) | `2025-01-01..2025-12-31` (248d) |
| Fold 5 | `2002-01-01..2025-11-25` (5,909d) | `2025-11-26..2025-12-31` (25d) | `2026-01-01..2026-10-13` (193d) |
