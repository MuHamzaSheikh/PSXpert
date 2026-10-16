"""
PSXpert - Real-Data Candlestick Chart Generator
Renders interactive HTML charts (Plotly) and high-resolution static PNG charts (mplfinance/matplotlib)
annotated with mathematically detected candlestick patterns for PSX equities and the KSE-100 index.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import matplotlib
matplotlib.use("Agg") # Non-interactive headless backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import mplfinance as mpf
from sqlalchemy import text

from src.database.connection import get_session
from src.analysis.candlestick_patterns import CandlestickPatternDetector


class CandlestickChartGenerator:
    """
    Renders professional trading candlestick charts with pattern recognition callouts.
    Fetches real price data directly from PostgreSQL / database.
    """

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir or "reports/charts")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.detector = CandlestickPatternDetector()

    def fetch_price_data(self, symbol: str, days: int = 120) -> pd.DataFrame:
        """
        Fetches real OHLCV data from database.
        If symbol == 'KSE100' or starts with '^', queries market_indices.
        Otherwise queries stock_prices.
        """
        sym = symbol.strip().upper()
        session = get_session()
        try:
            if sym in ["KSE100", "KSE-100", "INDEX", "MARKET"]:
                query = text("""
                    SELECT trading_date, open, high, low, close, volume, point_change, pct_change
                    FROM market_indices
                    WHERE index_symbol = 'KSE100'
                    ORDER BY trading_date DESC
                    LIMIT :limit;
                """)
                res = session.execute(query, {"limit": days}).fetchall()
                cols = ["trading_date", "open", "high", "low", "close", "volume", "point_change", "pct_change"]
            else:
                query = text("""
                    SELECT trading_date, open, high, low, close, volume
                    FROM stock_prices
                    WHERE symbol = :symbol
                    ORDER BY trading_date DESC
                    LIMIT :limit;
                """)
                res = session.execute(query, {"symbol": sym, "limit": days}).fetchall()
                cols = ["trading_date", "open", "high", "low", "close", "volume"]

            if not res:
                raise ValueError(f"No price records found in database for symbol '{sym}'.")

            df = pd.DataFrame(res, columns=cols)
            df["symbol"] = sym
            df = df.sort_values(by="trading_date").reset_index(drop=True)
            return df
        finally:
            session.close()

    def generate_interactive_html(
        self,
        symbol: str,
        df_annotated: pd.DataFrame,
        patterns: List[Dict[str, Any]],
        company_name: Optional[str] = None
    ) -> Path:
        """
        Builds a TradingView-caliber interactive dark-mode candlestick chart with Plotly.
        Includes volume subplots, EMA overlays, and marker annotations for all detected patterns.
        """
        display_title = f"{symbol} - {company_name}" if company_name else symbol
        if symbol == "KSE100":
            display_title = "KSE-100 Index (Pakistan Stock Exchange - Overall Market)"

        # Create 2 subplots (Row 1: Candlesticks & EMAs; Row 2: Volume)
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.78, 0.22],
            subplot_titles=(None, None)
        )

        dates = pd.to_datetime(df_annotated["trading_date"])

        # 1. Candlestick Trace
        candlestick = go.Candlestick(
            x=dates,
            open=df_annotated["open"],
            high=df_annotated["high"],
            low=df_annotated["low"],
            close=df_annotated["close"],
            name="OHLC",
            increasing_line_color="#00e676", # Vivid Emerald Green
            increasing_fillcolor="#00e676",
            decreasing_line_color="#ff1744", # Vivid Crimson Red
            decreasing_fillcolor="#ff1744",
            line=dict(width=1.2),
            hoverlabel=dict(bgcolor="#1f2937", font_size=12, font_family="Inter, sans-serif")
        )
        fig.add_trace(candlestick, row=1, col=1)

        # 2. Moving Average Overlays
        if "ema20" in df_annotated and df_annotated["ema20"].notna().any():
            fig.add_trace(go.Scatter(
                x=dates, y=df_annotated["ema20"],
                mode="lines", name="EMA 20",
                line=dict(color="#00e5ff", width=1.5) # Neon Cyan
            ), row=1, col=1)

        if "ema50" in df_annotated and df_annotated["ema50"].notna().any():
            fig.add_trace(go.Scatter(
                x=dates, y=df_annotated["ema50"],
                mode="lines", name="EMA 50",
                line=dict(color="#ffb300", width=1.5) # Gold / Amber
            ), row=1, col=1)

        if "ema200" in df_annotated and df_annotated["ema200"].notna().any():
            fig.add_trace(go.Scatter(
                x=dates, y=df_annotated["ema200"],
                mode="lines", name="EMA 200",
                line=dict(color="#d500f9", width=1.5) # Neon Violet
            ), row=1, col=1)

        # 3. Volume Subplot
        vol_colors = np.where(df_annotated["close"] >= df_annotated["open"], "#00e676", "#ff1744")
        volume_bars = go.Bar(
            x=dates,
            y=df_annotated["volume"],
            name="Volume",
            marker=dict(color=vol_colors, opacity=0.7),
            showlegend=False
        )
        fig.add_trace(volume_bars, row=2, col=1)

        # 4. Pattern Recognition Visual Annotations
        # Add shape/text callouts for each pattern
        for p in patterns:
            p_date = pd.to_datetime(p["date"])
            p_name = p["pattern"]
            p_type = p["type"]
            p_sig = p["signal"]
            p_desc = p["description"]
            high_val = p["high"]
            low_val = p["low"]

            if p_type == "BULLISH":
                arrow_color = "#00e676"
                y_pos = low_val * 0.985
                ay_pos = 35
                icon = "▲"
            elif p_type == "BEARISH":
                arrow_color = "#ff1744"
                y_pos = high_val * 1.015
                ay_pos = -35
                icon = "▼"
            else:
                arrow_color = "#9e9e9e"
                y_pos = high_val * 1.012
                ay_pos = -25
                icon = "◆"

            hover_text = (
                f"<b>{icon} {p_name} ({p_type})</b><br>"
                f"Date: {p['date']}<br>"
                f"Signal: <b>{p_sig}</b><br>"
                f"Close: {p['close']:,.2f}<br>"
                f"<i>{p_desc}</i>"
            )

            fig.add_annotation(
                x=p_date,
                y=y_pos,
                text=f"<b>{icon} {p_name}</b>",
                showarrow=True,
                arrowhead=2,
                arrowsize=1.2,
                arrowwidth=1.5,
                arrowcolor=arrow_color,
                ay=ay_pos,
                bgcolor="#111827",
                bordercolor=arrow_color,
                borderwidth=1.5,
                borderpad=3,
                font=dict(color="#ffffff", size=9, family="Inter, monospace"),
                hovertext=hover_text,
                row=1, col=1
            )

        # Layout styling
        latest_close = df_annotated["close"].iloc[-1]
        earliest_close = df_annotated["close"].iloc[0]
        net_pct = ((latest_close - earliest_close) / earliest_close) * 100
        net_color = "#00e676" if net_pct >= 0 else "#ff1744"

        fig.update_layout(
            title=dict(
                text=(
                    f"<b>{display_title}</b> &nbsp;|&nbsp; "
                    f"Latest Close: <b>PKR {latest_close:,.2f}</b> "
                    f"(<span style='color:{net_color}'>{net_pct:+.2f}%</span>) &nbsp;|&nbsp; "
                    f"Patterns Detected: <b>{len(patterns)}</b>"
                ),
                font=dict(color="#f3f4f6", size=16, family="Inter, sans-serif"),
                x=0.03, y=0.96
            ),
            template="plotly_dark",
            paper_bgcolor="#0b0e14",
            plot_bgcolor="#0f141c",
            font=dict(family="Inter, sans-serif", color="#9ca3af"),
            xaxis=dict(
                rangeslider=dict(visible=False),
                gridcolor="#1f2937",
                zerolinecolor="#374151",
                showspikes=True,
                spikecolor="#6b7280",
                spikemode="across",
                spikesnap="cursor",
                spikethickness=1
            ),
            xaxis2=dict(
                gridcolor="#1f2937",
                zerolinecolor="#374151"
            ),
            yaxis=dict(
                title=dict(text="Price (PKR)", font=dict(color="#d1d5db")),
                gridcolor="#1f2937",
                zerolinecolor="#374151",
                side="right"
            ),
            yaxis2=dict(
                title=dict(text="Volume", font=dict(color="#9ca3af")),
                gridcolor="#1f2937",
                zerolinecolor="#374151",
                side="right"
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1.0,
                bgcolor="rgba(17, 24, 39, 0.8)",
                bordercolor="#374151",
                borderwidth=1
            ),
            margin=dict(l=40, r=60, t=70, b=40),
            hovermode="x unified",
            height=750
        )

        out_file = self.output_dir / f"{symbol.lower()}_candlestick_patterns.html"
        fig.write_html(str(out_file), include_plotlyjs="cdn", full_html=True)
        return out_file

    def generate_static_image(
        self,
        symbol: str,
        df_annotated: pd.DataFrame,
        patterns: List[Dict[str, Any]],
        company_name: Optional[str] = None
    ) -> Path:
        """
        Renders a high-resolution static PNG chart using mplfinance and matplotlib
        with dark theme, volume panel, moving averages, and pattern annotations.
        """
        # Prepare DataFrame formatted for mplfinance (DatetimeIndex + Open, High, Low, Close, Volume)
        mpf_df = df_annotated.copy()
        mpf_df["Date"] = pd.to_datetime(mpf_df["trading_date"])
        mpf_df = mpf_df.set_index("Date").sort_index()
        mpf_df = mpf_df.rename(columns={
            "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"
        })

        # Custom dark market color style
        mc = mpf.make_marketcolors(
            up="#00e676", down="#ff1744",
            edge={"up": "#00e676", "down": "#ff1744"},
            wick={"up": "#00e676", "down": "#ff1744"},
            volume={"up": "#00c853", "down": "#d50000"}
        )
        s = mpf.make_mpf_style(
            base_mpf_style="nightclouds",
            marketcolors=mc,
            facecolor="#0b0e14",
            edgecolor="#1f2937",
            figcolor="#0b0e14",
            gridcolor="#1f2937",
            gridstyle="--",
            rc={"font.family": "DejaVu Sans", "axes.labelcolor": "#9ca3af", "xtick.color": "#9ca3af", "ytick.color": "#9ca3af"}
        )

        # Build additional plots (EMAs)
        addplots = []
        if "ema20" in df_annotated and df_annotated["ema20"].notna().any():
            addplots.append(mpf.make_addplot(mpf_df["ema20"], color="#00e5ff", width=1.2, panel=0))
        if "ema50" in df_annotated and df_annotated["ema50"].notna().any():
            addplots.append(mpf.make_addplot(mpf_df["ema50"], color="#ffb300", width=1.2, panel=0))

        # Build pattern marker series
        bull_markers = [np.nan] * len(mpf_df)
        bear_markers = [np.nan] * len(mpf_df)

        pattern_dates = {p["date"]: p for p in patterns}
        for idx, (dt, row) in enumerate(mpf_df.iterrows()):
            d_str = dt.strftime("%Y-%m-%d")
            if d_str in pattern_dates:
                pat = pattern_dates[d_str]
                if pat["type"] == "BULLISH":
                    bull_markers[idx] = row["Low"] * 0.985
                elif pat["type"] == "BEARISH":
                    bear_markers[idx] = row["High"] * 1.015

        if any(not np.isnan(v) for v in bull_markers):
            addplots.append(mpf.make_addplot(bull_markers, type="scatter", markersize=80, marker="^", color="#00e676", panel=0))
        if any(not np.isnan(v) for v in bear_markers):
            addplots.append(mpf.make_addplot(bear_markers, type="scatter", markersize=80, marker="v", color="#ff1744", panel=0))

        display_name = f"{symbol} - {company_name}" if company_name else symbol
        if symbol == "KSE100":
            display_name = "KSE-100 Index (Pakistan Stock Exchange)"

        out_png = self.output_dir / f"{symbol.lower()}_candlestick.png"

        has_volume = bool((mpf_df["Volume"] > 0).any())
        plot_kwargs = {
            "type": "candle",
            "style": s,
            "title": f"\n{display_name} | Real Data Candlestick & Pattern Analysis",
            "ylabel": "Price (PKR)",
            "volume": has_volume,
            "addplot": addplots,
            "figsize": (14, 8),
            "returnfig": True,
            "tight_layout": True
        }
        if has_volume:
            plot_kwargs["ylabel_lower"] = "Volume"
            plot_kwargs["panel_ratios"] = (4, 1)

        fig, axlist = mpf.plot(mpf_df, **plot_kwargs)

        # Annotate text labels for top patterns directly on matplotlib axes
        ax_main = axlist[0]
        annotated_count = 0
        for p in patterns[-8:]: # Annotate the 8 most recent patterns cleanly
            try:
                p_dt = pd.to_datetime(p["date"])
                if p_dt in mpf_df.index:
                    x_idx = mpf_df.index.get_loc(p_dt)
                    if p["type"] == "BULLISH":
                        y_pos = p["low"] * 0.97
                        ax_main.text(x_idx, y_pos, f"{p['pattern']}", color="#00e676", fontsize=7.5,
                                     ha="center", va="top", rotation=25, fontweight="bold")
                    elif p["type"] == "BEARISH":
                        y_pos = p["high"] * 1.03
                        ax_main.text(x_idx, y_pos, f"{p['pattern']}", color="#ff1744", fontsize=7.5,
                                     ha="center", va="bottom", rotation=25, fontweight="bold")
                    annotated_count += 1
            except Exception:
                pass

        fig.savefig(str(out_png), dpi=150, facecolor=fig.get_facecolor(), edgecolor="none")
        plt.close(fig)
        return out_png

    def analyze_and_chart(self, symbol: str, days: int = 120) -> Dict[str, Any]:
        """
        Master method:
        1. Queries real OHLCV data from database.
        2. Detects all candlestick patterns.
        3. Generates interactive Plotly HTML chart.
        4. Generates static High-Res PNG chart.
        5. Returns structured analysis results.
        """
        sym = symbol.strip().upper()
        df = self.fetch_price_data(sym, days=days)

        # Fetch corporate company name if stock
        company_name = None
        if sym not in ["KSE100", "KSE-100", "INDEX", "MARKET"]:
            session = get_session()
            try:
                row = session.execute(text("SELECT company_name FROM companies WHERE symbol = :s"), {"s": sym}).fetchone()
                if row:
                    company_name = row[0]
            finally:
                session.close()

        # Run pattern detection
        df_annotated, patterns = self.detector.detect_patterns(df)

        # Generate charts
        html_path = self.generate_interactive_html(sym, df_annotated, patterns, company_name)
        png_path = self.generate_static_image(sym, df_annotated, patterns, company_name)

        # Breakdown summary
        bullish_count = sum(1 for p in patterns if p["type"] == "BULLISH")
        bearish_count = sum(1 for p in patterns if p["type"] == "BEARISH")
        neutral_count = sum(1 for p in patterns if p["type"] == "NEUTRAL")

        return {
            "symbol": sym,
            "company_name": company_name or ("Pakistan Stock Exchange KSE-100" if sym == "KSE100" else sym),
            "total_bars": len(df),
            "date_range": f"{df['trading_date'].iloc[0]} to {df['trading_date'].iloc[-1]}",
            "latest_close": float(df["close"].iloc[-1]),
            "html_path": str(html_path),
            "png_path": str(png_path),
            "patterns_detected_count": len(patterns),
            "bullish_patterns": bullish_count,
            "bearish_patterns": bearish_count,
            "neutral_patterns": neutral_count,
            "patterns": patterns
        }
