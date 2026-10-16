"""
PSXpert - Financial Lexicon Sentiment Baseline
Combines VADER sentiment with Loughran-McDonald Financial Dictionary and
customized Pakistani local market financial terminology.
"""

from typing import Dict, Any
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Domain-specific financial lexicon tuning for Pakistani market (PSX, SBP, IMF, corporate results)
PAKISTANI_FINANCIAL_LEXICON = {
    # Bullish / Positive PSX Market & Corporate Terms (+1.5 to +3.5)
    "rally": 2.6,
    "rallies": 2.7,
    "bullish": 2.8,
    "surge": 2.4,
    "surges": 2.5,
    "surged": 2.5,
    "soar": 2.4,
    "soars": 2.5,
    "rebound": 2.2,
    "rebounds": 2.3,
    "dividend": 2.0,
    "payout": 2.1,
    "bonus issue": 2.3,
    "bonus shares": 2.4,
    "profit jumps": 3.0,
    "record profit": 3.2,
    "growth": 1.8,
    "inflow": 2.0,
    "inflows": 2.1,
    "upgrade": 2.2,
    "upgrades": 2.3,
    "expansion": 1.7,
    "discovery": 2.6,
    "oil discovery": 2.8,
    "gas discovery": 2.8,
    "rate cut": 2.5,
    "policy rate cut": 2.7,
    "monetary easing": 2.4,
    "imf agreement": 2.8,
    "imf tranche": 2.5,
    "imf approval": 2.7,
    "remittances rise": 2.3,
    "reserves increase": 2.4,
    "reserves surge": 2.7,
    "greenback drops": 1.8,
    "rupee strengthens": 2.2,
    "rupee gains": 2.1,
    "curb inflation": 1.9,
    "debt reprofiling": 1.8,
    "privatization": 1.8,

    # Bearish / Negative PSX Market & Corporate Terms (-1.5 to -3.5)
    "slump": -2.6,
    "slumps": -2.7,
    "plunge": -2.8,
    "plunges": -2.9,
    "selling pressure": -2.5,
    "bearish": -2.6,
    "selloff": -2.7,
    "sell-off": -2.7,
    "circular debt": -3.2,
    "loss": -2.4,
    "losses": -2.5,
    "loss widens": -3.0,
    "default": -3.5,
    "bankruptcy": -3.5,
    "rate hike": -2.4,
    "policy rate hike": -2.6,
    "monetary tightening": -2.2,
    "gas tariff hike": -2.7,
    "electricity tariff hike": -2.6,
    "power tariff hike": -2.6,
    "dumping duty": -2.1,
    "plant shutdown": -2.8,
    "curtailment": -2.5,
    "gas curtailment": -2.7,
    "penalty": -2.2,
    "deficit": -2.0,
    "fiscal deficit": -2.3,
    "trade deficit widens": -2.6,
    "devaluation": -2.6,
    "rupee plunges": -2.9,
    "rupee weakens": -2.3,
    "reserves drop": -2.5,
    "reserves deplete": -2.8,
    "downgrade": -2.4,
    "downgrades": -2.5,
    "political volatility": -2.3,
    "political unrest": -2.5,
    "imf talks stall": -2.8,
    "import curbs": -1.9,
    "anti-dumping duty": -2.0,
    "margin squeeze": -2.4,
}


class LexiconFinancialAnalyzer:
    """
    Baseline Lexicon model for financial news sentiment.
    Uses VADER engine augmented with Loughran-McDonald & Pakistani market lexicons.
    """
    def __init__(self):
        self.vader = SentimentIntensityAnalyzer()
        # Update VADER lexicon with custom financial weights
        self.vader.lexicon.update(PAKISTANI_FINANCIAL_LEXICON)

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Analyzes input text sentiment.
        Returns:
            - sentiment_label: 'POSITIVE', 'NEGATIVE', or 'NEUTRAL'
            - sentiment_score: normalized compound polarity in [-1.0, +1.0]
            - confidence: confidence score based on margin of compound polarity
            - probabilities: {'positive': float, 'negative': float, 'neutral': float}
        """
        if not text or not text.strip():
            return {
                "sentiment_label": "NEUTRAL",
                "sentiment_score": 0.0,
                "confidence": 0.5,
                "positive_score": 0.0,
                "negative_score": 0.0,
                "neutral_score": 1.0,
                "model_name": "lexicon_baseline"
            }

        scores = self.vader.polarity_scores(text)
        compound = scores["compound"]

        # Classification thresholds (standard financial NLP thresholds)
        if compound >= 0.05:
            label = "POSITIVE"
            confidence = min(1.0, abs(compound) + 0.2)
        elif compound <= -0.05:
            label = "NEGATIVE"
            confidence = min(1.0, abs(compound) + 0.2)
        else:
            label = "NEUTRAL"
            confidence = scores["neu"]

        return {
            "sentiment_label": label,
            "sentiment_score": round(compound, 4),
            "confidence": round(confidence, 4),
            "positive_score": round(scores["pos"], 4),
            "negative_score": round(scores["neg"], 4),
            "neutral_score": round(scores["neu"], 4),
            "model_name": "lexicon_baseline"
        }
