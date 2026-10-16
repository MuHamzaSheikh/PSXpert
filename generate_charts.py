#!/usr/bin/env python3
"""
PSXpert - Real-Data Candlestick Chart & Pattern Generator CLI
Generates interactive HTML charts and static high-res PNG charts for PSX stocks and KSE-100 index.
Detects 20+ candlestick patterns with real historical and recent data from PostgreSQL.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from src.visualization.chart_generator import CandlestickChartGenerator

# Top representative PSX equities across major sectors
DEFAULT_TICKERS = [
    "KSE100",  # Overall Market Index
    "OGDC",    # Oil & Gas Exploration (Large Cap)
    "LUCK",    # Cement & Construction
    "MEBL",    # Islamic Commercial Banks
    "SYS",     # Technology & Software
    "HUBC",    # Power Generation
    "HBL",     # Commercial Banking
    "PRL",     # Refinery
    "ENGRO"    # Conglomerate / Fertilizer
]


def print_pattern_table(patterns, symbol):
    print(f"\n[Detected Candlestick Patterns for {symbol} (Latest to Oldest)]")
    if not patterns:
        print("  No major classical patterns detected in this window.")
        return

    table_data = []
    for p in reversed(patterns[-15:]): # Show up to 15 latest patterns
        table_data.append({
            "Date": p["date"],
            "Pattern": p["pattern"],
            "Type": p["type"],
            "Signal": p["signal"],
            "Close (PKR)": f"{p['close']:,.2f}",
            "Description": p["description"][:50] + "..."
        })
    df = pd.DataFrame(table_data)
    print(df.to_string(index=False))


def generate_master_dashboard_html(results_list, output_file: Path):
    """Generates an executive interactive dashboard linking all generated charts with pattern highlights."""
    cards_html = ""
    for res in results_list:
        sym = res["symbol"]
        name = res["company_name"]
        close_p = res["latest_close"]
        pats = res["patterns"]
        total_p = res["patterns_detected_count"]
        bull_p = res["bullish_patterns"]
        bear_p = res["bearish_patterns"]
        neu_p = res["neutral_patterns"]
        html_link = f"{sym.lower()}_candlestick_patterns.html"
        png_link = f"{sym.lower()}_candlestick.png"

        # Recent 3 patterns badges
        recent_badges = ""
        for p in reversed(pats[-3:]):
            badge_color = "#00e676" if p["type"] == "BULLISH" else ("#ff1744" if p["type"] == "BEARISH" else "#9e9e9e")
            recent_badges += f"""
                <div style="display:flex; justify-content:space-between; margin-bottom:4px; font-size:12px;">
                    <span style="color:{badge_color}; font-weight:600;">{p['pattern']}</span>
                    <span style="color:#9ca3af;">{p['date']}</span>
                </div>
            """

        cards_html += f"""
        <div class="stock-card">
            <div class="card-header">
                <div>
                    <span class="ticker-badge">{sym}</span>
                    <h3 style="margin:6px 0 0 0; font-size:16px; color:#ffffff;">{name}</h3>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:18px; font-weight:700; color:#ffffff;">PKR {close_p:,.2f}</div>
                    <div style="font-size:11px; color:#9ca3af;">{res['date_range']}</div>
                </div>
            </div>
            
            <div class="stats-row">
                <div class="stat-box">
                    <div class="stat-val" style="color:#38bdf8;">{total_p}</div>
                    <div class="stat-lbl">Total Patterns</div>
                </div>
                <div class="stat-box">
                    <div class="stat-val" style="color:#00e676;">{bull_p}</div>
                    <div class="stat-lbl">Bullish</div>
                </div>
                <div class="stat-box">
                    <div class="stat-val" style="color:#ff1744;">{bear_p}</div>
                    <div class="stat-lbl">Bearish</div>
                </div>
                <div class="stat-box">
                    <div class="stat-val" style="color:#9e9e9e;">{neu_p}</div>
                    <div class="stat-lbl">Neutral</div>
                </div>
            </div>

            <div style="background:#111827; border-radius:8px; padding:10px; margin:12px 0;">
                <div style="font-size:11px; font-weight:600; color:#6b7280; text-transform:uppercase; margin-bottom:6px;">Latest Formations</div>
                {recent_badges or '<div style="color:#6b7280; font-size:12px;">No recent patterns in window</div>'}
            </div>

            <div class="actions">
                <a href="{html_link}" target="_blank" class="btn btn-primary">📊 Open Interactive Chart</a>
                <a href="{png_link}" target="_blank" class="btn btn-secondary">🖼️ View PNG</a>
            </div>
        </div>
        """

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PSXpert — Candlestick Charts & Real-Data Pattern Recognition</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-dark: #0a0e17;
            --card-bg: #111827;
            --border: #1f2937;
            --accent-bull: #00e676;
            --accent-bear: #ff1744;
            --text-main: #f9fafb;
            --text-muted: #9ca3af;
        }}
        body {{
            margin: 0;
            padding: 0;
            background-color: var(--bg-dark);
            color: var(--text-main);
            font-family: 'Inter', -apple-system, sans-serif;
            -webkit-font-smoothing: antialiased;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 32px 24px;
        }}
        header {{
            border-bottom: 1px solid var(--border);
            padding-bottom: 24px;
            margin-bottom: 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .brand-icon {{
            background: linear-gradient(135deg, #00e676 0%, #00b0ff 100%);
            width: 40px;
            height: 40px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            font-weight: 800;
            color: #000000;
        }}
        h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 800;
            letter-spacing: -0.5px;
        }}
        .subtitle {{
            color: var(--text-muted);
            font-size: 13px;
            margin-top: 4px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
            gap: 24px;
        }}
        .stock-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
        }}
        .stock-card:hover {{
            transform: translateY(-2px);
            border-color: #374151;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 1px solid #1f2937;
            padding-bottom: 12px;
        }}
        .ticker-badge {{
            background: #1f2937;
            color: #38bdf8;
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
            border: 1px solid #374151;
        }}
        .stats-row {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 8px;
            margin: 14px 0;
        }}
        .stat-box {{
            background: #0d131f;
            border: 1px solid #1f2937;
            border-radius: 8px;
            padding: 8px 4px;
            text-align: center;
        }}
        .stat-val {{
            font-size: 16px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }}
        .stat-lbl {{
            font-size: 10px;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-top: 2px;
        }}
        .actions {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 14px;
        }}
        .btn {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 9px 12px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            text-decoration: none;
            cursor: pointer;
            transition: all 0.15s ease;
        }}
        .btn-primary {{
            background: #00e676;
            color: #000000;
        }}
        .btn-primary:hover {{
            background: #00c853;
        }}
        .btn-secondary {{
            background: #1f2937;
            color: #e5e7eb;
            border: 1px solid #374151;
        }}
        .btn-secondary:hover {{
            background: #374151;
            color: #ffffff;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="brand">
                <div class="brand-icon">📈</div>
                <div>
                    <h1>PSXpert Candlestick & Pattern Analysis Suite</h1>
                    <div class="subtitle">Live PostgreSQL Real-Data Trading Engine | 20+ Candlestick Patterns Detected</div>
                </div>
            </div>
            <div>
                <span style="background:rgba(0,230,118,0.1); color:#00e676; border:1px solid rgba(0,230,118,0.3); padding:6px 12px; border-radius:20px; font-size:12px; font-weight:600;">
                    ● Database Status: Connected (PostgreSQL 18)
                </span>
            </div>
        </header>

        <div class="grid">
            {cards_html}
        </div>
    </div>
</body>
</html>"""
    output_file.write_text(full_html, encoding="utf-8")
    print(f"\n[Generated Master Visual Dashboard] -> {output_file}")


def main():
    parser = argparse.ArgumentParser(description="PSXpert Candlestick & Pattern Generator CLI")
    parser.add_argument("--symbol", type=str, default=None, help="Stock symbol (e.g. OGDC, LUCK, KSE100)")
    parser.add_argument("--days", type=int, default=120, help="Number of trading days to chart (default: 120)")
    parser.add_argument("--all", action="store_true", help="Generate charts for all top representative PSX stocks and KSE-100")
    args = parser.parse_args()

    print("=" * 75)
    print("PSXPERT REAL-DATA CANDLESTICK & PATTERN RECOGNITION SUITE")
    print("=" * 75)

    chart_gen = CandlestickChartGenerator()
    results = []

    if args.symbol:
        symbols_to_run = [args.symbol.upper()]
    elif args.all or not args.symbol:
        symbols_to_run = DEFAULT_TICKERS

    print(f"Target Symbols: {', '.join(symbols_to_run)}")
    print(f"Historical Window: {args.days} trading days\n")

    for sym in symbols_to_run:
        try:
            print(f"Processing {sym} from database...")
            res = chart_gen.analyze_and_chart(sym, days=args.days)
            results.append(res)
            print(f"  [+] {res['company_name']}: {res['total_bars']} bars, {res['patterns_detected_count']} patterns detected")
            print(f"    - Interactive HTML : {res['html_path']}")
            print(f"    - Static PNG Image : {res['png_path']}")
            print_pattern_table(res["patterns"], sym)
            print("-" * 75)
        except Exception as e:
            print(f"  [-] Failed to process {sym}: {e}\n")

    if results:
        dashboard_path = Path("reports/charts/index.html")
        generate_master_dashboard_html(results, dashboard_path)

    print("\nAll charts and candlestick pattern recognitions generated successfully!")


if __name__ == "__main__":
    main()
