from dataclasses import dataclass
from math import isfinite
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
TZ = "Asia/Karachi"
CLASSES = ("BEARISH", "SIDEWAYS", "BULLISH")
PRICE_BASIS = "unadjusted close; price return excluding dividends"
FEATURE_VERSION = 1


@dataclass(frozen=True)
class Settings:
    horizon: int = 20
    bearish: float = -3.0
    bullish: float = 3.0
    embargo_sessions: int = 5
    seed: int = 42
    max_filing_age_days: int = 550

    def __post_init__(self):
        if not (
            isfinite(self.bearish) and isfinite(self.bullish)
            and self.bearish < 0 < self.bullish and self.horizon == 20
            and self.embargo_sessions >= 0 and self.max_filing_age_days > 0
        ):
            raise ValueError("Invalid thresholds, horizon, embargo or filing age")
