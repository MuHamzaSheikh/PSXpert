"""
PSXpert - Master Database Ingestion Engine
High-throughput, idempotent, and retry-safe bulk ingestion pipeline.
Supports both PostgreSQL (ON CONFLICT DO UPDATE/NOTHING) and SQLite (INSERT OR REPLACE/IGNORE).
Logs every step and records data provenance in data_sources.
"""

import logging
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import pandas as pd
from sqlalchemy import text
from src.database.connection import get_engine, get_session, is_postgres
from src.database.models import (
    DataSource, Company, StockPrice, MarketIndex, NewsArticle,
    NewsEntity, CompanyFinancial, NewsSentiment, CorporateAnnouncement, CorporatePayout
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PSXpertIngestor")


class PSXDataIngestor:
    def __init__(self, processed_dir: str = "data/processed"):
        self.processed_dir = Path(processed_dir)
        self.engine = get_engine()
        self.is_pg = is_postgres()
        logger.info(f"Initialized PSXDataIngestor with backend: {'PostgreSQL' if self.is_pg else 'SQLite'}")

    def register_data_sources(self) -> Dict[str, int]:
        """Registers data provenance sources in data_sources table."""
        sources = [
            ("PSX_DPS", "EXCHANGE_PORTAL", "https://dps.psx.com.pk", "Official Direct PSX exchange portal for daily settlement, market statistics, and regulatory disclosures."),
            ("SARMAAYA_API", "REST_API", "https://beta-restapi.sarmaaya.pk", "Primary REST API for 2002-2026 historical OHLCV, balance sheets, and cash flow fundamentals."),
            ("DAWN_BUSINESS", "WEB_SCRAPE", "https://www.dawn.com/business", "Dawn Financial & Business news articles with automated NLP ticker detection."),
            ("BUSINESS_RECORDER", "WEB_SCRAPE", "https://www.brecorder.com", "Business Recorder Pakistan market news archive and breaking corporate reports.")
        ]
        source_map = {}
        session = get_session()
        try:
            for name, stype, url, notes in sources:
                existing = session.query(DataSource).filter_by(source_name=name).first()
                if not existing:
                    ds = DataSource(
                        source_name=name,
                        source_type=stype,
                        base_url=url,
                        retrieval_timestamp=datetime.utcnow(),
                        status="SUCCESS",
                        provenance_notes=notes
                    )
                    session.add(ds)
                    session.flush()
                    source_map[name] = ds.id
                else:
                    source_map[name] = existing.id
            session.commit()
            logger.info(f"Registered {len(source_map)} data sources.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error registering data sources: {e}")
            raise
        finally:
            session.close()
        return source_map

    def ingest_companies(self) -> int:
        """Ingests clean companies into companies table."""
        file_path = self.processed_dir / "companies_clean.csv"
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return 0

        df = pd.read_csv(file_path)
        logger.info(f"Ingesting {len(df)} companies...")
        
        with self.engine.begin() as conn:
            if self.is_pg:
                stmt = text("""
                    INSERT INTO companies (symbol, company_name, sector, sector_category, isin, is_shariah, is_kse100, is_active)
                    VALUES (:symbol, :company_name, :sector, :sector_category, :isin, :is_shariah, :is_kse100, :is_active)
                    ON CONFLICT (symbol) DO UPDATE SET
                        company_name = EXCLUDED.company_name,
                        sector = EXCLUDED.sector,
                        sector_category = EXCLUDED.sector_category,
                        isin = EXCLUDED.isin,
                        is_shariah = EXCLUDED.is_shariah,
                        updated_at = CURRENT_TIMESTAMP;
                """)
            else:
                stmt = text("""
                    INSERT OR REPLACE INTO companies (symbol, company_name, sector, sector_category, isin, is_shariah, is_kse100, is_active)
                    VALUES (:symbol, :company_name, :sector, :sector_category, :isin, :is_shariah, :is_kse100, :is_active);
                """)
            conn.execute(stmt, df.to_dict(orient="records"))
        logger.info(f"Successfully ingested {len(df)} companies.")
        return len(df)

    def ingest_market_indices(self, source_id: Optional[int] = None) -> int:
        """Ingests KSE-100 historical index records."""
        file_path = self.processed_dir / "market_indices_clean.csv"
        if not file_path.exists():
            return 0

        df = pd.read_csv(file_path)
        df["source_id"] = source_id
        logger.info(f"Ingesting {len(df):,} market index records...")

        with self.engine.begin() as conn:
            if self.is_pg:
                stmt = text("""
                    INSERT INTO market_indices (index_symbol, trading_date, open, high, low, close, volume, point_change, pct_change, source_id)
                    VALUES (:index_symbol, :trading_date, :open, :high, :low, :close, :volume, :point_change, :pct_change, :source_id)
                    ON CONFLICT (index_symbol, trading_date) DO UPDATE SET
                        close = EXCLUDED.close,
                        point_change = EXCLUDED.point_change,
                        pct_change = EXCLUDED.pct_change;
                """)
            else:
                stmt = text("""
                    INSERT OR REPLACE INTO market_indices (index_symbol, trading_date, open, high, low, close, volume, point_change, pct_change, source_id)
                    VALUES (:index_symbol, :trading_date, :open, :high, :low, :close, :volume, :point_change, :pct_change, :source_id);
                """)
            # Execute in batches
            batch_size = 2000
            for i in range(0, len(df), batch_size):
                chunk = df.iloc[i:i + batch_size].to_dict(orient="records")
                conn.execute(stmt, chunk)
        logger.info(f"Successfully ingested {len(df):,} market index records.")
        return len(df)

    def ingest_stock_prices(self, source_id: Optional[int] = None, batch_size: int = 10000) -> int:
        """
        Fast batch ingestion for 475k+ daily stock prices.
        Enforces unique constraint (symbol, trading_date) with safe idempotent retry.
        """
        file_path = self.processed_dir / "stock_prices_clean.csv"
        if not file_path.exists():
            return 0

        logger.info(f"Reading {file_path} for bulk ingestion...")
        df = pd.read_csv(file_path, low_memory=False)
        total = len(df)
        df["source_id"] = source_id
        
        # Replace NaN with None for database compatibility
        df = df.where(pd.notnull(df), None)

        logger.info(f"Ingesting {total:,} stock price records in batches of {batch_size:,}...")
        start_t = time.time()

        if self.is_pg:
            stmt = text("""
                INSERT INTO stock_prices (symbol, trading_date, open, high, low, close, volume, market_cap, source_id)
                VALUES (:symbol, :trading_date, :open, :high, :low, :close, :volume, :market_cap, :source_id)
                ON CONFLICT (symbol, trading_date) DO UPDATE SET
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    market_cap = EXCLUDED.market_cap;
            """)
        else:
            stmt = text("""
                INSERT OR REPLACE INTO stock_prices (symbol, trading_date, open, high, low, close, volume, market_cap, source_id)
                VALUES (:symbol, :trading_date, :open, :high, :low, :close, :volume, :market_cap, :source_id);
            """)

        with self.engine.begin() as conn:
            num_batches = math.ceil(total / batch_size)
            for b_idx in range(num_batches):
                chunk = df.iloc[b_idx * batch_size:(b_idx + 1) * batch_size].to_dict(orient="records")
                conn.execute(stmt, chunk)
                if (b_idx + 1) % 5 == 0 or (b_idx + 1) == num_batches:
                    curr_rows = min((b_idx + 1) * batch_size, total)
                    logger.info(f"Progress: [{curr_rows:,}/{total:,}] stock price records ingested ({curr_rows/total*100:.1f}%)")

        elapsed = time.time() - start_t
        logger.info(f"Successfully ingested {total:,} stock prices in {elapsed:.2f}s ({total/elapsed:,.0f} rows/s).")
        return total

    def ingest_news(self, source_map: Dict[str, int]) -> Tuple[int, int]:
        """Ingests news articles and news entities."""
        art_path = self.processed_dir / "news_articles_clean.csv"
        ent_path = self.processed_dir / "news_entities_clean.csv"
        if not art_path.exists() or not ent_path.exists():
            return 0, 0

        df_art = pd.read_csv(art_path)
        df_ent = pd.read_csv(ent_path)

        def map_source(publisher):
            if "Dawn" in str(publisher):
                return source_map.get("DAWN_BUSINESS")
            return source_map.get("BUSINESS_RECORDER")

        df_art["source_id"] = df_art["publisher"].apply(map_source)
        df_art = df_art.where(pd.notnull(df_art), None)
        df_ent = df_ent.where(pd.notnull(df_ent), None)

        logger.info(f"Ingesting {len(df_art)} news articles and {len(df_ent)} news entities...")
        with self.engine.begin() as conn:
            if self.is_pg:
                art_stmt = text("""
                    INSERT INTO news_articles (id, headline, summary, article_text, publisher, url, published_at, source_id)
                    VALUES (:article_id, :headline, :summary, :article_text, :publisher, :url, :published_at, :source_id)
                    ON CONFLICT (url) DO UPDATE SET
                        headline = EXCLUDED.headline,
                        summary = EXCLUDED.summary,
                        article_text = EXCLUDED.article_text;
                """)
                ent_stmt = text("""
                    INSERT INTO news_entities (article_id, entity_type, entity_value, confidence_score)
                    VALUES (:article_id, :entity_type, :entity_value, :confidence_score)
                    ON CONFLICT (article_id, entity_type, entity_value) DO NOTHING;
                """)
            else:
                art_stmt = text("""
                    INSERT OR REPLACE INTO news_articles (id, headline, summary, article_text, publisher, url, published_at, source_id)
                    VALUES (:article_id, :headline, :summary, :article_text, :publisher, :url, :published_at, :source_id);
                """)
                ent_stmt = text("""
                    INSERT OR IGNORE INTO news_entities (article_id, entity_type, entity_value, confidence_score)
                    VALUES (:article_id, :entity_type, :entity_value, :confidence_score);
                """)
            conn.execute(art_stmt, df_art.to_dict(orient="records"))
            conn.execute(ent_stmt, df_ent.to_dict(orient="records"))

        logger.info(f"Successfully ingested {len(df_art)} articles and {len(df_ent)} entities.")
        return len(df_art), len(df_ent)

    def ingest_company_financials(self, source_id: Optional[int] = None) -> int:
        """
        Ingests normalized company fundamentals.
        Stores publication_date alongside period_end_date.
        """
        file_path = self.processed_dir / "company_financials_clean.csv"
        if not file_path.exists():
            return 0

        df = pd.read_csv(file_path)
        df["source_id"] = source_id
        df = df.where(pd.notnull(df), None)
        total = len(df)
        logger.info(f"Ingesting {total:,} company financial metric records...")

        with self.engine.begin() as conn:
            if self.is_pg:
                stmt = text("""
                    INSERT INTO company_financials (
                        symbol, statement_type, fiscal_year, fiscal_period,
                        period_end_date, publication_date, metric_name, metric_value, unit, source_id
                    ) VALUES (
                        :symbol, :statement_type, :fiscal_year, :fiscal_period,
                        :period_end_date, :publication_date, :metric_name, :metric_value, :unit, :source_id
                    ) ON CONFLICT (symbol, statement_type, fiscal_year, fiscal_period, metric_name) DO UPDATE SET
                        metric_value = EXCLUDED.metric_value,
                        publication_date = EXCLUDED.publication_date;
                """)
            else:
                stmt = text("""
                    INSERT OR REPLACE INTO company_financials (
                        symbol, statement_type, fiscal_year, fiscal_period,
                        period_end_date, publication_date, metric_name, metric_value, unit, source_id
                    ) VALUES (
                        :symbol, :statement_type, :fiscal_year, :fiscal_period,
                        :period_end_date, :publication_date, :metric_name, :metric_value, :unit, :source_id
                    );
                """)
            batch_size = 5000
            for i in range(0, total, batch_size):
                chunk = df.iloc[i:i + batch_size].to_dict(orient="records")
                conn.execute(stmt, chunk)

        logger.info(f"Successfully ingested {total:,} financial records.")
        return total

    def ingest_sentiment_baseline(self) -> int:
        """
        Initializes news_sentiment baseline scores so model evaluation
        and sentiment joins are ready out of the box.
        """
        art_path = self.processed_dir / "news_articles_clean.csv"
        if not art_path.exists():
            return 0

        df_art = pd.read_csv(art_path)
        sentiment_rows = []
        positive_keywords = ["growth", "profit", "surges", "rallies", "dividend", "up", "gain", "boost", "record", "expansion", "bullish"]
        negative_keywords = ["fall", "drop", "loss", "decline", "inflation", "deficit", "down", "crisis", "slump", "bearish"]

        for _, r in df_art.iterrows():
            text_corpus = (str(r.get("headline", "")) + " " + str(r.get("summary", ""))).lower()
            pos_hits = sum(1 for w in positive_keywords if w in text_corpus)
            neg_hits = sum(1 for w in negative_keywords if w in text_corpus)
            
            score = 0.0
            if pos_hits > neg_hits:
                label = "POSITIVE"
                score = min(1.0, 0.25 * (pos_hits - neg_hits))
            elif neg_hits > pos_hits:
                label = "NEGATIVE"
                score = max(-1.0, -0.25 * (neg_hits - pos_hits))
            else:
                label = "NEUTRAL"
                score = 0.0

            sentiment_rows.append({
                "article_id": int(r["article_id"]),
                "model_name": "psx-lexicon-v1",
                "sentiment_score": round(score, 4),
                "sentiment_label": label,
                "confidence": 0.850,
                "positive_score": round(max(0.0, score), 4),
                "negative_score": round(max(0.0, -score), 4),
                "neutral_score": round(1.0 - abs(score), 4),
                "evaluation_metadata": '{"method": "lexicon_baseline", "engine": "PSXpert-NLP"}'
            })

        df_sent = pd.DataFrame(sentiment_rows)
        with self.engine.begin() as conn:
            if self.is_pg:
                stmt = text("""
                    INSERT INTO news_sentiment (
                        article_id, model_name, sentiment_score, sentiment_label,
                        confidence, positive_score, negative_score, neutral_score, evaluation_metadata
                    ) VALUES (
                        :article_id, :model_name, :sentiment_score, :sentiment_label,
                        :confidence, :positive_score, :negative_score, :neutral_score, :evaluation_metadata
                    ) ON CONFLICT (article_id, model_name) DO UPDATE SET
                        sentiment_score = EXCLUDED.sentiment_score,
                        sentiment_label = EXCLUDED.sentiment_label;
                """)
            else:
                stmt = text("""
                    INSERT OR REPLACE INTO news_sentiment (
                        article_id, model_name, sentiment_score, sentiment_label,
                        confidence, positive_score, negative_score, neutral_score, evaluation_metadata
                    ) VALUES (
                        :article_id, :model_name, :sentiment_score, :sentiment_label,
                        :confidence, :positive_score, :negative_score, :neutral_score, :evaluation_metadata
                    );
                """)
            conn.execute(stmt, df_sent.to_dict(orient="records"))
        logger.info(f"Ingested {len(df_sent)} news sentiment evaluations.")
        return len(df_sent)

    def ingest_announcements_and_payouts(self, source_map: Dict[str, int]) -> Tuple[int, int]:
        """Ingests corporate announcements and historical payouts."""
        ann_path = self.processed_dir / "corporate_announcements_clean.csv"
        pay_path = self.processed_dir / "corporate_payouts_clean.csv"

        ann_cnt, pay_cnt = 0, 0
        src_id = source_map.get("PSX_DPS")

        if ann_path.exists():
            df_ann = pd.read_csv(ann_path)
            df_ann["source_id"] = src_id
            df_ann = df_ann.where(pd.notnull(df_ann), None)
            ann_cnt = len(df_ann)
            logger.info(f"Ingesting {ann_cnt:,} corporate announcements...")
            with self.engine.begin() as conn:
                if self.is_pg:
                    stmt = text("""
                        INSERT INTO corporate_announcements (
                            symbol, posting_date, category, title, announcement_id, document_url, attachment_url, source_id
                        ) VALUES (
                            :symbol, :posting_date, :category, :title, :announcement_id, :document_url, :attachment_url, :source_id
                        ) ON CONFLICT (symbol, announcement_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            category = EXCLUDED.category;
                    """)
                else:
                    stmt = text("""
                        INSERT OR REPLACE INTO corporate_announcements (
                            symbol, posting_date, category, title, announcement_id, document_url, attachment_url, source_id
                        ) VALUES (
                            :symbol, :posting_date, :category, :title, :announcement_id, :document_url, :attachment_url, :source_id
                        );
                    """)
                batch_size = 5000
                for i in range(0, ann_cnt, batch_size):
                    chunk = df_ann.iloc[i:i + batch_size].to_dict(orient="records")
                    conn.execute(stmt, chunk)
            logger.info(f"Successfully ingested {ann_cnt:,} corporate announcements.")

        if pay_path.exists():
            df_pay = pd.read_csv(pay_path)
            df_pay["source_id"] = src_id
            df_pay = df_pay.where(pd.notnull(df_pay), None)
            pay_cnt = len(df_pay)
            logger.info(f"Ingesting {pay_cnt:,} corporate payouts...")
            with self.engine.begin() as conn:
                if self.is_pg:
                    stmt = text("""
                        INSERT INTO corporate_payouts (
                            symbol, announcement_date, fiscal_year, payout_type,
                            dividend_per_share, payout_percentage, face_value, source_id
                        ) VALUES (
                            :symbol, :announcement_date, :fiscal_year, :payout_type,
                            :dividend_per_share, :payout_percentage, :face_value, :source_id
                        );
                    """)
                else:
                    stmt = text("""
                        INSERT INTO corporate_payouts (
                            symbol, announcement_date, fiscal_year, payout_type,
                            dividend_per_share, payout_percentage, face_value, source_id
                        ) VALUES (
                            :symbol, :announcement_date, :fiscal_year, :payout_type,
                            :dividend_per_share, :payout_percentage, :face_value, :source_id
                        );
                    """)
                conn.execute(stmt, df_pay.to_dict(orient="records"))
            logger.info(f"Successfully ingested {pay_cnt:,} corporate payouts.")

        return ann_cnt, pay_cnt

    def run_all(self):
        """Executes full repeatable database ingestion pipeline."""
        start_time = time.time()
        logger.info("=" * 65)
        logger.info("STARTING MASTER PSXPERT DATABASE INGESTION PIPELINE")
        logger.info("=" * 65)

        source_map = self.register_data_sources()
        sarmaaya_id = source_map.get("SARMAAYA_API")
        dps_id = source_map.get("PSX_DPS")

        c_count = self.ingest_companies()
        i_count = self.ingest_market_indices(source_id=sarmaaya_id)
        p_count = self.ingest_stock_prices(source_id=sarmaaya_id)
        a_count, e_count = self.ingest_news(source_map=source_map)
        f_count = self.ingest_company_financials(source_id=sarmaaya_id)
        s_count = self.ingest_sentiment_baseline()
        ann_cnt, pay_cnt = self.ingest_announcements_and_payouts(source_map=source_map)

        elapsed = time.time() - start_time
        logger.info("=" * 65)
        logger.info(f"INGESTION PIPELINE COMPLETED IN {elapsed:.2f}s")
        logger.info(f"  Companies:               {c_count:>8,}")
        logger.info(f"  Market Indices:          {i_count:>8,}")
        logger.info(f"  Daily Stock Prices:      {p_count:>8,}")
        logger.info(f"  News Articles:           {a_count:>8,}")
        logger.info(f"  News Entities:           {e_count:>8,}")
        logger.info(f"  Company Financials:      {f_count:>8,}")
        logger.info(f"  News Sentiment Scores:   {s_count:>8,}")
        logger.info(f"  Corporate Announcements: {ann_cnt:>8,}")
        logger.info(f"  Corporate Payouts:       {pay_cnt:>8,}")
        logger.info("=" * 65)
