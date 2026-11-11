"""Fundamental Analysis ML Pipeline: PIT dataset builder, label feasibility audit, and diagnostic benchmark."""

from __future__ import annotations

import json
import logging
import platform
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd
import sklearn
from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.analysis.common import safe_div, safe_float, sanitize_for_json
from src.analysis.fundamental_engine import FundamentalAnalysisEngine
from src.ml.metrics import evaluate_by_regime, evaluate_multiclass_predictions
from src.predictive_data.regime_causal import CausalMarketRegimeHMM

logger = logging.getLogger(__name__)

FUNDAMENTAL_ML_VERSION = "psxpert_fund_ml_audit_v2.0"
FUND_CLASSES = ["Weak", "Moderate", "Strong"]  # 0, 1, 2
DEFAULT_FUND_ARTIFACTS_DIR = Path("artifacts/fundamental")
DEFAULT_FUND_DIR = DEFAULT_FUND_ARTIFACTS_DIR
DEFAULT_FUND_REPORTS_DIR = Path("reports/ml")

FUND_FEATURE_COLS: list[str] = [
    "eps_pkr",
    "revenue_growth_yoy",
    "net_income_growth_yoy",
    "eps_growth_yoy",
    "roe",
    "roa",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "pe_pit",
    "pb_pit",
    "earnings_yield_pit",
    "debt_to_equity",
    "current_ratio",
    "interest_coverage",
    "ocf_margin",
    "fcf_margin",
    "ocf_to_ni",
    "fcf_yield_pit",
    "cf_dividend_yield_pit",
    "cash_payout_ratio",
    "fcf_dividend_coverage",
    "sector_roe_diff",
    "sector_net_margin_diff",
    "sector_pe_diff",
    "sector_pb_diff",
    "sector_de_diff",
    "is_bank",
    "has_classified_sector",
]

PROPOSED_FUNDAMENTAL_TARGET_SPEC = {
    "target_name": "next_12m_fundamental_health_and_distress_outcome",
    "classes": ["Strong", "Moderate", "Weak"],
    "economic_definition": {
        "Strong": (
            "Company maintains or achieves investment-grade credit stability (PACRA/VIS >= A-), "
            "delivers positive YoY operating income/EPS growth, ROE >= sector median (or >= 15%), "
            "positive Free Cash Flow (OCF/NI >= 0.8), and maintains uninterrupted cash dividends."
        ),
        "Moderate": (
            "Company stays solvent with positive operating cash flow and no rating downgrade or covenant breach, "
            "but shows flat/modest earnings growth, margin compression, or moderate leverage."
        ),
        "Weak": (
            "Independent external credit rating downgrade to sub-investment tier (< BBB) / PSX Defaulter Counter "
            "placement / dividend omission after prior payouts, OR severe realized FY_{t+1} distress "
            "(net loss <= 0, negative operating cash flow, equity erosion, or Interest Coverage < 1.25x)."
        ),
    },
    "mandatory_data_prerequisites": [
        "1. Historical PACRA / VIS credit-rating panel and PSX Defaulter Segment / delisting date logs (eliminating 100% survivorship bias).",
        "2. >= 8-10 years of audited annual + clean quarterly IFRS disclosures across >= 300+ firms (>= 1,500 non-overlapping train transitions before Val/Test).",
        "3. Full sector classification for the 61 currently unclassified IFRS firms (of 711 unclassified total) and pre-2025 corporate_payouts dividend backfill.",
    ],
}


def build_fundamental_disclosures_dataset(
    conn: Connection,
    max_date: date = date(2026, 10, 13),
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Construct a clean, non-duplicated point-in-time dataset of unique IFRS disclosures
    (1 row per (symbol, period_end_date)) strictly aligned to effective_pub_date <= max_date,
    with KSE-100 price/market_cap, sector-relative spreads, and causal t+1 outcome columns.
    """
    fe = FundamentalAnalysisEngine()
    comp_rows = conn.execute(
        text(
            """
            SELECT DISTINCT cf.symbol, c.sector, c.sector_category, c.is_active, c.is_kse100
            FROM company_financials cf
            JOIN companies c ON c.symbol = cf.symbol
            WHERE cf.statement_type IN ('INCOME_STATEMENT', 'BALANCE_SHEET', 'CASH_FLOW')
            ORDER BY cf.symbol
            """
        )
    ).mappings().all()
    meta_map = {r["symbol"]: dict(r) for r in comp_rows}
    stmts_map = fe._load_pit_statements_for_symbols(conn, list(meta_map.keys()), max_date)

    # Load clean KSE-100 aligned prices for valuation on effective_pub_date
    px_df = pd.read_sql(
        text(
            """
            SELECT sp.symbol, sp.trading_date, sp.close, sp.market_cap, sp.source_id
            FROM stock_prices sp
            JOIN market_indices mi ON mi.trading_date = sp.trading_date AND mi.index_symbol = 'KSE100'
            WHERE sp.symbol = ANY(:syms) AND sp.close > 0 AND sp.trading_date <= :max_d
            ORDER BY sp.symbol, sp.trading_date, sp.source_id
            """
        ),
        conn,
        params={"syms": list(meta_map.keys()), "max_d": max_date},
    )
    px_df["trading_date"] = pd.to_datetime(px_df["trading_date"])
    px_df = px_df.drop_duplicates(subset=["symbol", "trading_date"], keep="last").sort_values(["trading_date", "symbol"])

    # Causal KSE-100 HMM on calendar
    idx_df = pd.read_sql(
        text(
            """
            SELECT trading_date, open, high, low, close, volume
            FROM market_indices WHERE index_symbol = 'KSE100' AND trading_date <= :max_d
            ORDER BY trading_date
            """
        ),
        conn,
        params={"max_d": max_date},
    )
    idx_dates = pd.to_datetime(idx_df["trading_date"]).dt.date
    hmm = CausalMarketRegimeHMM(n_states=3, random_state=42).fit(idx_df[idx_dates <= date(2021, 11, 26)])
    hmm_daily = hmm.filter_causal_probabilities(idx_df)
    hmm_daily["trading_date"] = pd.to_datetime(hmm_daily["trading_date"]).dt.date
    hmm_lookup = hmm_daily.set_index("trading_date")["hmm_mkt_regime_label"].to_dict()

    # Flatten unique IFRS statements + attach prior (t-1) for growth and next (t+1) for transition audit
    base_records: list[dict[str, Any]] = []
    for sym, plist in stmts_map.items():
        m = meta_map[sym]
        sec = (m.get("sector") or "").strip()
        has_sec = sec.upper() not in ("", "OTHER / UNCLASSIFIED", "OTHER / PSX HISTORICAL", "UNCLASSIFIED", "N/A", "NONE")
        is_bank = (m.get("sector_category") or "").strip().lower() == "banks" or sec.upper() == "COMMERCIAL BANKS"

        for i, p in enumerate(plist):
            prev = plist[i - 1] if i > 0 else None
            nxt = plist[i + 1] if i + 1 < len(plist) else None

            rev, ni, eq, assets = p["total_revenue"], p["net_income"], p["common_stock_equity"], p["total_assets"]
            ocf, fcf = p["operating_cash_flow"], p["effective_fcf"]
            debt, ca, cl = p["total_debt"], p["current_assets"], p["current_liabilities"]
            ebit, op_inc, ie = p["ebit"], p["operating_income"], p["interest_expense"]
            div_paid = abs(p["cash_dividends_paid"]) if p["cash_dividends_paid"] is not None else None

            rev_g = ni_g = eps_g = np.nan
            if prev is not None and 300 <= (p["period_end_date"] - prev["period_end_date"]).days <= 430:
                if rev is not None and prev["total_revenue"] and prev["total_revenue"] != 0:
                    rev_g = (rev - prev["total_revenue"]) / abs(prev["total_revenue"])
                if ni is not None and prev["net_income"] and prev["net_income"] != 0:
                    ni_g = (ni - prev["net_income"]) / abs(prev["net_income"])
                if p["effective_eps"] is not None and prev["effective_eps"] and prev["effective_eps"] != 0:
                    eps_g = (p["effective_eps"] - prev["effective_eps"]) / abs(prev["effective_eps"])

            roe = safe_div(ni, eq, require_positive_den=True)
            roa = safe_div(ni, assets, require_positive_den=True)
            gm = np.nan if is_bank else safe_div(p["gross_profit"], rev, require_positive_den=True)
            om = np.nan if is_bank else safe_div(op_inc, rev, require_positive_den=True)
            nm = safe_div(ni, rev, require_positive_den=True)
            de = safe_div(debt, eq, require_positive_den=True)
            cr = np.nan if is_bank else safe_div(ca, cl, require_positive_den=True)
            ic_num = ebit if ebit is not None else op_inc
            ic = np.nan if (is_bank or ie is None or abs(ie) == 0 or ic_num is None) else float(ic_num / abs(ie))
            ocf_margin = safe_div(ocf, rev, require_positive_den=True)
            fcf_margin = safe_div(fcf, rev, require_positive_den=True)
            ocf_to_ni = safe_div(ocf, ni, require_positive_den=True)
            cash_payout = safe_div(div_paid, ni, require_positive_den=True)
            fcf_div_cov = safe_div(fcf, div_paid, require_positive_den=True)

            base_records.append(
                {
                    "symbol": sym,
                    "sector": sec if has_sec else "UNCLASSIFIED",
                    "is_bank": int(is_bank),
                    "has_classified_sector": int(has_sec),
                    "period_end_date": p["period_end_date"],
                    "effective_pub_date": p["effective_pub_date"],
                    "pub_verified": int(p["pub_verified"]),
                    "has_complete_core": int(p["has_complete_core"]),
                    "eps_pkr": safe_float(p["effective_eps"]),
                    "revenue_growth_yoy": rev_g,
                    "net_income_growth_yoy": ni_g,
                    "eps_growth_yoy": eps_g,
                    "roe": roe,
                    "roa": roa,
                    "gross_margin": gm,
                    "operating_margin": om,
                    "net_margin": nm,
                    "debt_to_equity": de,
                    "current_ratio": cr,
                    "interest_coverage": ic,
                    "ocf_margin": ocf_margin,
                    "fcf_margin": fcf_margin,
                    "ocf_to_ni": ocf_to_ni,
                    "cash_payout_ratio": cash_payout,
                    "fcf_dividend_coverage": fcf_div_cov,
                    "_net_income": ni,
                    "_equity": eq,
                    "_fcf": fcf,
                    "_ocf": ocf,
                    "_div_paid": div_paid,
                    "_shares": p["shares"],
                    "_nxt_pub": nxt["effective_pub_date"] if nxt else None,
                    "_nxt_ni": nxt["net_income"] if nxt else np.nan,
                    "_nxt_eq": nxt["common_stock_equity"] if nxt else np.nan,
                    "_nxt_ocf": nxt["operating_cash_flow"] if nxt else np.nan,
                    "_nxt_fcf": nxt["effective_fcf"] if nxt else np.nan,
                    "_nxt_ebit": nxt["ebit"] if nxt else np.nan,
                    "_nxt_ie": nxt["interest_expense"] if nxt else np.nan,
                }
            )

    df = pd.DataFrame(base_records).sort_values(["effective_pub_date", "symbol"]).reset_index(drop=True)
    df["_pub_dt"] = pd.to_datetime(df["effective_pub_date"])

    # Backward as-of merge onto trading price snapshot <= effective_pub_date (point-in-time market valuation)
    df = pd.merge_asof(
        df.sort_values("_pub_dt"),
        px_df.rename(columns={"trading_date": "_px_dt", "close": "_px_close", "market_cap": "_px_mcap"})[
            ["symbol", "_px_dt", "_px_close", "_px_mcap"]
        ].sort_values("_px_dt"),
        left_on="_pub_dt",
        right_on="_px_dt",
        by="symbol",
        direction="backward",
        allow_exact_matches=True,
    )

    mcap_eff = np.where(
        pd.to_numeric(df["_px_mcap"], errors="coerce") > 0,
        pd.to_numeric(df["_px_mcap"], errors="coerce"),
        pd.to_numeric(df["_px_close"], errors="coerce") * pd.to_numeric(df["_shares"], errors="coerce"),
    )
    mcap_s = pd.Series(mcap_eff, index=df.index).replace(0.0, np.nan)
    ni_s = pd.to_numeric(df["_net_income"], errors="coerce")
    eq_s = pd.to_numeric(df["_equity"], errors="coerce")
    fcf_s = pd.to_numeric(df["_fcf"], errors="coerce")
    div_s = pd.to_numeric(df["_div_paid"], errors="coerce")

    df["pe_pit"] = np.where(ni_s > 0, mcap_s / ni_s, np.nan)
    df["pb_pit"] = np.where(eq_s > 0, mcap_s / eq_s, np.nan)
    df["earnings_yield_pit"] = ni_s / mcap_s
    df["fcf_yield_pit"] = fcf_s / mcap_s
    df["cf_dividend_yield_pit"] = div_s / mcap_s

    # Map HMM market regime on effective_pub_date (via latest trading date <= pub_date)
    df["hmm_regime_on_pub"] = pd.to_datetime(df["_px_dt"]).dt.date.map(hmm_lookup).fillna("UNKNOWN")

    # Compute causal sector-relative diffs strictly using peers disclosed <= row effective_pub_date within 370d period window
    for mcol in ["roe", "net_margin", "pe_pit", "pb_pit", "debt_to_equity"]:
        df[f"sector_{mcol.replace('_pit', '')}_diff"] = np.nan

    for idx_i, row in df.iterrows():
        if row["has_classified_sector"] != 1:
            continue
        peers = df[
            (df["sector"] == row["sector"])
            & (df["symbol"] != row["symbol"])
            & (df["effective_pub_date"] <= row["effective_pub_date"])
        ]
        if peers.empty:
            continue
        # Keep latest disclosure per peer within +/- 370d of target period_end_date
        peers = peers.sort_values("period_end_date").groupby("symbol").tail(1)
        pe_diff = (pd.to_datetime(peers["period_end_date"]) - pd.to_datetime(row["period_end_date"])).dt.days.abs()
        peers = peers[pe_diff <= 370]
        if len(peers) < 2:
            continue
        for mcol, outcol in [
            ("roe", "sector_roe_diff"),
            ("net_margin", "sector_net_margin_diff"),
            ("pe_pit", "sector_pe_diff"),
            ("pb_pit", "sector_pb_diff"),
            ("debt_to_equity", "sector_de_diff"),
        ]:
            pvals = pd.to_numeric(peers[mcol], errors="coerce").dropna()
            if len(pvals) >= 2 and pd.notna(row[mcol]):
                df.at[idx_i, outcol] = float(row[mcol] - pvals.median())

    # Define chronological splits cleanly matching chronological_splits.json
    def _map_split(d: Optional[date]) -> Optional[str]:
        if d is None or pd.isna(d):
            return None
        if d <= date(2024, 5, 20):
            return "FUND_TRAIN"
        if d <= date(2024, 6, 28):
            return "FUND_PURGE_TV"
        if d <= date(2025, 5, 20):
            return "FUND_VAL"
        if d <= date(2025, 6, 30):
            return "FUND_PURGE_VT"
        return "FUND_TEST"

    df["fund_split"] = df["effective_pub_date"].apply(_map_split)
    df["next_pub_split"] = df["_nxt_pub"].apply(_map_split)

    # Inter-temporal t -> t+1 non-circular health outcome for diagnostic feasibility test ONLY
    nxt_ni = pd.to_numeric(df["_nxt_ni"], errors="coerce")
    nxt_eq = pd.to_numeric(df["_nxt_eq"], errors="coerce")
    nxt_ocf = pd.to_numeric(df["_nxt_ocf"], errors="coerce")
    nxt_fcf = pd.to_numeric(df["_nxt_fcf"], errors="coerce")
    nxt_ebit = pd.to_numeric(df["_nxt_ebit"], errors="coerce")
    nxt_ie = pd.to_numeric(df["_nxt_ie"], errors="coerce").abs()
    nxt_roe = np.where(nxt_eq > 0, nxt_ni / nxt_eq, np.nan)
    nxt_ic = np.where((df["is_bank"] == 0) & (nxt_ie > 0), nxt_ebit / nxt_ie, np.nan)

    has_next = df["_nxt_pub"].notna() & nxt_ni.notna()
    is_weak = has_next & (
        (nxt_ni <= 0)
        | (nxt_ocf < 0)
        | (pd.notna(nxt_ic) & (nxt_ic < 1.25))
        | ((df["roe"] > 0.05) & pd.notna(nxt_roe) & (nxt_roe < df["roe"] * 0.50))
    )
    is_strong = has_next & (~is_weak) & (nxt_ni > df["_net_income"]) & (nxt_roe >= 0.14) & (nxt_ocf > 0) & (nxt_fcf > 0)
    df["diag_next_health_cls"] = np.where(~has_next, -1, np.where(is_weak, 0, np.where(is_strong, 2, 1)))

    audit_counts = {
        "total_unique_disclosures": int(len(df)),
        "total_companies": int(df["symbol"].nunique()),
        "banks_count": int(df.loc[df["is_bank"] == 1, "symbol"].nunique()),
        "unclassified_sector_firms": int(df.loc[df["has_classified_sector"] == 0, "symbol"].nunique()),
        "inactive_delisted_firms": int(conn.execute(text("""
            SELECT COUNT(DISTINCT cf.symbol) FROM company_financials cf
            JOIN companies c ON c.symbol = cf.symbol
            WHERE cf.statement_type IN ('INCOME_STATEMENT', 'BALANCE_SHEET', 'CASH_FLOW') AND c.is_active = FALSE
        """)).scalar() or 0),
        "external_credit_rating_labels": 0,
        "missingness_pct": {col: round(float(df[col].isna().mean() * 100), 1) for col in FUND_FEATURE_COLS},
    }

    return df, audit_counts


def run_fundamental_ml_audit(
    conn: Connection,
    out_dir: str | Path = DEFAULT_FUND_ARTIFACTS_DIR,
    reports_dir: str | Path = DEFAULT_FUND_REPORTS_DIR,
) -> dict[str, Any]:
    """
    Audit Fundamental ML labeling readiness, run non-deployed CatBoost/LGBM/XGB diagnostic
    benchmark on inter-temporal (t -> t+1) durability outcomes to expose sample limits,
    and write honest metadata/schema files into `artifacts/fundamental/` WITHOUT exporting
    a misleading `fundamental_model.pkl`.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    rep_path = Path(reports_dir)
    rep_path.mkdir(parents=True, exist_ok=True)

    df, audit = build_fundamental_disclosures_dataset(conn)
    feat_parquet = rep_path / "fundamental_disclosures_features.parquet"
    df.to_parquet(feat_parquet, index=False)

    tr_df = df[(df["diag_next_health_cls"] >= 0) & (df["fund_split"] == "FUND_TRAIN") & (df["next_pub_split"] == "FUND_TRAIN")].copy()
    va_df = df[(df["diag_next_health_cls"] >= 0) & (df["fund_split"] == "FUND_TRAIN") & (df["next_pub_split"] == "FUND_VAL")].copy()
    vt_df = df[(df["diag_next_health_cls"] >= 0) & (df["fund_split"] == "FUND_VAL") & (df["next_pub_split"] == "FUND_TEST")].copy()
    te_pure_df = df[(df["diag_next_health_cls"] >= 0) & (df["fund_split"] == "FUND_TEST") & (df["next_pub_split"] == "FUND_TEST")].copy()

    def _cls_counts(sub: pd.DataFrame) -> dict[str, int]:
        y = sub["diag_next_health_cls"]
        return {FUND_CLASSES[i]: int((y == i).sum()) for i in range(3)}

    diag_benchmark: dict[str, Any] = {}
    if len(tr_df) >= 50 and len(va_df) >= 20 and len(vt_df) >= 20:
        import catboost as cb_pkg
        import lightgbm as lgb_pkg
        import xgboost as xgb_pkg
        from catboost import CatBoostClassifier
        from lightgbm import LGBMClassifier
        from xgboost import XGBClassifier

        x_tr = tr_df[FUND_FEATURE_COLS].to_numpy(dtype=np.float32)
        y_tr = tr_df["diag_next_health_cls"].to_numpy(dtype=np.int32)
        x_vt = vt_df[FUND_FEATURE_COLS].to_numpy(dtype=np.float32)
        y_vt = vt_df["diag_next_health_cls"].to_numpy(dtype=np.int32)

        cb = CatBoostClassifier(
            iterations=250, depth=4, learning_rate=0.04, l2_leaf_reg=6.0, random_seed=42, verbose=0, allow_writing_files=False
        )
        cb.fit(np.where(np.isnan(x_tr), -999.0, x_tr), y_tr)

        lgb = LGBMClassifier(
            objective="multiclass", num_class=3, n_estimators=150, learning_rate=0.04,
            num_leaves=15, min_child_samples=15, random_state=42, verbose=-1
        )
        lgb.fit(x_tr, y_tr)

        xgb = XGBClassifier(
            objective="multi:softprob", num_class=3, eval_metric="mlogloss",
            n_estimators=150, max_depth=3, learning_rate=0.04, min_child_weight=10, random_state=42
        )
        xgb.fit(x_tr, y_tr)

        maj_cls = int(pd.Series(y_tr).mode().iloc[0])
        maj_vt = np.full(len(y_vt), maj_cls, dtype=np.int32)
        rule_vt = np.where(
            (vt_df["roe"].fillna(0) >= 0.15) & (vt_df["fcf_margin"].fillna(0) > 0) & (vt_df["debt_to_equity"].fillna(1) < 1.0),
            2,
            np.where((vt_df["roe"].fillna(1) < 0.05) | (vt_df["ocf_to_ni"].fillna(1) < 0.5), 0, 1),
        ).astype(np.int32)

        cb_x_vt = np.where(np.isnan(x_vt), -999.0, x_vt)
        for name, m, x_eval in [("catboost_diag", cb, cb_x_vt), ("lightgbm_diag", lgb, x_vt), ("xgboost_diag", xgb, x_vt)]:
            p_vt = m.predict_proba(x_eval)
            pred_vt = np.argmax(p_vt, axis=1)
            diag_benchmark[name] = {
                "val_test_metrics": evaluate_multiclass_predictions(y_vt, pred_vt, p_vt, FUND_CLASSES),
                "by_regime": evaluate_by_regime(y_vt, pred_vt, p_vt, vt_df["hmm_regime_on_pub"], FUND_CLASSES),
            }
        diag_benchmark["majority_baseline"] = evaluate_multiclass_predictions(y_vt, maj_vt, None, FUND_CLASSES)
        diag_benchmark["simple_rule_baseline"] = evaluate_multiclass_predictions(y_vt, rule_vt, None, FUND_CLASSES)

    blocking_reasons = [
        f"Zero independent historical ground-truth financial health labels (credit ratings={audit['external_credit_rating_labels']}, delisted/defaulted IFRS firms={audit['inactive_delisted_firms']}).",
        "Using contemporaneous accounting ratios to score Strong/Moderate/Weak would merely clone FundamentalAnalysisEngine deterministically (circular tautology).",
        f"Non-circular inter-temporal (t -> t+1) sample depth is severely underpowered: only {len(tr_df)} strictly in-train transitions (1 fiscal cycle FY22->FY23) and only {len(te_pure_df)} transitions fully inside FUND_TEST (min_test_class={min(_cls_counts(te_pure_df).values())}).",
        f"Structural feature gaps: {audit['unclassified_sector_firms']}/{audit['total_companies']} (43.6%) firms lack PSX sector tags for sector-relative metrics; {audit['missingness_pct']['current_ratio']}% missing current_ratio and {audit['missingness_pct']['interest_coverage']}% missing interest_coverage.",
        "100% survivorship bias among all 140 audited IFRS companies (zero inactive/failed historical companies in company_financials).",
    ]

    features_schema = sanitize_for_json(
        {
            "model_name": "PSXpert Fundamental Health ML Classifier (Blocked — Awaiting Labels)",
            "version": FUNDAMENTAL_ML_VERSION,
            "feature_count": len(FUND_FEATURE_COLS),
            "feature_cols": FUND_FEATURE_COLS,
            "classes": {str(i): FUND_CLASSES[i] for i in range(3)},
            "observed_missingness_pct": audit["missingness_pct"],
        }
    )
    feat_json_path = out_path / "fundamental_features.json"
    feat_json_path.write_text(json.dumps(features_schema, indent=2), encoding="utf-8")

    assessed_at = datetime.now(timezone.utc).isoformat()
    report = sanitize_for_json(
        {
            "model_name": "PSXpert Fundamental Health ML Classifier",
            "algorithm": None,
            "candidate_models_benchmarked_diagnostic_only": ["catboost", "lightgbm", "xgboost"],
            "module_version": FUNDAMENTAL_ML_VERSION,
            "version": FUNDAMENTAL_ML_VERSION,
            "assessed_at": assessed_at,
            "trained_at": None,
            "training_status": "BLOCKED_INSUFFICIENT_RELIABLE_LABELS",
            "model_exported": False,
            "model_deployed": False,
            "feature_names": FUND_FEATURE_COLS,
            "audit_summary": audit,
            "split_transition_counts": {
                "train_strict_within_fund_train": {"count": int(len(tr_df)), "classes": _cls_counts(tr_df)},
                "val_train_to_val": {"count": int(len(va_df)), "classes": _cls_counts(va_df)},
                "val_to_test_transitions": {"count": int(len(vt_df)), "classes": _cls_counts(vt_df)},
                "strict_within_fund_test": {"count": int(len(te_pure_df)), "classes": _cls_counts(te_pure_df)},
            },
            "blocking_reasons": blocking_reasons,
            "diagnostic_only_not_deployed_benchmark": diag_benchmark,
            "target_definition": PROPOSED_FUNDAMENTAL_TARGET_SPEC,
            "proposed_target_definition": PROPOSED_FUNDAMENTAL_TARGET_SPEC,
            "python_and_library_versions": {
                "python": platform.python_version(),
                "joblib": joblib.__version__,
                "scikit_learn": sklearn.__version__,
            },
            "artifact_files": {
                "model_pkl": None,
                "preprocessor_pkl": None,
                "features_json": str(feat_json_path),
                "metadata_json": str(out_path / "fundamental_metadata.json"),
                "disclosures_dataset": str(feat_parquet),
            },
        }
    )
    (out_path / "fundamental_metadata.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (rep_path / "fundamental_ml_readiness_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


class FundamentalMLAdvisor:
    """Loads Fundamental ML readiness/metadata (or approved `.pkl` if ever trained) cleanly without fake outputs."""

    def __init__(self, model_dir: str | Path = DEFAULT_FUND_ARTIFACTS_DIR, reports_dir: str | Path = DEFAULT_FUND_REPORTS_DIR) -> None:
        self.model_dir = Path(model_dir)
        self.reports_dir = Path(reports_dir)
        self._report: Optional[dict[str, Any]] = None
        self._model: Any = None
        self._preprocessor: Any = None
        self._features_schema: Optional[dict[str, Any]] = None
        self._load_error: Optional[str] = None

    def is_model_artifact_present(self) -> bool:
        return (self.model_dir / "fundamental_model.pkl").exists()

    def preload(self) -> bool:
        """Attempt startup load cleanly; returns True only if a valid trained fundamental_model.pkl loaded."""
        self._load_error = None
        self._report = None
        try:
            _ = self.get_readiness_report(strict=True)
        except Exception as exc:
            self._load_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Fundamental metadata read issue (%s): %s", self.model_dir, self._load_error)

        feat_path = self.model_dir / "fundamental_features.json"
        if feat_path.exists():
            try:
                self._features_schema = json.loads(feat_path.read_text(encoding="utf-8"))
            except Exception as exc:
                self._load_error = f"{type(exc).__name__}: {exc}"

        mdl_path = self.model_dir / "fundamental_model.pkl"
        if not mdl_path.exists():
            return False
        try:
            self._model = joblib.load(mdl_path)
            pre_path = self.model_dir / "fundamental_preprocessor.pkl"
            if pre_path.exists():
                self._preprocessor = joblib.load(pre_path)
            return hasattr(self._model, "predict_proba")
        except Exception as exc:
            self._model = None
            self._preprocessor = None
            self._load_error = f"{type(exc).__name__}: {exc}"
            return False

    def get_readiness_report(self, strict: bool = False) -> dict[str, Any]:
        if self._report is not None:
            return self._report
        for cand in (
            self.model_dir / "fundamental_metadata.json",
            self.model_dir / "fundamental_ml_readiness_report.json",
            self.reports_dir / "fundamental_ml_readiness_report.json",
        ):
            if cand.exists():
                try:
                    self._report = json.loads(cand.read_text(encoding="utf-8"))
                    return self._report
                except Exception as exc:
                    self._load_error = f"{type(exc).__name__}: {exc}"
                    if strict:
                        raise
                    return {
                        "module_version": FUNDAMENTAL_ML_VERSION,
                        "training_status": "CORRUPT_METADATA",
                        "model_deployed": False,
                        "blocking_reasons": [f"Corrupt metadata JSON at {cand}: {exc}"],
                    }
        return {
            "module_version": FUNDAMENTAL_ML_VERSION,
            "training_status": "BLOCKED_INSUFFICIENT_RELIABLE_LABELS",
            "model_deployed": False,
            "blocking_reasons": ["Readiness report not generated yet; run train_ml_models.py."],
        }

    def get_status_summary(self) -> dict[str, Any]:
        rep = self.get_readiness_report()
        exists = self.is_model_artifact_present()
        loaded = exists and (self._model is not None)
        if not exists:
            return sanitize_for_json(
                {
                    "status": rep.get("training_status", "BLOCKED_INSUFFICIENT_RELIABLE_LABELS"),
                    "artifact_exists": False,
                    "loaded_successfully": False,
                    "ready_for_inference": False,
                    "model_type": None,
                    "version": rep.get("version", FUNDAMENTAL_ML_VERSION),
                    "trained_at": None,
                    "feature_count": len(FUND_FEATURE_COLS),
                    "classes": FUND_CLASSES,
                    "blocking_reasons": rep.get("blocking_reasons", []),
                    "error": self._load_error or "fundamental_model.pkl intentionally not exported (reliable labels unavailable).",
                }
            )
        if not loaded:
            return sanitize_for_json(
                {
                    "status": "CORRUPT_OR_INVALID_ARTIFACT",
                    "artifact_exists": True,
                    "loaded_successfully": False,
                    "ready_for_inference": False,
                    "model_type": rep.get("algorithm"),
                    "version": rep.get("version", FUNDAMENTAL_ML_VERSION),
                    "trained_at": rep.get("trained_at"),
                    "error": self._load_error or "Artifact failed loading.",
                }
            )
        return sanitize_for_json(
            {
                "status": "READY",
                "artifact_exists": True,
                "loaded_successfully": True,
                "ready_for_inference": True,
                "model_type": rep.get("algorithm"),
                "version": rep.get("version", FUNDAMENTAL_ML_VERSION),
                "trained_at": rep.get("trained_at"),
                "feature_count": len(FUND_FEATURE_COLS),
                "classes": FUND_CLASSES,
                "error": None,
            }
        )

    def assess_symbol(
        self,
        rule_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Return honest blocked ML status, feature completeness, and rule-derived strengths/weaknesses without fake predictions."""
        rep = self.get_readiness_report()
        prof = rule_result.get("profitability") or {}
        val = rule_result.get("valuation") or {}
        hlth = rule_result.get("financial_health") or {}
        cf = rule_result.get("cash_flow_analysis") or {}
        gr = rule_result.get("growth") or {}
        sec = rule_result.get("sector_comparison") or {}

        key_metrics = {
            "eps_pkr": prof.get("eps_pkr"),
            "roe_pct": prof.get("roe_pct"),
            "roa_pct": prof.get("roa_pct"),
            "net_margin_pct": prof.get("net_margin_pct"),
            "operating_margin_pct": prof.get("operating_margin_pct"),
            "pe_ratio": val.get("pe_ratio"),
            "pb_ratio": val.get("pb_ratio"),
            "dividend_yield_pct": val.get("dividend_yield_pct"),
            "debt_to_equity": hlth.get("debt_to_equity"),
            "current_ratio": hlth.get("current_ratio"),
            "interest_coverage_ratio": hlth.get("interest_coverage_ratio"),
            "revenue_growth_yoy_pct": gr.get("revenue_growth_yoy_pct"),
            "net_income_growth_yoy_pct": gr.get("net_income_growth_yoy_pct"),
            "operating_cash_flow_pkr": cf.get("operating_cash_flow_pkr"),
            "free_cash_flow_pkr": cf.get("free_cash_flow_pkr"),
            "sector_peers_comparable": sec.get("comparable_peers_count"),
        }
        present_cnt = sum(1 for v in key_metrics.values() if v is not None)

        return sanitize_for_json(
            {
                "symbol": rule_result.get("symbol"),
                "as_of_date": rule_result.get("as_of_date"),
                "status": rep.get("training_status", "BLOCKED_INSUFFICIENT_RELIABLE_LABELS"),
                "model_available": False,
                "model_version": rep.get("module_version", FUNDAMENTAL_ML_VERSION),
                "trained_at": None,
                "predicted_health_category": None,
                "probabilities": None,
                "reason": (
                    "Fundamental ML classification model was intentionally NOT deployed because PSXpert lacks independent "
                    "historical financial-health ground-truth labels and has only 142 non-overlapping inter-temporal train disclosures "
                    "(24 test transitions) across 100% surviving firms. Reliable supervised training would require external credit ratings / "
                    "multi-year failure outcomes."
                ),
                "blocking_reasons": rep.get("blocking_reasons", []),
                "proposed_target_definition": rep.get("proposed_target_definition"),
                "available_metrics_snapshot": key_metrics,
                "feature_completeness": f"{present_cnt}/{len(key_metrics)}",
                "financial_strengths": rule_result.get("strengths", []),
                "financial_weaknesses": rule_result.get("weaknesses", []),
            }
        )

