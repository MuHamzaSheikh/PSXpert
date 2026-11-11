"""Platform-independent project root and directory path definitions."""

from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_DATA_DIR: Path = DATA_DIR / "raw"
PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
PREDICTIVE_DATA_DIR: Path = DATA_DIR / "predictive"

ARTIFACTS_DIR: Path = PROJECT_ROOT / "artifacts"
TECHNICAL_ARTIFACTS_DIR: Path = ARTIFACTS_DIR / "technical"
FUNDAMENTAL_ARTIFACTS_DIR: Path = ARTIFACTS_DIR / "fundamental"

REPORTS_DIR: Path = PROJECT_ROOT / "reports"
DATA_AUDIT_REPORTS_DIR: Path = REPORTS_DIR / "data_audit"
ANALYSIS_REPORTS_DIR: Path = REPORTS_DIR / "analysis"
ML_REPORTS_DIR: Path = REPORTS_DIR / "model_evaluation"
CHARTS_REPORTS_DIR: Path = REPORTS_DIR / "charts"

STATIC_DIR: Path = PROJECT_ROOT / "static"
ARCHIVE_DIR: Path = PROJECT_ROOT / "archive"

