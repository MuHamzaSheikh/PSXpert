"""
PSXpert - Master News Sentiment Processing & Storage Pipeline
Orchestrates:
1. Retrieval of raw news articles from database
2. Text cleaning, deduplication, and language detection
3. Symbol matching & sector classification
4. Sentiment analysis (Lexicon Baseline + FinBERT Transformer)
5. Target-Specific Aspect Sentiment Analysis (ABSA) for multi-company articles
6. Persistence of structured scores and entities into PostgreSQL
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional

import pandas as pd
from sqlalchemy import text
from src.database.connection import get_engine, is_postgres
from src.sentiment.cleaner import preprocess_article
from src.sentiment.entity_matcher import EntityMatcher
from src.sentiment.lexicon_baseline import LexiconFinancialAnalyzer
from src.sentiment.finbert_analyzer import FinBERTAnalyzer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SentimentPipeline")


class NewsSentimentPipeline:
    def __init__(self, use_finbert: bool = True):
        self.engine = get_engine()
        self.is_pg = is_postgres()
        self.matcher = EntityMatcher()
        self.baseline_analyzer = LexiconFinancialAnalyzer()
        self.use_finbert = use_finbert

        if self.use_finbert:
            logger.info("Initializing FinBERT Transformer model...")
            self.finbert_analyzer = FinBERTAnalyzer()
            logger.info("FinBERT initialized.")
        else:
            self.finbert_analyzer = None

    def process_all_articles(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Runs the complete sentiment pipeline across all news articles in the database.
        Saves scores and entities with idempotent deduplication.
        """
        logger.info(f"Starting sentiment pipeline on database: {'PostgreSQL' if self.is_pg else 'SQLite'}...")

        # 1. Fetch articles from database
        with self.engine.connect() as conn:
            sql = "SELECT id, published_at, publisher, headline, article_text FROM news_articles"
            if limit:
                sql += f" LIMIT {limit}"
            df_articles = pd.read_sql(text(sql), conn)

        total_articles = len(df_articles)
        logger.info(f"Retrieved {total_articles} articles for processing.")

        if total_articles == 0:
            return {"status": "No articles found"}

        start_time = time.time()
        entities_to_insert = []
        sentiment_records_to_insert = []

        seen_entities = set()

        for idx, row in df_articles.iterrows():
            article_id = int(row["id"])
            headline = str(row["headline"] or "")
            body = str(row["article_text"] or "")
            pub_time = row["published_at"]

            # 2. Text Preprocessing & Language Detection
            preprocessed = preprocess_article(headline, body)
            full_text = preprocessed["full_text"]
            lang = preprocessed["language"]

            # 3. Entity & Sector Matching
            symbols = self.matcher.extract_companies(full_text)
            sectors = self.matcher.extract_sectors(full_text)

            # Store matched entities (Article-to-Company and Article-to-Sector links)
            for sym in symbols:
                key = (article_id, "COMPANY", sym)
                if key not in seen_entities:
                    seen_entities.add(key)
                    entities_to_insert.append({
                        "article_id": article_id,
                        "entity_type": "COMPANY",
                        "entity_value": sym,
                        "confidence_score": 1.0
                    })

            for sec in sectors:
                key = (article_id, "SECTOR", sec)
                if key not in seen_entities:
                    seen_entities.add(key)
                    entities_to_insert.append({
                        "article_id": article_id,
                        "entity_type": "SECTOR",
                        "entity_value": sec,
                        "confidence_score": 0.95
                    })

            # Extract Target-Specific contexts for each company
            entity_contexts = self.matcher.extract_entity_contexts(full_text, symbols)

            # 4. Lexicon Baseline Model Inference
            baseline_overall = self.baseline_analyzer.analyze(full_text)
            baseline_targets = {}
            for sym, ctx in entity_contexts.items():
                baseline_targets[sym] = self.baseline_analyzer.analyze(ctx)

            b_meta = {
                "language": lang,
                "symbols_mentioned": symbols,
                "sectors_mentioned": sectors,
                "target_specific_sentiments": {
                    s: {
                        "label": baseline_targets[s]["sentiment_label"],
                        "score": baseline_targets[s]["sentiment_score"]
                    } for s in baseline_targets
                }
            }

            sentiment_records_to_insert.append({
                "article_id": article_id,
                "model_name": "lexicon_baseline",
                "sentiment_score": baseline_overall["sentiment_score"],
                "sentiment_label": baseline_overall["sentiment_label"],
                "confidence": baseline_overall["confidence"],
                "positive_score": baseline_overall["positive_score"],
                "negative_score": baseline_overall["negative_score"],
                "neutral_score": baseline_overall["neutral_score"],
                "evaluation_metadata": json.dumps(b_meta)
            })

            # 5. FinBERT Transformer Model Inference
            if self.finbert_analyzer is not None:
                finbert_res = self.finbert_analyzer.analyze_article_with_targets(full_text, entity_contexts)
                f_meta = {
                    "language": lang,
                    "symbols_mentioned": symbols,
                    "sectors_mentioned": sectors,
                    "target_specific_sentiments": finbert_res["target_sentiments"]
                }

                sentiment_records_to_insert.append({
                    "article_id": article_id,
                    "model_name": "finbert",
                    "sentiment_score": finbert_res["sentiment_score"],
                    "sentiment_label": finbert_res["sentiment_label"],
                    "confidence": finbert_res["confidence"],
                    "positive_score": finbert_res["positive_score"],
                    "negative_score": finbert_res["negative_score"],
                    "neutral_score": finbert_res["neutral_score"],
                    "evaluation_metadata": json.dumps(f_meta)
                })

            if (idx + 1) % 50 == 0 or (idx + 1) == total_articles:
                logger.info(f"Processed [{idx + 1}/{total_articles}] articles...")

        # 6. Database Storage with Idempotent Upsert
        logger.info(f"Persisting {len(entities_to_insert)} entity links and {len(sentiment_records_to_insert)} sentiment evaluations...")

        with self.engine.begin() as conn:
            # Insert Entities
            if entities_to_insert:
                if self.is_pg:
                    stmt_ent = text("""
                        INSERT INTO news_entities (article_id, entity_type, entity_value, confidence_score)
                        VALUES (:article_id, :entity_type, :entity_value, :confidence_score)
                        ON CONFLICT (article_id, entity_type, entity_value) DO NOTHING;
                    """)
                else:
                    stmt_ent = text("""
                        INSERT OR IGNORE INTO news_entities (article_id, entity_type, entity_value, confidence_score)
                        VALUES (:article_id, :entity_type, :entity_value, :confidence_score);
                    """)
                conn.execute(stmt_ent, entities_to_insert)

            # Insert Sentiment Scores
            if sentiment_records_to_insert:
                if self.is_pg:
                    stmt_sent = text("""
                        INSERT INTO news_sentiment (
                            article_id, model_name, sentiment_score, sentiment_label,
                            confidence, positive_score, negative_score, neutral_score, evaluation_metadata
                        )
                        VALUES (
                            :article_id, :model_name, :sentiment_score, :sentiment_label,
                            :confidence, :positive_score, :negative_score, :neutral_score, :evaluation_metadata
                        )
                        ON CONFLICT (article_id, model_name) DO UPDATE SET
                            sentiment_score = EXCLUDED.sentiment_score,
                            sentiment_label = EXCLUDED.sentiment_label,
                            confidence = EXCLUDED.confidence,
                            positive_score = EXCLUDED.positive_score,
                            negative_score = EXCLUDED.negative_score,
                            neutral_score = EXCLUDED.neutral_score,
                            evaluation_metadata = EXCLUDED.evaluation_metadata;
                    """)
                else:
                    stmt_sent = text("""
                        INSERT OR REPLACE INTO news_sentiment (
                            article_id, model_name, sentiment_score, sentiment_label,
                            confidence, positive_score, negative_score, neutral_score, evaluation_metadata
                        )
                        VALUES (
                            :article_id, :model_name, :sentiment_score, :sentiment_label,
                            :confidence, :positive_score, :negative_score, :neutral_score, :evaluation_metadata
                        );
                    """)
                conn.execute(stmt_sent, sentiment_records_to_insert)

        elapsed = time.time() - start_time
        logger.info(f"Pipeline completed successfully in {elapsed:.2f}s!")

        return {
            "articles_processed": total_articles,
            "entities_linked": len(entities_to_insert),
            "sentiment_evaluations": len(sentiment_records_to_insert),
            "elapsed_seconds": round(elapsed, 2)
        }
