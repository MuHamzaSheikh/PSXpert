#!/usr/bin/env python3
"""
PSXpert - Phase 3 News Sentiment Pipeline Runner
Processes news articles, matches entities & sectors, evaluates overall & target-specific sentiments,
and saves structured records into PostgreSQL.

Usage:
  python scripts/data/run_sentiment_pipeline.py                # Process all database articles
  python scripts/data/run_sentiment_pipeline.py --limit 50     # Process a subset of articles
  python scripts/data/run_sentiment_pipeline.py --baseline-only # Skip FinBERT (fast baseline only)
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.sentiment.pipeline import NewsSentimentPipeline


def main():
    parser = argparse.ArgumentParser(description="PSXpert Phase 3 News Sentiment Pipeline Runner")
    parser.add_argument("--limit", type=int, default=None, help="Process a subset of articles")
    parser.add_argument("--baseline-only", action="store_true", help="Skip FinBERT (fast baseline only)")
    args = parser.parse_args()

    limit = args.limit
    use_finbert = not args.baseline_only

    pipeline = NewsSentimentPipeline(use_finbert=use_finbert)
    res = pipeline.process_all_articles(limit=limit)

    print("\n" + "=" * 65)
    print("PSXPERT NEWS SENTIMENT PIPELINE EXECUTION COMPLETE")
    print("=" * 65)
    print(f"Articles Processed      : {res.get('articles_processed', 0)}")
    print(f"Entity Links Generated  : {res.get('entities_linked', 0)}")
    print(f"Sentiment Evaluations   : {res.get('sentiment_evaluations', 0)}")
    print(f"Total Processing Time   : {res.get('elapsed_seconds', 0)} seconds")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    main()
