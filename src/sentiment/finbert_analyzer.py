"""
PSXpert - FinBERT Financial Transformer Sentiment Analyzer
Utilizes pretrained ProsusAI/finbert transformer model for high-accuracy financial sentiment.
Supports Document-Level Sentiment and Target-Specific (Aspect-Based) Sentiment for individual stocks.
"""

from typing import Dict, List, Optional, Any
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL_NAME = "ProsusAI/finbert"
LABELS = ["positive", "negative", "neutral"]


class FinBERTAnalyzer:
    """
    Financial BERT Sentiment Classifier.
    Computes both overall article sentiment and target-specific sentiment
    for individual company symbols.
    """
    def __init__(self, device: Optional[str] = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        self.model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME).to(self.device)
        self.model.eval()

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """Classifies a single text string with FinBERT."""
        if not text or not text.strip():
            return {
                "sentiment_label": "NEUTRAL",
                "sentiment_score": 0.0,
                "confidence": 0.5,
                "positive_score": 0.0,
                "negative_score": 0.0,
                "neutral_score": 1.0,
                "model_name": "finbert"
            }

        inputs = self.tokenizer(
            text,
            truncation=True,
            max_length=512,
            padding=True,
            return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probs = torch.nn.functional.softmax(logits, dim=-1)[0].cpu().tolist()

        pos_prob = probs[0]
        neg_prob = probs[1]
        neu_prob = probs[2]

        # Normalized continuous score in [-1.0, +1.0]: positive - negative
        compound_score = pos_prob - neg_prob

        # Best class
        max_idx = probs.index(max(probs))
        label_map = ["POSITIVE", "NEGATIVE", "NEUTRAL"]
        sentiment_label = label_map[max_idx]
        confidence = probs[max_idx]

        return {
            "sentiment_label": sentiment_label,
            "sentiment_score": round(compound_score, 4),
            "confidence": round(confidence, 4),
            "positive_score": round(pos_prob, 4),
            "negative_score": round(neg_prob, 4),
            "neutral_score": round(neu_prob, 4),
            "model_name": "finbert"
        }

    def analyze_batch(self, texts: List[str], batch_size: int = 16) -> List[Dict[str, Any]]:
        """Fast batch inference for multiple texts."""
        results = []
        for i in range(0, len(texts), batch_size):
            chunk = texts[i:i + batch_size]
            inputs = self.tokenizer(
                chunk,
                truncation=True,
                max_length=512,
                padding=True,
                return_tensors="pt"
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = torch.nn.functional.softmax(outputs.logits, dim=-1).cpu().tolist()

            label_map = ["POSITIVE", "NEGATIVE", "NEUTRAL"]
            for p in probs:
                pos_prob, neg_prob, neu_prob = p[0], p[1], p[2]
                compound = pos_prob - neg_prob
                max_idx = p.index(max(p))
                results.append({
                    "sentiment_label": label_map[max_idx],
                    "sentiment_score": round(compound, 4),
                    "confidence": round(p[max_idx], 4),
                    "positive_score": round(pos_prob, 4),
                    "negative_score": round(neg_prob, 4),
                    "neutral_score": round(neu_prob, 4),
                    "model_name": "finbert"
                })
        return results

    def analyze_article_with_targets(self, full_text: str, entity_contexts: Dict[str, str]) -> Dict[str, Any]:
        """
        Analyzes both overall article sentiment and target-specific stock sentiments.
        Crucial requirement: Distinguishes between the general article sentiment and its
        impact on specific stocks when multiple companies are mentioned.
        """
        overall = self.analyze_text(full_text)

        target_sentiments = {}
        for sym, context_sent in entity_contexts.items():
            t_res = self.analyze_text(context_sent)
            target_sentiments[sym] = {
                "sentiment_label": t_res["sentiment_label"],
                "sentiment_score": t_res["sentiment_score"],
                "confidence": t_res["confidence"],
                "positive_score": t_res["positive_score"],
                "negative_score": t_res["negative_score"],
                "neutral_score": t_res["neutral_score"],
                "context_snippet": context_sent[:150]
            }

        overall["target_sentiments"] = target_sentiments
        return overall
