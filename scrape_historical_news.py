import os
import sys
import argparse
import time
import pandas as pd
from datetime import datetime
from src.historical_news_scraper import HistoricalNewsScraper

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def generate_sample_dates(start_year: int = 2002, end_year: int = 2026, freq: str = "quarterly"):
    dates = []
    for y in range(start_year, end_year + 1):
        if freq == "monthly":
            for m in range(1, 13):
                # Avoid future dates in current year
                d_str = f"{y}-{m:02d}-15"
                if d_str <= "2026-10-13":
                    dates.append(d_str)
        elif freq == "quarterly":
            for m in [3, 6, 9, 12]:
                d_str = f"{y}-{m:02d}-15"
                if d_str <= "2026-10-13":
                    dates.append(d_str)
        elif freq == "biannual":
            for m in [6, 12]:
                d_str = f"{y}-{m:02d}-15"
                if d_str <= "2026-10-13":
                    dates.append(d_str)
        else:  # annual
            d_str = f"{y}-06-15"
            if d_str <= "2026-10-13":
                dates.append(d_str)
    return dates


def main():
    parser = argparse.ArgumentParser(description="Scrape historical financial news from 2002 to 2026")
    parser.add_argument("--start-year", type=int, default=2002, help="Start year (default 2002)")
    parser.add_argument("--end-year", type=int, default=2026, help="End year (default 2026)")
    parser.add_argument("--freq", type=str, default="biannual", choices=["annual", "biannual", "quarterly", "monthly"], help="Sampling frequency per year")
    parser.add_argument("--articles-per-date", type=int, default=10, help="Max articles per sampled date")
    args = parser.parse_args()

    print("=" * 70)
    print("PSXpert: Historical Financial News Scraper (2002 – 2026)")
    print(f"Timeframe : {args.start_year} to {args.end_year}")
    print(f"Frequency : {args.freq} sampling across all {args.end_year - args.start_year + 1} years")
    print("Source    : Dawn Business Newspaper Archives")
    print("=" * 70)

    os.makedirs(DATA_DIR, exist_ok=True)
    out_csv = os.path.join(DATA_DIR, "financial_news_historical_2002_2026.csv")

    dates = generate_sample_dates(args.start_year, args.end_year, args.freq)
    print(f"\nGenerated {len(dates)} historical dates across {args.start_year}-{args.end_year} to scrape.")

    scraper = HistoricalNewsScraper()
    all_articles = []

    # If partial file exists, load it
    existing_urls = set()
    if os.path.exists(out_csv):
        try:
            prev_df = pd.read_csv(out_csv)
            existing_urls = set(prev_df["url"].dropna().tolist())
            all_articles = prev_df.to_dict("records")
            print(f"Loaded {len(all_articles)} existing records from {out_csv}.")
        except Exception:
            pass

    for i, date_str in enumerate(dates):
        year = date_str.split("-")[0]
        print(f"[{i+1}/{len(dates)}] Scraping Year {year} ({date_str})...", end=" ", flush=True)
        records = scraper.fetch_articles_for_date(date_str, max_articles=args.articles_per_date)
        
        new_records = [r for r in records if r["url"] not in existing_urls]
        for r in new_records:
            existing_urls.add(r["url"])
            all_articles.append(r)

        print(f"found {len(records)} articles ({len(new_records)} new). Total: {len(all_articles)}")

        # Checkpoint save every 5 dates
        if (i + 1) % 5 == 0 and all_articles:
            df_temp = pd.DataFrame(all_articles)
            df_temp.drop_duplicates(subset=["url"], inplace=True)
            df_temp.to_csv(out_csv, index=False, encoding="utf-8-sig")

    if all_articles:
        df_final = pd.DataFrame(all_articles)
        df_final.drop_duplicates(subset=["url"], inplace=True)
        df_final.sort_values(by="published_at", inplace=True)
        df_final.reset_index(drop=True, inplace=True)
        df_final.to_csv(out_csv, index=False, encoding="utf-8-sig")

        # Also merge into master data/financial_news.csv
        master_news_path = os.path.join(DATA_DIR, "financial_news.csv")
        if os.path.exists(master_news_path):
            df_live = pd.read_csv(master_news_path)
            combined = pd.concat([df_final, df_live], ignore_index=True)
            combined.drop_duplicates(subset=["url"], inplace=True)
            combined.sort_values(by="published_at", inplace=True)
            combined.reset_index(drop=True, inplace=True)
            combined.to_csv(master_news_path, index=False, encoding="utf-8-sig")
            print(f"\n-> Merged into master: {master_news_path} (Total: {len(combined)} articles)")

        print("\n" + "=" * 70)
        print(f"SUCCESS: {len(df_final)} historical articles saved to {out_csv}")
        # Show year distribution
        years = df_final["published_at"].str.slice(0, 4)
        print("\nYear Distribution Summary:")
        print(years.value_counts().sort_index().to_string())
        print("=" * 70)
    else:
        print("Warning: No historical articles were retrieved.")


if __name__ == "__main__":
    main()
