import os
import sys
import pandas as pd
from src.news_scraper import FinancialNewsScraper

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def main():
    print("=" * 70)
    print("PSXpert: Financial News Scraper (Dataset B)")
    print("Sources: Dawn Business, Business Recorder, Profit Pakistan Today")
    print("=" * 70)

    os.makedirs(DATA_DIR, exist_ok=True)
    scraper = FinancialNewsScraper()

    df = scraper.scrape_all_financial_news()

    if df.empty:
        print("Warning: No financial news articles could be retrieved.")
        return

    output_path = os.path.join(DATA_DIR, "financial_news.csv")
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 70)
    print(f"SUCCESS: {len(df)} financial news articles saved to {output_path}")
    print("=" * 70)

    # Display Breakdown by Publisher
    print("\n[Breakdown by Publisher]")
    print(df["publisher"].value_counts().to_string())

    # Display Sample Tagged Articles
    print("\n[Sample Articles with Detected Symbols & Sectors]")
    for i, row in df.head(8).iterrows():
        print(f"\n{i+1}. [{row['publisher']}] ({row['published_at']})")
        print(f"   Headline : {row['headline']}")
        print(f"   Symbols  : {row['symbols_mentioned']}")
        print(f"   Sector   : {row['relevant_sector_or_market']}")
        print(f"   URL      : {row['url']}")
        print(f"   Summary  : {str(row['summary'])[:120]}...")


if __name__ == "__main__":
    main()
