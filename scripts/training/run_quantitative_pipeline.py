"""
Entry point to run the PSXpert Quantitative ML Research & Training Pipeline.
Usage:
    python scripts/training/run_quantitative_pipeline.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ml.pipeline.quantitative_pipeline import run_pipeline

if __name__ == "__main__":
    sys.exit(run_pipeline())
