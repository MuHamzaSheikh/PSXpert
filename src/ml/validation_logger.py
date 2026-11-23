"""Centralized Validation & Verification Logger for PSXpert ML Models.

Maintains an immutable timeline and structured JSON ledger in `logs/validation/`
recording every validation run, test suite execution, and model benchmark.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DEFAULT_LOG_DIR = Path("logs/validation")
RUNS_JSON_FILE = DEFAULT_LOG_DIR / "validation_runs.json"
TIMELINE_MD_FILE = DEFAULT_LOG_DIR / "VALIDATION_TIMELINE.md"


def record_validation_run(
    name: str,
    target: str,
    universe: str,
    splits: str,
    status: str,
    metrics: dict[str, Any],
    report_file: str,
    notes: Optional[str] = None,
    log_dir: Path = DEFAULT_LOG_DIR,
) -> dict[str, Any]:
    """
    Append a validation run record to `validation_runs.json` and `VALIDATION_TIMELINE.md`.

    Parameters
    ----------
    name : str
        Descriptive name of the validation run.
    target : str
        Prediction target or evaluation scope.
    universe : str
        Market universe (e.g. 'KSE-100', 'PSX Equities').
    splits : str
        Data splits evaluated (e.g. 'Fold 1-3 Walk-Forward', 'Untouched TEST').
    status : str
        Outcome status ('PASS', 'FAIL', 'VERIFIED', 'DIAGNOSED').
    metrics : dict
        Key performance indicators and verification metrics.
    report_file : str
        Relative path to the associated markdown/json report or test script.
    notes : str, optional
        Additional contextual findings or remarks.

    Returns
    -------
    dict
        The logged run record dictionary.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    json_path = log_dir / "validation_runs.json"
    timeline_path = log_dir / "VALIDATION_TIMELINE.md"

    # 1. Load or initialize JSON ledger
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            data = {"version": "1.0.0", "project": "PSXpert", "runs": []}
    else:
        data = {"version": "1.0.0", "project": "PSXpert", "runs": []}

    runs: list[dict[str, Any]] = data.get("runs", [])
    next_num = len(runs) + 1
    run_id = f"RUN-{next_num:02d}"
    now_utc = datetime.now(timezone.utc).isoformat()

    new_run = {
      "run_id": run_id,
      "name": name,
      "timestamp_utc": now_utc,
      "target": target,
      "universe": universe,
      "splits": splits,
      "status": status,
      "metrics": metrics,
      "report_file": report_file,
    }
    if notes:
        new_run["notes"] = notes

    runs.append(new_run)
    data["runs"] = runs
    data["total_runs_recorded"] = len(runs)
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # 2. Append markdown entry to VALIDATION_TIMELINE.md if file exists
    if timeline_path.exists():
        md_text = timeline_path.read_text(encoding="utf-8")
        entry = (
            f"\n---\n\n"
            f"### {run_id}: {name}\n"
            f"- **Timestamp (UTC)**: `{now_utc}`\n"
            f"- **Target / Scope**: {target}\n"
            f"- **Universe**: {universe} | **Splits**: {splits}\n"
            f"- **Status**: **`{status}`**\n"
            f"- **Key Metrics**: `{json.dumps(metrics)}`\n"
            f"- **Associated Artifact / Report**: `{report_file}`\n"
        )
        if notes:
            entry += f"- **Notes**: {notes}\n"
        timeline_path.write_text(md_text + entry, encoding="utf-8")

    return new_run
