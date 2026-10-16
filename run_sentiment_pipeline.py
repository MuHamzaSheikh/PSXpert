#!/usr/bin/env python3
"""
PSXpert - Phase 3 News Sentiment Pipeline Runner
Processes news articles, matches entities & sectors, evaluates overall & target-specific sentiments,
and saves structured records into PostgreSQL.

Usage:
  python run_sentiment_pipeline.py              # Process all database articles
  python run_sentiment_pipeline.py --limit 50   # Process a subset of articles
  python run_sentiment_pipeline.py --baseline-only # Skip FinBERT (fast baseline only)
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.sentiment.pipeline import NewsSentimentPipeline

def main():
    limit = None
    use_finbert = True

    for i, arg in enumerate(sys.argv):
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
        elif arg == "--baseline-only":
            use_finbert = False

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
