"""
PSXpert - Historical News Sentiment & Stock-Specific Impact Feature Generator
Processes historical financial news corpus (40,430 articles) into a clean,
daily stock-level sentiment and impact feature table aligned with official PSX trading days.

Anti-Leakage Guarantees:
- Strictly maps articles published <= 09:15 to current day session t.
- Maps articles published > 09:15 or on non-trading days/weekends to next valid trading day t+1.
- Exponential decay weighting for 7-day and 30-day sentiment windows.
"""

import csv
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.sentiment.stock_news_impact import StockNewsImpactEngine, COMPANY_ALIASES

NEWS_CSV = os.path.join("data", "news", "news data", "processed", "master_news_corpus_complete.csv")
CALENDAR_CSV = os.path.join("data", "cleaned", "kse100_calendar_clean.csv")
STOCKS_CSV = os.path.join("data", "cleaned", "kse100_stocks_historical_clean.csv")
OUTPUT_CSV = os.path.join("data", "cleaned", "daily_stock_news_sentiment.csv")

def load_trading_calendar(calendar_path):
    print("-> Loading official PSX trading calendar...")
    dates = []
    with open(calendar_path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            d = row.get("date", "").strip()
            if d:
                dates.append(d)
    dates.sort()
    print(f"   Loaded {len(dates)} trading sessions ({dates[0]} to {dates[-1]}).")
    return dates

def load_active_symbols(stocks_path):
    print("-> Loading active stock symbols from cleaned prices...")
    symbols = set()
    with open(stocks_path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            symbols.add(row["symbol"])
    print(f"   Identified {len(symbols)} unique equities.")
    return sorted(symbols)

def main():
    print("=================================================================")
    print("PSXpert - Processing News Sentiment & Stock-Specific Impact Data")
    print("=================================================================")

    if not os.path.exists(NEWS_CSV):
        print(f"ERROR: News corpus not found at {NEWS_CSV}")
        return

    trading_calendar = load_trading_calendar(CALENDAR_CSV)
    cal_set = set(trading_calendar)
    engine = StockNewsImpactEngine(trading_calendar)

    # Dictionary: (symbol, session_date) -> list of impact records
    daily_stock_impacts = defaultdict(list)
    daily_stock_direct = defaultdict(list)
    daily_theme_impacts = defaultdict(lambda: defaultdict(list))

    print("-> Streaming and processing historical news articles...")
    processed_count = 0
    impacted_pairs = 0

    with open(NEWS_CSV, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            processed_count += 1
            headline = row.get("headline", "")
            summary = row.get("summary", "")
            pub_at = row.get("published_at", "")
            score_val = row.get("sentiment_score", "0")
            try:
                base_score = float(score_val)
            except ValueError:
                base_score = 0.0

            label_val = row.get("sentiment_label", "Neutral")
            conf_val = row.get("sentiment_confidence", "0.5")
            try:
                base_conf = float(conf_val)
            except ValueError:
                base_conf = 0.5

            res = engine.evaluate_article_impact(
                headline=headline,
                summary=summary,
                published_at=pub_at,
                base_sentiment_score=base_score,
                base_sentiment_label=label_val,
                base_confidence=base_conf
            )

            aligned_session = res["aligned_trading_session"]
            if not aligned_session or aligned_session not in cal_set:
                continue

            # Store stock-specific impacts
            for sym, imp in res["stock_impacts"].items():
                imp_score = imp["impact_score"]
                is_direct = imp["is_direct_mention"]
                daily_stock_impacts[(sym, aligned_session)].append(imp_score)
                if is_direct:
                    daily_stock_direct[(sym, aligned_session)].append(imp_score)

                # Track specific macro themes
                for th in res["macro_themes_detected"]:
                    if "OIL" in th:
                        daily_theme_impacts["OIL"][(sym, aligned_session)].append(imp_score)
                    elif "RATE" in th:
                        daily_theme_impacts["RATE"][(sym, aligned_session)].append(imp_score)
                    elif "PKR" in th:
                        daily_theme_impacts["PKR"][(sym, aligned_session)].append(imp_score)

                impacted_pairs += 1

            if processed_count % 10000 == 0:
                print(f"   Processed {processed_count:,} articles -> {impacted_pairs:,} stock-day pairs...")

    print(f"-> Finished raw news pass: {processed_count:,} articles parsed.")
    print(f"   Generated {len(daily_stock_impacts):,} unique (symbol, session) impact points.")

    # Multi-horizon exponential decay aggregation
    # Lambda = 0.35 (half-life approx 2 trading days)
    print("-> Computing multi-horizon decayed sentiment features (1d, 7d, 30d)...")

    # Get set of all stocks impacted
    impacted_symbols = sorted(set(sym for (sym, d) in daily_stock_impacts.keys()))
    print(f"   Total unique stocks impacted: {len(impacted_symbols)}")

    # Calendar date to index
    date_to_idx = {d: i for i, d in enumerate(trading_calendar)}

    # Build output table
    output_rows = []
    
    # Process per symbol to efficiently maintain rolling exponential decay
    for sym in impacted_symbols:
        # Get sorted list of sessions for this symbol
        sym_sessions = sorted(set(d for (s, d) in daily_stock_impacts.keys() if s == sym))
        
        # Track rolling states
        # rolling_7d = decay * prev + today
        decay_7d = math.exp(-0.35)
        decay_30d = math.exp(-0.08)

        rolling_imp_7d = 0.0
        rolling_imp_30d = 0.0
        rolling_dir_7d = 0.0
        rolling_count_7d = 0.0

        last_idx = None

        for session in sym_sessions:
            curr_idx = date_to_idx.get(session)
            if curr_idx is None:
                continue

            day_impacts = daily_stock_impacts.get((sym, session), [])
            day_directs = daily_stock_direct.get((sym, session), [])
            oil_impacts = daily_theme_impacts["OIL"].get((sym, session), [])
            rate_impacts = daily_theme_impacts["RATE"].get((sym, session), [])
            fx_impacts = daily_theme_impacts["PKR"].get((sym, session), [])

            imp_1d = sum(day_impacts) / len(day_impacts) if day_impacts else 0.0
            dir_1d = sum(day_directs) / len(day_directs) if day_directs else 0.0
            oil_1d = sum(oil_impacts) / len(oil_impacts) if oil_impacts else 0.0
            rate_1d = sum(rate_impacts) / len(rate_impacts) if rate_impacts else 0.0
            fx_1d = sum(fx_impacts) / len(fx_impacts) if fx_impacts else 0.0
            cnt_1d = len(day_impacts)

            if last_idx is not None and curr_idx > last_idx:
                gap = curr_idx - last_idx
                rolling_imp_7d = rolling_imp_7d * (decay_7d ** gap) + imp_1d
                rolling_imp_30d = rolling_imp_30d * (decay_30d ** gap) + imp_1d
                rolling_dir_7d = rolling_dir_7d * (decay_7d ** gap) + dir_1d
                rolling_count_7d = rolling_count_7d * (decay_7d ** gap) + cnt_1d
            else:
                rolling_imp_7d = imp_1d
                rolling_imp_30d = imp_1d
                rolling_dir_7d = dir_1d
                rolling_count_7d = float(cnt_1d)

            last_idx = curr_idx

            output_rows.append({
                "symbol": sym,
                "trading_date": session,
                "news_sentiment_1d": round(dir_1d, 4),
                "news_sentiment_7d": round(rolling_dir_7d, 4),
                "stock_impact_score_1d": round(imp_1d, 4),
                "stock_impact_score_7d": round(rolling_imp_7d, 4),
                "stock_impact_score_30d": round(rolling_imp_30d, 4),
                "article_count_1d": cnt_1d,
                "article_count_7d": round(rolling_count_7d, 2),
                "direct_mention_count_7d": len(day_directs),
                "macro_oil_impact_7d": round(oil_1d, 4),
                "macro_rate_impact_7d": round(rate_1d, 4),
                "macro_fx_impact_7d": round(fx_1d, 4),
            })

    output_rows.sort(key=lambda x: (x["trading_date"], x["symbol"]))
    print(f"-> Writing {len(output_rows):,} feature rows to {OUTPUT_CSV}...")
    fieldnames = [
        "symbol", "trading_date",
        "news_sentiment_1d", "news_sentiment_7d",
        "stock_impact_score_1d", "stock_impact_score_7d", "stock_impact_score_30d",
        "article_count_1d", "article_count_7d", "direct_mention_count_7d",
        "macro_oil_impact_7d", "macro_rate_impact_7d", "macro_fx_impact_7d"
    ]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"[OK] Daily stock-level news sentiment dataset created successfully at {OUTPUT_CSV}.")

if __name__ == "__main__":
    main()
