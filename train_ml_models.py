"""
PSXpert - Root Training & Quantitative ML Pipeline Runner
Usage:
    python train_ml_models.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ml.pipeline.quantitative_pipeline import run_pipeline

if __name__ == "__main__":
    sys.exit(run_pipeline())
