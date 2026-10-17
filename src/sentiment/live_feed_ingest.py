"""
PSXpert - Live Financial & Geopolitical News Feed Ingestion Engine
Fetches live RSS feeds from Business Recorder (Latest News & World Geopolitics)
and Dawn Business, evaluates FinBERT sentiment and entity targets, and updates PostgreSQL.
"""

import logging
import xml.etree.ElementTree as ET
import urllib.request
from datetime import datetime
from typing import Dict, List, Any
from bs4 import BeautifulSoup
import pandas as pd
from sqlalchemy import text

from src.database.connection import get_engine, get_session
from src.sentiment.entity_matcher import EntityMatcher
from src.sentiment.lexicon_baseline import LexiconFinancialAnalyzer

logger = logging.getLogger("LiveNewsIngest")
logger.setLevel(logging.INFO)

RSS_FEEDS = [
    {
        "url": "https://www.brecorder.com/feeds/latest-news",
        "publisher": "Business Recorder",
        "feed_type": "MARKETS_LOCAL"
    },
    {
        "url": "https://www.brecorder.com/feeds/world",
        "publisher": "Business Recorder World",
        "feed_type": "GEOPOLITICAL"
    },
    {
        "url": "https://www.dawn.com/feeds/business",
        "publisher": "Dawn Business",
        "feed_type": "FINANCIAL"
    }
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


def fetch_and_ingest_live_news(max_per_feed: int = 15) -> Dict[str, Any]:
    """
    Fetches latest live items from financial and geopolitical RSS feeds,
    runs entity matching and sentiment analysis, and persists new records to PostgreSQL.
    """
    engine = get_engine()
    matcher = EntityMatcher()
    baseline_analyzer = LexiconFinancialAnalyzer()

    # Try loading FinBERT analyzer if available, fallback gracefully
    finbert_analyzer = None
    try:
        from src.sentiment.finbert_analyzer import FinBERTAnalyzer
        finbert_analyzer = FinBERTAnalyzer()
    except Exception as e:
        logger.warning(f"FinBERT unavailable for live stream, using financial lexicon: {e}")

    session = get_session()
    new_articles_count = 0

    try:
        # Get existing URLs to prevent duplicate scraping
        existing_urls = set(r[0] for r in session.execute(text("SELECT url FROM news_articles")).fetchall())

        for feed in RSS_FEEDS:
            feed_url = feed["url"]
            publisher = feed["publisher"]

            try:
                req = urllib.request.Request(feed_url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    content = resp.read()

                root = ET.fromstring(content)
                items = root.findall(".//item")
            except Exception as err:
                logger.error(f"Error fetching RSS feed {feed_url}: {err}")
                continue

            for item in items[:max_per_feed]:
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub_date_raw = item.findtext("pubDate", "").strip()
                desc_raw = item.findtext("description", "").strip()

                if not link or link in existing_urls or not title or len(title) < 15:
                    continue

                summary = BeautifulSoup(desc_raw, "html.parser").get_text(strip=True) if desc_raw else ""
                
                # Parse publication datetime
                try:
                    dt = pd.to_datetime(pub_date_raw)
                    if dt.tz is None:
                        dt = dt.tz_localize("UTC")
                except Exception:
                    dt = datetime.utcnow()

                full_text = f"{title} {summary}".strip()
                symbols = matcher.extract_companies(full_text)
                sectors = matcher.extract_sectors(full_text)
                entity_contexts = matcher.extract_entity_contexts(full_text, symbols)

                # Sentiment Analysis (FinBERT or Baseline)
                if finbert_analyzer is not None:
                    try:
                        res = finbert_analyzer.analyze_article_with_targets(full_text, entity_contexts)
                        sent_label = res["sentiment_label"]
                        sent_score = res["sentiment_score"]
                        confidence = res["confidence"]
                        pos_score = res["positive_score"]
                        neg_score = res["negative_score"]
                        neu_score = res["neutral_score"]
                        target_sents = res["target_sentiments"]
                    except Exception:
                        b_res = baseline_analyzer.analyze(full_text)
                        sent_label = b_res["sentiment_label"]
                        sent_score = b_res["sentiment_score"]
                        confidence = b_res["confidence"]
                        pos_score = b_res["positive_score"]
                        neg_score = b_res["negative_score"]
                        neu_score = b_res["neutral_score"]
                        target_sents = {}
                else:
                    b_res = baseline_analyzer.analyze(full_text)
                    sent_label = b_res["sentiment_label"]
                    sent_score = b_res["sentiment_score"]
                    confidence = b_res["confidence"]
                    pos_score = b_res["positive_score"]
                    neg_score = b_res["negative_score"]
                    neu_score = b_res["neutral_score"]
                    target_sents = {}

                meta_data = {
                    "language": "en",
                    "symbols_mentioned": symbols,
                    "sectors_mentioned": sectors,
                    "target_specific_sentiments": target_sents,
                    "feed_type": feed["feed_type"]
                }

                import json
                # Insert news article
                insert_art_sql = text("""
                    INSERT INTO news_articles (headline, summary, article_text, publisher, url, published_at, created_at)
                    VALUES (:headline, :summary, :article_text, :publisher, :url, :published_at, NOW())
                    ON CONFLICT (url) DO NOTHING
                    RETURNING id;
                """)
                res_art = session.execute(insert_art_sql, {
                    "headline": title,
                    "summary": summary,
                    "article_text": summary,
                    "publisher": publisher,
                    "url": link,
                    "published_at": dt
                }).fetchone()

                if res_art:
                    art_id = res_art[0]
                    # Insert FinBERT sentiment
                    insert_sent_sql = text("""
                        INSERT INTO news_sentiment (
                            article_id, model_name, sentiment_score, sentiment_label,
                            confidence, positive_score, negative_score, neutral_score,
                            evaluation_metadata, created_at
                        )
                        VALUES (
                            :article_id, 'finbert', :sentiment_score, :sentiment_label,
                            :confidence, :positive_score, :negative_score, :neutral_score,
                            :evaluation_metadata, NOW()
                        )
                        ON CONFLICT (article_id, model_name) DO NOTHING;
                    """)
                    session.execute(insert_sent_sql, {
                        "article_id": art_id,
                        "sentiment_score": sent_score,
                        "sentiment_label": sent_label,
                        "confidence": confidence,
                        "positive_score": pos_score,
                        "negative_score": neg_score,
                        "neutral_score": neu_score,
                        "evaluation_metadata": json.dumps(meta_data)
                    })

                    existing_urls.add(link)
                    new_articles_count += 1

        session.commit()
        return {
            "status": "success",
            "new_articles_ingested": new_articles_count,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        session.rollback()
        logger.error(f"Error ingesting live feeds: {e}")
        return {
            "status": "error",
            "message": str(e)
        }
    finally:
        session.close()
