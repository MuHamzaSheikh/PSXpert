"""
PSXpert - Financial News Sentiment Analysis Package
"""

from src.sentiment.cleaner import clean_text, detect_article_language, preprocess_article
from src.sentiment.entity_matcher import EntityMatcher, COMPANY_ALIASES, SECTOR_KEYWORDS
from src.sentiment.lexicon_baseline import LexiconFinancialAnalyzer
from src.sentiment.finbert_analyzer import FinBERTAnalyzer
from src.sentiment.benchmark_evaluator import BenchmarkEvaluator, GOLD_BENCHMARK_DATA
from src.sentiment.pipeline import NewsSentimentPipeline

__all__ = [
    "clean_text",
    "detect_article_language",
    "preprocess_article",
    "EntityMatcher",
    "COMPANY_ALIASES",
    "SECTOR_KEYWORDS",
    "LexiconFinancialAnalyzer",
    "FinBERTAnalyzer",
    "BenchmarkEvaluator",
    "GOLD_BENCHMARK_DATA",
    "NewsSentimentPipeline"
]
