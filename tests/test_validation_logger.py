"""Unit tests for Centralized Validation Logger."""

import json
import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ml.validation_logger import record_validation_run


def test_record_validation_run_creates_ledger(tmp_path: Path):
    """record_validation_run must cleanly initialize and append validation records."""
    log_dir = tmp_path / "logs" / "validation"
    
    # Run 1
    r1 = record_validation_run(
        name="Test Validation Run A",
        target="10d technical entry return",
        universe="KSE-100",
        splits="Fold 1",
        status="PASS",
        metrics={"f1_macro": 0.40, "accuracy": 0.42},
        report_file="reports/test_report.md",
        notes="First test run",
        log_dir=log_dir,
    )
    assert r1["run_id"] == "RUN-01"
    assert (log_dir / "validation_runs.json").exists()

    # Run 2
    r2 = record_validation_run(
        name="Test Validation Run B",
        target="126d fundamental ranking",
        universe="KSE-100",
        splits="Fold 2",
        status="VERIFIED",
        metrics={"ndcg": 0.58},
        report_file="reports/test_report_b.md",
        log_dir=log_dir,
    )
    assert r2["run_id"] == "RUN-02"

    data = json.loads((log_dir / "validation_runs.json").read_text(encoding="utf-8"))
    assert data["total_runs_recorded"] == 2
    assert len(data["runs"]) == 2
