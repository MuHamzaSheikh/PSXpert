"""End-to-end training & feasibility audit runner for PSXpert Technical & Fundamental ML models."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.paths import (
    FUNDAMENTAL_ARTIFACTS_DIR,
    ML_REPORTS_DIR,
    PREDICTIVE_DATA_DIR,
    TECHNICAL_ARTIFACTS_DIR,
)
from src.database.connection import get_engine, is_postgres
from src.ml.fundamental_ml import run_fundamental_ml_audit
from src.ml.technical_ml import train_and_evaluate_technical_models

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("train_ml_models")


def main() -> int:
    logger.info("Connecting to database (is_postgres=%s)...", is_postgres())
    engine = get_engine()

    logger.info("=== 1. Training & Evaluating Technical Analysis ML Models (LightGBM / XGBoost / Random Forest) ===")
    tech_eval = train_and_evaluate_technical_models(
        parquet_path=PREDICTIVE_DATA_DIR / "daily_features.parquet",
        out_dir=TECHNICAL_ARTIFACTS_DIR,
        targets_path=PREDICTIVE_DATA_DIR / "daily_targets.parquet",
        reports_dir=ML_REPORTS_DIR,
    )

    meta = tech_eval["metadata"]
    sel = meta["selected_model_name"]
    logger.info("Selected Technical ML model (by VAL Macro-F1): %s (%s)", sel, meta["model_version"])
    for split_key in ("validation_results", "test_results"):
        logger.info("--- Technical %s ---", split_key)
        for mname, block in tech_eval[split_key].items():
            m = block["metrics"]
            logger.info(
                "  %-22s | Acc=%.4f | PrecM=%.4f | RecM=%.4f | F1M=%.4f | AUC=%s | ECE=%s | Brier=%s",
                mname,
                m["accuracy"],
                m["precision_macro"],
                m["recall_macro"],
                m["f1_macro"],
                m.get("roc_auc_ovr_macro"),
                m.get("ece"),
                m.get("brier_score"),
            )

    logger.info("=== 2. Running Fundamental Analysis ML Label Feasibility & Diagnostic Audit ===")
    with engine.connect() as conn:
        fund_audit = run_fundamental_ml_audit(
            conn,
            out_dir=FUNDAMENTAL_ARTIFACTS_DIR,
            reports_dir=ML_REPORTS_DIR,
        )

    logger.info("Fundamental ML status: %s (deployed=%s)", fund_audit["training_status"], fund_audit["model_deployed"])
    for r in fund_audit["blocking_reasons"]:
        logger.info("  Blocker: %s", r)

    diag = fund_audit.get("diagnostic_only_not_deployed_benchmark", {})
    if diag:
        logger.info("  Diagnostic-Only Unseen Val->Test transitions benchmark:")
        for k, v in diag.items():
            m = v["val_test_metrics"] if "val_test_metrics" in v else v
            logger.info("    %-22s | n=%d | Acc=%.4f | F1M=%.4f | AUC=%s", k, m["n_samples"], m["accuracy"], m["f1_macro"], m.get("roc_auc_ovr_macro"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

