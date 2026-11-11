"""Point-in-time Technical Analysis Engine for PSX equities."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd
from sqlalchemy.engine import Connection

from src.analysis.candlestick_patterns import CandlestickPatternDetector
from src.analysis.common import (
    get_company_metadata,
    load_clean_symbol_prices,
    load_trading_calendar,
    resolve_effective_as_of_date,
    safe_div,
    safe_float,
    sanitize_for_json,
)
from src.analysis.technical_indicators import TechnicalIndicatorCalculator
from src.predictive_data.regime_causal import CausalMarketRegimeHMM

logger = logging.getLogger(__name__)

# Matches chronological_splits.json TRAIN end date to avoid Val/Test leakage
HMM_DEFAULT_TRAIN_END = date(2021, 11, 26)

# Three-candle & two-candle structural pattern strength classification
_STRONG_PATTERNS = {
    "Morning Star",
    "Evening Star",
    "Three White Soldiers",
    "Three Black Crows",
    "Bullish Engulfing",
    "Bearish Engulfing",
    "Bullish Marubozu",
    "Bearish Marubozu",
}
_MODERATE_PATTERNS = {
    "Piercing Line",
    "Dark Cloud Cover",
    "Bullish Harami",
    "Bearish Harami",
    "Hammer",
    "Inverted Hammer",
    "Shooting Star",
    "Hanging Man",
    "Dragonfly Doji",
    "Gravestone Doji",
}


class TechnicalAnalysisEngine:
    """
    Independent, causal Technical Analysis Engine for PSX stocks.

    Reuses TechnicalIndicatorCalculator, CandlestickPatternDetector,
    corporate-action split adjustment, and CausalMarketRegimeHMM without
    weekend phantom bars or future candle leakage.
    """

    def __init__(self) -> None:
        self.indicator_calc = TechnicalIndicatorCalculator()
        self.pattern_detector = CandlestickPatternDetector()
        self._hmm_cache: dict[tuple[str, str, int], pd.DataFrame] = {}

    def analyze(
        self,
        conn: Connection,
        symbol: str,
        as_of_date: Optional[date | datetime | str] = None,
    ) -> dict[str, Any]:
        """Run full 7-pillar point-in-time technical analysis for `symbol` up to `as_of_date`."""
        sym = symbol.strip().upper()
        meta = get_company_metadata(conn, sym)
        req_cutoff, mkt_cutoff = resolve_effective_as_of_date(conn, sym, as_of_date)

        cal_df = load_trading_calendar(conn, max_date=mkt_cutoff)
        adj_df, cal_df, price_audit = load_clean_symbol_prices(conn, sym, max_date=mkt_cutoff, cal_df=cal_df)

        if adj_df.empty:
            return self._build_no_price_response(sym, meta, req_cutoff, mkt_cutoff, price_audit)

        # Prepare clean split-adjusted OHLCV DataFrame matching TechnicalIndicatorCalculator schema
        df_ind_input = pd.DataFrame(
            {
                "trading_date": pd.to_datetime(adj_df["trading_date"]),
                "open": pd.to_numeric(adj_df["adj_open"], errors="coerce"),
                "high": pd.to_numeric(adj_df["adj_high"], errors="coerce"),
                "low": pd.to_numeric(adj_df["adj_low"], errors="coerce"),
                "close": pd.to_numeric(adj_df["adj_close"], errors="coerce"),
                "volume": pd.to_numeric(adj_df["volume"], errors="coerce").fillna(0.0),
                "raw_close": pd.to_numeric(adj_df["raw_close"], errors="coerce"),
                "is_flat_ohlc_bar": adj_df["is_flat_ohlc_bar"].astype(bool),
                "has_price_glitch_flag": adj_df["has_price_glitch_flag"].astype(bool)
                if "has_price_glitch_flag" in adj_df.columns
                else False,
            }
        )

        ind_df = self.indicator_calc.compute_all_indicators(df_ind_input)
        if "obv_ema_20" not in ind_df.columns and "obv" in ind_df.columns:
            ind_df["obv_ema_20"] = ind_df["obv"].ewm(span=20, adjust=False).mean()

        n_bars = len(ind_df)
        latest = ind_df.iloc[-1]
        latest_trade_date = pd.to_datetime(latest["trading_date"]).date()
        staleness_cal_days = max(0, (mkt_cutoff - latest_trade_date).days)
        missing_mkt_sessions = int(
            (pd.to_datetime(cal_df["trading_date"]).dt.date > latest_trade_date).sum()
        )

        # 7 analytical domains
        trend = self._analyze_trend(ind_df, latest, n_bars)
        momentum = self._analyze_momentum(ind_df, latest, n_bars)
        volatility = self._analyze_volatility(ind_df, latest, n_bars)
        volume = self._analyze_volume(ind_df, latest, n_bars)
        candlesticks = self._analyze_candlesticks(ind_df, sym, df_ind_input["is_flat_ohlc_bar"])
        support_resistance = self._analyze_support_resistance(ind_df, latest, n_bars)
        hmm_context = self._analyze_hmm_context(conn, cal_df, ind_df, mkt_cutoff)

        # Composite scoring & conflicting signals
        synthesis = self._synthesize_assessment(
            trend=trend,
            momentum=momentum,
            volatility=volatility,
            volume=volume,
            candlesticks=candlesticks,
            support_resistance=support_resistance,
            hmm_context=hmm_context,
            n_bars=n_bars,
            staleness_cal_days=staleness_cal_days,
            price_audit=price_audit,
        )

        raw_close = safe_float(latest["raw_close"], 4)
        adj_close = safe_float(latest["close"], 4)
        prev_close = safe_float(ind_df["close"].iloc[-2], 4) if n_bars >= 2 else None
        change_1d_pct = (
            safe_float(((adj_close - prev_close) / prev_close) * 100.0, 2)
            if adj_close is not None and prev_close and prev_close > 0
            else None
        )

        ret_5d_pct = self._period_return_pct(ind_df["close"], 5)
        ret_20d_pct = self._period_return_pct(ind_df["close"], 20)
        ret_60d_pct = self._period_return_pct(ind_df["close"], 60)
        ret_252d_pct = self._period_return_pct(ind_df["close"], 252)

        recent_flat_bars = int(df_ind_input["is_flat_ohlc_bar"].tail(20).sum())
        recent_glitch_bars = int(df_ind_input["has_price_glitch_flag"].tail(20).sum())

        data_freshness = {
            "requested_as_of_date": req_cutoff.isoformat(),
            "market_cutoff_date": mkt_cutoff.isoformat(),
            "latest_stock_trading_date": latest_trade_date.isoformat(),
            "earliest_stock_trading_date": pd.to_datetime(ind_df["trading_date"].iloc[0]).date().isoformat(),
            "total_trading_sessions": int(n_bars),
            "staleness_calendar_days": int(staleness_cal_days),
            "missed_market_sessions_since_last_trade": int(missing_mkt_sessions),
            "is_stale": staleness_cal_days > 5 or missing_mkt_sessions > 3,
            "recent_20d_flat_ohlc_bars": recent_flat_bars,
            "recent_20d_glitch_bars": recent_glitch_bars,
        }

        data_source_references = {
            "price_table": "stock_prices (KSE100 trading-calendar aligned, close > 0, split-adjusted)",
            "calendar_table": "market_indices (index_symbol = 'KSE100')",
            "corporate_actions": "corporate_payouts (split) & corporate_announcements (split/bonus)",
            "indicator_engine": "src.analysis.technical_indicators.TechnicalIndicatorCalculator",
            "pattern_engine": "src.analysis.candlestick_patterns.CandlestickPatternDetector",
            "hmm_engine": "src.predictive_data.regime_causal.CausalMarketRegimeHMM",
            "hygiene_audit": price_audit,
        }

        result = {
            "symbol": sym,
            "company_name": meta.get("company_name"),
            "sector": meta.get("sector"),
            "sector_category": meta.get("sector_category"),
            "analysis_type": "TECHNICAL",
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "as_of_date": mkt_cutoff.isoformat(),
            "data_cutoff_timestamp": latest_trade_date.isoformat(),
            "price_snapshot": {
                "latest_trading_date": latest_trade_date.isoformat(),
                "close_pkr": raw_close,
                "split_adjusted_close_pkr": adj_close,
                "open_pkr": safe_float(latest["open"], 4),
                "high_pkr": safe_float(latest["high"], 4),
                "low_pkr": safe_float(latest["low"], 4),
                "volume": int(safe_float(latest["volume"], 0) or 0),
                "change_1d_pct": change_1d_pct,
                "return_5d_pct": ret_5d_pct,
                "return_20d_pct": ret_20d_pct,
                "return_60d_pct": ret_60d_pct,
                "return_252d_pct": ret_252d_pct,
            },
            "trend_analysis": trend,
            "momentum_analysis": momentum,
            "volatility_analysis": volatility,
            "volume_analysis": volume,
            "candlestick_analysis": candlesticks,
            "support_resistance": support_resistance,
            "hmm_market_context": hmm_context,
            "bullish_signals": synthesis["bullish_signals"],
            "bearish_signals": synthesis["bearish_signals"],
            "conflicting_signals": synthesis["conflicting_signals"],
            "overall_assessment": synthesis["overall_assessment"],
            "technical_score": synthesis["technical_score"],
            "score_methodology": synthesis["score_methodology"],
            "summary": synthesis["summary"],
            "data_freshness": data_freshness,
            "data_source_references": data_source_references,
        }
        return sanitize_for_json(result)

    def _build_no_price_response(
        self,
        symbol: str,
        meta: dict[str, Any],
        req_cutoff: date,
        mkt_cutoff: date,
        price_audit: dict[str, Any],
    ) -> dict[str, Any]:
        return sanitize_for_json(
            {
                "symbol": symbol,
                "company_name": meta.get("company_name"),
                "sector": meta.get("sector"),
                "sector_category": meta.get("sector_category"),
                "analysis_type": "TECHNICAL",
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                "as_of_date": mkt_cutoff.isoformat(),
                "data_cutoff_timestamp": mkt_cutoff.isoformat(),
                "status": "NO_PRICE_DATA",
                "price_snapshot": None,
                "trend_analysis": None,
                "momentum_analysis": None,
                "volatility_analysis": None,
                "volume_analysis": None,
                "candlestick_analysis": None,
                "support_resistance": None,
                "hmm_market_context": None,
                "bullish_signals": [],
                "bearish_signals": [],
                "conflicting_signals": [],
                "overall_assessment": "INSUFFICIENT_DATA",
                "technical_score": None,
                "score_methodology": None,
                "summary": f"No valid positive closing prices on KSE-100 trading days for {symbol} on or before {mkt_cutoff}.",
                "data_freshness": {
                    "requested_as_of_date": req_cutoff.isoformat(),
                    "market_cutoff_date": mkt_cutoff.isoformat(),
                    "total_trading_sessions": 0,
                    "is_stale": True,
                },
                "data_source_references": {"hygiene_audit": price_audit},
            }
        )

    @staticmethod
    def _period_return_pct(series: pd.Series, lookback: int) -> Optional[float]:
        if len(series) <= lookback:
            return None
        cur = safe_float(series.iloc[-1])
        prev = safe_float(series.iloc[-(lookback + 1)])
        if cur is None or prev is None or prev <= 0:
            return None
        return safe_float(((cur - prev) / prev) * 100.0, 2)

    @staticmethod
    def _masked_indicator(val: Any, n_bars: int, min_bars: int, digits: int = 4) -> Optional[float]:
        if n_bars < min_bars:
            return None
        return safe_float(val, digits)

    def _analyze_trend(self, ind_df: pd.DataFrame, latest: pd.Series, n_bars: int) -> dict[str, Any]:
        close = safe_float(latest["close"], 4)
        sma_20 = self._masked_indicator(latest.get("sma_20"), n_bars, 20, 4)
        sma_50 = self._masked_indicator(latest.get("sma_50"), n_bars, 50, 4)
        sma_200 = self._masked_indicator(latest.get("sma_200"), n_bars, 200, 4)
        ema_12 = self._masked_indicator(latest.get("ema_12"), n_bars, 12, 4)
        ema_20 = self._masked_indicator(latest.get("ema_20"), n_bars, 20, 4)
        ema_26 = self._masked_indicator(latest.get("ema_26"), n_bars, 26, 4)
        ema_50 = self._masked_indicator(latest.get("ema_50"), n_bars, 50, 4)
        ema_200 = self._masked_indicator(latest.get("ema_200"), n_bars, 200, 4)
        adx = self._masked_indicator(latest.get("adx_14"), n_bars, 28, 2)
        di_plus = self._masked_indicator(latest.get("dmi_plus_14"), n_bars, 28, 2)
        di_minus = self._masked_indicator(latest.get("dmi_minus_14"), n_bars, 28, 2)

        # Short-term trend (EMA12/EMA26 & Close vs EMA20 & 5-bar EMA20 slope)
        ema20_slope_pct = None
        if n_bars >= 25 and "ema_20" in ind_df.columns:
            e_now = safe_float(ind_df["ema_20"].iloc[-1])
            e_prev = safe_float(ind_df["ema_20"].iloc[-6])
            if e_now and e_prev and e_prev > 0:
                ema20_slope_pct = safe_float(((e_now - e_prev) / e_prev) * 100.0, 2)

        short_votes = 0
        if close is not None and ema_20 is not None:
            short_votes += 1 if close > ema_20 else -1
        if ema_12 is not None and ema_26 is not None:
            short_votes += 1 if ema_12 > ema_26 else -1
        if ema20_slope_pct is not None:
            if ema20_slope_pct > 0.3:
                short_votes += 1
            elif ema20_slope_pct < -0.3:
                short_votes -= 1

        if short_votes >= 2:
            short_term_trend = "BULLISH"
        elif short_votes <= -2:
            short_term_trend = "BEARISH"
        else:
            short_term_trend = "SIDEWAYS"

        # Long-term trend (Close vs SMA50 & SMA200, SMA50 vs SMA200)
        long_votes = 0
        long_available = 0
        if close is not None and sma_50 is not None:
            long_available += 1
            long_votes += 1 if close > sma_50 else -1
        if close is not None and sma_200 is not None:
            long_available += 1
            long_votes += 1 if close > sma_200 else -1
        if sma_50 is not None and sma_200 is not None:
            long_available += 1
            long_votes += 1 if sma_50 > sma_200 else -1

        if long_available == 0:
            long_term_trend = "INSUFFICIENT_HISTORY"
        elif long_votes >= 2 or (long_available == 1 and long_votes == 1):
            long_term_trend = "BULLISH"
        elif long_votes <= -2 or (long_available == 1 and long_votes == -1):
            long_term_trend = "BEARISH"
        else:
            long_term_trend = "SIDEWAYS"

        # Trend strength classification from ADX(14)
        if adx is None:
            trend_strength = "UNAVAILABLE"
        elif adx >= 40.0:
            trend_strength = "VERY_STRONG"
        elif adx >= 25.0:
            trend_strength = "STRONG"
        elif adx >= 18.0:
            trend_strength = "MODERATE"
        else:
            trend_strength = "WEAK_OR_RANGEBOUND"

        dmi_direction = None
        if di_plus is not None and di_minus is not None:
            dmi_direction = "BULLISH_DI" if di_plus > di_minus else ("BEARISH_DI" if di_minus > di_plus else "BALANCED")

        # Cross state between SMA 50 and SMA 200 (check exact crossover in last 10 bars)
        ma_cross_status = None
        recent_ma_cross = None
        if sma_50 is not None and sma_200 is not None:
            ma_cross_status = "GOLDEN_ALIGNMENT (SMA50 > SMA200)" if sma_50 > sma_200 else "DEATH_ALIGNMENT (SMA50 < SMA200)"
            if n_bars >= 210:
                tail50 = ind_df["sma_50"].tail(11).values
                tail200 = ind_df["sma_200"].tail(11).values
                for k in range(1, len(tail50)):
                    if tail50[k - 1] <= tail200[k - 1] and tail50[k] > tail200[k]:
                        d_cross = pd.to_datetime(ind_df["trading_date"].iloc[-(len(tail50) - k)]).date().isoformat()
                        recent_ma_cross = f"Golden Cross on {d_cross}"
                    elif tail50[k - 1] >= tail200[k - 1] and tail50[k] < tail200[k]:
                        d_cross = pd.to_datetime(ind_df["trading_date"].iloc[-(len(tail50) - k)]).date().isoformat()
                        recent_ma_cross = f"Death Cross on {d_cross}"

        # Overall trend combines MA direction & ADX filter
        if adx is not None and adx < 16.0 and short_term_trend == "SIDEWAYS":
            overall_trend = "SIDEWAYS"
        elif short_term_trend == "BULLISH" and long_term_trend in ("BULLISH", "INSUFFICIENT_HISTORY"):
            overall_trend = "BULLISH"
        elif short_term_trend == "BEARISH" and long_term_trend in ("BEARISH", "INSUFFICIENT_HISTORY"):
            overall_trend = "BEARISH"
        elif long_term_trend in ("BULLISH", "BEARISH") and abs(long_votes) >= 2 and adx is not None and adx >= 20.0:
            overall_trend = long_term_trend
        elif short_term_trend != long_term_trend and long_term_trend != "INSUFFICIENT_HISTORY":
            overall_trend = "SIDEWAYS"
        else:
            overall_trend = short_term_trend

        dist_sma50_pct = safe_float(((close - sma_50) / sma_50) * 100.0, 2) if close and sma_50 and sma_50 > 0 else None
        dist_sma200_pct = safe_float(((close - sma_200) / sma_200) * 100.0, 2) if close and sma_200 and sma_200 > 0 else None

        signals: list[str] = []
        if close and ema_20:
            signals.append(
                f"Price ({close:.2f}) is {'above' if close > ema_20 else 'below'} EMA 20 ({ema_20:.2f})."
            )
        if sma_50 and sma_200:
            signals.append(f"SMA 50 ({sma_50:.2f}) vs SMA 200 ({sma_200:.2f}): {ma_cross_status}.")
        if recent_ma_cross:
            signals.append(f"Recent major crossover detected: {recent_ma_cross}.")
        if adx is not None and di_plus is not None and di_minus is not None:
            signals.append(f"ADX (14) = {adx:.1f} ({trend_strength}), +DI={di_plus:.1f} vs -DI={di_minus:.1f}.")

        return {
            "overall_trend": overall_trend,
            "short_term_trend": short_term_trend,
            "long_term_trend": long_term_trend,
            "trend_strength": trend_strength,
            "dmi_direction": dmi_direction,
            "ma_cross_status": ma_cross_status,
            "recent_ma_cross": recent_ma_cross,
            "indicators": {
                "sma_20": sma_20,
                "sma_50": sma_50,
                "sma_200": sma_200,
                "ema_12": ema_12,
                "ema_26": ema_26,
                "ema_20": ema_20,
                "ema_50": ema_50,
                "ema_200": ema_200,
                "adx_14": adx,
                "dmi_plus_14": di_plus,
                "dmi_minus_14": di_minus,
                "ema20_5d_slope_pct": ema20_slope_pct,
                "distance_from_sma50_pct": dist_sma50_pct,
                "distance_from_sma200_pct": dist_sma200_pct,
            },
            "findings": signals,
        }

    def _analyze_momentum(self, ind_df: pd.DataFrame, latest: pd.Series, n_bars: int) -> dict[str, Any]:
        rsi = self._masked_indicator(latest.get("rsi_14"), n_bars, 20, 2)
        macd_line = self._masked_indicator(latest.get("macd_line"), n_bars, 26, 4)
        macd_signal = self._masked_indicator(latest.get("macd_signal"), n_bars, 35, 4)
        macd_diff = self._masked_indicator(latest.get("macd_diff"), n_bars, 35, 4)
        stoch_k = self._masked_indicator(latest.get("stoch_k"), n_bars, 14, 2)
        stoch_d = self._masked_indicator(latest.get("stoch_d"), n_bars, 16, 2)

        # RSI condition & 5d change
        rsi_condition = "UNAVAILABLE"
        rsi_5d_change = None
        if rsi is not None:
            if rsi >= 70.0:
                rsi_condition = "OVERBOUGHT"
            elif rsi >= 58.0:
                rsi_condition = "BULLISH_MOMENTUM"
            elif rsi <= 30.0:
                rsi_condition = "OVERSOLD"
            elif rsi <= 42.0:
                rsi_condition = "BEARISH_MOMENTUM"
            else:
                rsi_condition = "NEUTRAL"

            if n_bars >= 26:
                r_prev = safe_float(ind_df["rsi_14"].iloc[-6])
                if r_prev is not None:
                    rsi_5d_change = safe_float(rsi - r_prev, 2)

        # MACD crossovers within trailing 5 bars & histogram acceleration
        macd_state = "UNAVAILABLE"
        recent_macd_cross = None
        macd_hist_direction = None
        if macd_line is not None and macd_signal is not None and macd_diff is not None:
            macd_state = "BULLISH_ABOVE_SIGNAL" if macd_line > macd_signal else "BEARISH_BELOW_SIGNAL"
            if n_bars >= 38:
                prev_diff = safe_float(ind_df["macd_diff"].iloc[-2])
                if prev_diff is not None:
                    if macd_diff > 0 and macd_diff > prev_diff:
                        macd_hist_direction = "EXPANDING_POSITIVE"
                    elif macd_diff > 0 and macd_diff <= prev_diff:
                        macd_hist_direction = "FADING_POSITIVE"
                    elif macd_diff < 0 and macd_diff < prev_diff:
                        macd_hist_direction = "EXPANDING_NEGATIVE"
                    else:
                        macd_hist_direction = "IMPROVING_NEGATIVE"

                # Scan last 5 transitions for exact cross
                diffs = ind_df["macd_diff"].tail(6).values
                for k in range(1, len(diffs)):
                    if diffs[k - 1] <= 0 < diffs[k]:
                        cd = pd.to_datetime(ind_df["trading_date"].iloc[-(len(diffs) - k)]).date().isoformat()
                        recent_macd_cross = f"BULLISH_CROSSOVER ({cd})"
                    elif diffs[k - 1] >= 0 > diffs[k]:
                        cd = pd.to_datetime(ind_df["trading_date"].iloc[-(len(diffs) - k)]).date().isoformat()
                        recent_macd_cross = f"BEARISH_CROSSOVER ({cd})"

        # Stochastic condition
        stoch_condition = "UNAVAILABLE"
        if stoch_k is not None:
            if stoch_k >= 80.0:
                stoch_condition = "OVERBOUGHT"
            elif stoch_k <= 20.0:
                stoch_condition = "OVERSOLD"
            else:
                stoch_condition = "NEUTRAL"

        # Causal RSI divergence check between two recent halves of trailing 30 bars
        rsi_divergence = "NONE_DETECTED"
        if n_bars >= 45 and rsi is not None:
            sub = ind_df.tail(35)
            first_half = sub.iloc[:17]
            second_half = sub.iloc[17:]
            # Bullish divergence: recent 17-bar low < prior 17-bar low by >= 2%, while RSI min rose >= 3 pts
            p1_low = safe_float(first_half["close"].min())
            p2_low = safe_float(second_half["close"].min())
            r1_low = safe_float(first_half["rsi_14"].min())
            r2_low = safe_float(second_half["rsi_14"].min())
            # Bearish divergence: recent high > prior high by >= 2%, while RSI max fell >= 3 pts
            p1_high = safe_float(first_half["close"].max())
            p2_high = safe_float(second_half["close"].max())
            r1_high = safe_float(first_half["rsi_14"].max())
            r2_high = safe_float(second_half["rsi_14"].max())
            if p1_low and p2_low and r1_low and r2_low and (p2_low < p1_low * 0.98) and (r2_low > r1_low + 3.0):
                rsi_divergence = "BULLISH_DIVERGENCE"
            elif p1_high and p2_high and r1_high and r2_high and (p2_high > p1_high * 1.02) and (r2_high < r1_high - 3.0):
                rsi_divergence = "BEARISH_DIVERGENCE"

        # Aggregate momentum label
        mom_score = 0
        if rsi is not None:
            if rsi >= 70.0:
                mom_score += 1  # strong positive momentum, though overbought risk noted separately
            elif rsi >= 55.0:
                mom_score += 1
            elif rsi <= 30.0:
                mom_score -= 1
            elif rsi <= 45.0:
                mom_score -= 1
        if macd_diff is not None:
            mom_score += 1 if macd_diff > 0 else -1
        if stoch_k is not None and stoch_d is not None:
            if stoch_k > stoch_d and stoch_k > 50:
                mom_score += 1
            elif stoch_k < stoch_d and stoch_k < 50:
                mom_score -= 1

        if mom_score >= 2:
            momentum_bias = "BULLISH"
        elif mom_score <= -2:
            momentum_bias = "BEARISH"
        else:
            momentum_bias = "NEUTRAL"

        findings: list[str] = []
        if rsi is not None:
            findings.append(f"RSI (14) is {rsi:.1f} ({rsi_condition}).")
        if macd_line is not None and macd_signal is not None:
            findings.append(
                f"MACD ({macd_line:.2f}) vs Signal ({macd_signal:.2f}): {macd_state}"
                + (f", recent {recent_macd_cross}." if recent_macd_cross else ".")
            )
        if stoch_k is not None and stoch_d is not None:
            findings.append(f"Stochastic %K={stoch_k:.1f}, %D={stoch_d:.1f} ({stoch_condition}).")
        if rsi_divergence != "NONE_DETECTED":
            findings.append(f"Causal 35-day RSI pattern suggests {rsi_divergence}.")

        return {
            "momentum_bias": momentum_bias,
            "rsi_condition": rsi_condition,
            "rsi_5d_change": rsi_5d_change,
            "rsi_divergence": rsi_divergence,
            "macd_state": macd_state,
            "macd_histogram_direction": macd_hist_direction,
            "recent_macd_cross": recent_macd_cross,
            "stochastic_condition": stoch_condition,
            "indicators": {
                "rsi_14": rsi,
                "macd_line": macd_line,
                "macd_signal": macd_signal,
                "macd_diff": macd_diff,
                "stoch_k": stoch_k,
                "stoch_d": stoch_d,
            },
            "findings": findings,
        }

    def _analyze_volatility(self, ind_df: pd.DataFrame, latest: pd.Series, n_bars: int) -> dict[str, Any]:
        atr_14 = self._masked_indicator(latest.get("atr_14"), n_bars, 15, 4)
        atr_pct = self._masked_indicator(latest.get("atr_pct"), n_bars, 15, 2)
        bb_upper = self._masked_indicator(latest.get("bb_upper"), n_bars, 20, 4)
        bb_middle = self._masked_indicator(latest.get("bb_middle"), n_bars, 20, 4)
        bb_lower = self._masked_indicator(latest.get("bb_lower"), n_bars, 20, 4)
        bb_bw = self._masked_indicator(latest.get("bb_bandwidth"), n_bars, 20, 2)
        bb_pct_b = self._masked_indicator(latest.get("bb_percent_b"), n_bars, 20, 4)

        log_ret = np.log(ind_df["close"] / ind_df["close"].shift(1))
        hv_20_series = log_ret.rolling(20).std() * np.sqrt(252.0) * 100.0
        hv_60_series = log_ret.rolling(60).std() * np.sqrt(252.0) * 100.0

        hv_20 = safe_float(hv_20_series.iloc[-1], 2) if n_bars >= 21 else None
        hv_60 = safe_float(hv_60_series.iloc[-1], 2) if n_bars >= 61 else None

        # Trailing 252-bar percentile rank of 20d volatility
        vol_percentile_252d = None
        volatility_regime = "UNAVAILABLE"
        if hv_20 is not None and hv_20_series.dropna().shape[0] >= 40:
            hist_window = hv_20_series.dropna().tail(252)
            vol_percentile_252d = safe_float((hist_window <= hv_20).mean() * 100.0, 1)
            if vol_percentile_252d >= 85.0:
                volatility_regime = "HIGH_VOLATILITY"
            elif vol_percentile_252d >= 65.0:
                volatility_regime = "ELEVATED_VOLATILITY"
            elif vol_percentile_252d <= 25.0:
                volatility_regime = "LOW_VOLATILITY"
            else:
                volatility_regime = "NORMAL_VOLATILITY"

        # ATR expansion vs 20d average
        atr_trend = None
        if atr_pct is not None and n_bars >= 35:
            atr_ma20 = safe_float(ind_df["atr_pct"].tail(20).mean())
            if atr_ma20 and atr_ma20 > 0:
                if atr_pct > atr_ma20 * 1.15:
                    atr_trend = "EXPANDING"
                elif atr_pct < atr_ma20 * 0.85:
                    atr_trend = "CONTRACTING"
                else:
                    atr_trend = "STABLE"

        # Bollinger squeeze/breakout state vs trailing 126d bandwidth percentile
        bb_state = "UNAVAILABLE"
        bb_bw_percentile_126d = None
        if bb_bw is not None and bb_pct_b is not None and n_bars >= 40:
            bw_hist = ind_df["bb_bandwidth"].dropna().tail(126)
            if len(bw_hist) >= 20:
                bb_bw_percentile_126d = safe_float((bw_hist <= bb_bw).mean() * 100.0, 1)
            if bb_pct_b > 1.0:
                bb_state = "UPPER_BAND_BREAKOUT"
            elif bb_pct_b < 0.0:
                bb_state = "LOWER_BAND_BREAKDOWN"
            elif bb_bw_percentile_126d is not None and bb_bw_percentile_126d <= 20.0:
                bb_state = "BOLLINGER_SQUEEZE"
            elif bb_bw_percentile_126d is not None and bb_bw_percentile_126d >= 85.0:
                bb_state = "BAND_EXPANSION"
            else:
                bb_state = "WITHIN_BANDS"

        findings: list[str] = []
        if hv_20 is not None:
            findings.append(
                f"20-day annualized historical volatility is {hv_20:.1f}%"
                + (f" ({vol_percentile_252d:.0f}th percentile vs trailing 1Y: {volatility_regime})." if vol_percentile_252d is not None else ".")
            )
        if atr_14 is not None and atr_pct is not None:
            findings.append(f"ATR (14) = {atr_14:.2f} PKR ({atr_pct:.2f}% of close), volatility range {atr_trend or 'STABLE'}.")
        if bb_bw is not None and bb_pct_b is not None:
            findings.append(f"Bollinger Band width is {bb_bw:.2f}% with %B = {bb_pct_b:.2f} ({bb_state}).")

        return {
            "volatility_regime": volatility_regime,
            "volatility_percentile_252d": vol_percentile_252d,
            "atr_trend": atr_trend,
            "bollinger_state": bb_state,
            "bb_bandwidth_percentile_126d": bb_bw_percentile_126d,
            "indicators": {
                "historical_vol_20d_ann_pct": hv_20,
                "historical_vol_60d_ann_pct": hv_60,
                "atr_14": atr_14,
                "atr_pct": atr_pct,
                "bb_upper": bb_upper,
                "bb_middle": bb_middle,
                "bb_lower": bb_lower,
                "bb_bandwidth": bb_bw,
                "bb_percent_b": bb_pct_b,
            },
            "findings": findings,
        }

    def _analyze_volume(self, ind_df: pd.DataFrame, latest: pd.Series, n_bars: int) -> dict[str, Any]:
        vol_series = pd.to_numeric(ind_df["volume"], errors="coerce").fillna(0.0)
        latest_vol = safe_float(latest.get("volume"), 0) or 0.0
        vol_sma_20 = safe_float(vol_series.tail(20).mean(), 0) if n_bars >= 20 else None
        vol_sma_60 = safe_float(vol_series.tail(60).mean(), 0) if n_bars >= 60 else None

        vol_ratio_20 = safe_div(latest_vol, vol_sma_20, require_positive_den=True, digits=2)
        vol_ratio_60 = safe_div(latest_vol, vol_sma_60, require_positive_den=True, digits=2)

        avg_turnover_20d_pkr = None
        if n_bars >= 20:
            turnover = (ind_df["raw_close"].tail(20) * vol_series.tail(20)).mean()
            avg_turnover_20d_pkr = safe_float(turnover, 0)

        if latest_vol == 0.0:
            volume_condition = "ZERO_VOLUME"
        elif vol_ratio_20 is None:
            volume_condition = "INSUFFICIENT_HISTORY"
        elif vol_ratio_20 >= 2.0:
            volume_condition = "UNUSUAL_SURGE"
        elif vol_ratio_20 >= 1.3:
            volume_condition = "ABOVE_AVERAGE"
        elif vol_ratio_20 <= 0.6:
            volume_condition = "LOW_DRY_UP"
        else:
            volume_condition = "NORMAL"

        obv_val = safe_float(latest.get("obv"), 0)
        obv_ema_20 = safe_float(latest.get("obv_ema_20"), 0) if n_bars >= 20 else None
        obv_trend = "UNAVAILABLE"
        if obv_val is not None and obv_ema_20 is not None:
            obv_trend = "ACCUMULATION (OBV > EMA20)" if obv_val > obv_ema_20 else "DISTRIBUTION (OBV <= EMA20)"

        # Volume-price signal on latest session
        prev_close = safe_float(ind_df["close"].iloc[-2]) if n_bars >= 2 else None
        cur_close = safe_float(latest["close"])
        day_change = (cur_close - prev_close) if (cur_close and prev_close) else 0.0
        if vol_ratio_20 is not None and vol_ratio_20 >= 1.3:
            vp_confirmation = "HEAVY_VOLUME_ADVANCE" if day_change > 0 else ("HEAVY_VOLUME_DECLINE" if day_change < 0 else "HIGH_VOLUME_INDECISION")
        elif vol_ratio_20 is not None and vol_ratio_20 <= 0.6:
            vp_confirmation = "WEAK_CONVICTION_MOVE"
        else:
            vp_confirmation = "NORMAL_PARTICIPATION"

        # 20-day OBV slope vs price slope divergence check
        obv_divergence = "NONE"
        if n_bars >= 21 and "obv" in ind_df.columns:
            p_start = safe_float(ind_df["close"].iloc[-21])
            p_end = safe_float(ind_df["close"].iloc[-1])
            o_start = safe_float(ind_df["obv"].iloc[-21])
            o_end = safe_float(ind_df["obv"].iloc[-1])
            if p_start and p_end and o_start is not None and o_end is not None:
                p_chg = (p_end - p_start) / p_start
                if p_chg < -0.02 and o_end > o_start:
                    obv_divergence = "BULLISH_OBV_DIVERGENCE"
                elif p_chg > 0.02 and o_end < o_start:
                    obv_divergence = "BEARISH_OBV_DIVERGENCE"

        findings: list[str] = [
            f"Latest volume is {int(latest_vol):,} shares"
            + (f" ({vol_ratio_20:.2f}x 20-day avg of {int(vol_sma_20):,}: {volume_condition})." if vol_ratio_20 is not None and vol_sma_20 else ".")
        ]
        if obv_trend != "UNAVAILABLE":
            findings.append(f"On-Balance Volume shows {obv_trend}.")
        if obv_divergence != "NONE":
            findings.append(f"20-day volume flow divergence detected: {obv_divergence}.")
        if avg_turnover_20d_pkr is not None:
            findings.append(f"Average 20-day traded value is {avg_turnover_20d_pkr / 1e6:,.2f}M PKR/day.")

        return {
            "volume_condition": volume_condition,
            "volume_price_confirmation": vp_confirmation,
            "obv_trend": obv_trend,
            "obv_divergence": obv_divergence,
            "indicators": {
                "latest_volume": int(latest_vol),
                "volume_sma_20": int(vol_sma_20) if vol_sma_20 is not None else None,
                "volume_sma_60": int(vol_sma_60) if vol_sma_60 is not None else None,
                "volume_ratio_20d": vol_ratio_20,
                "volume_ratio_60d": vol_ratio_60,
                "avg_daily_turnover_20d_pkr": avg_turnover_20d_pkr,
                "obv": obv_val,
                "obv_ema_20": obv_ema_20,
            },
            "findings": findings,
        }

    def _analyze_candlesticks(
        self,
        ind_df: pd.DataFrame,
        symbol: str,
        flat_bar_mask: pd.Series,
    ) -> dict[str, Any]:
        # Run CandlestickPatternDetector on trailing 120 bars for speed & sufficient MA warmup
        tail_n = min(len(ind_df), 120)
        sub_df = ind_df.tail(tail_n).copy().reset_index(drop=True)
        sub_df["symbol"] = symbol
        flat_tail = flat_bar_mask.tail(tail_n).reset_index(drop=True)

        _, raw_patterns = self.pattern_detector.detect_patterns(sub_df)

        vol_sma_20 = pd.to_numeric(sub_df["volume"], errors="coerce").rolling(20, min_periods=1).mean()
        cutoff_idx = max(0, tail_n - 10)

        valid_recent: list[dict[str, Any]] = []
        suppressed_flat_count = 0
        for p in raw_patterns:
            idx = int(p.get("index", -1))
            if idx < cutoff_idx or idx >= tail_n:
                continue
            if bool(flat_tail.iloc[idx]):
                suppressed_flat_count += 1
                continue

            pname = str(p.get("pattern", ""))
            ptype = str(p.get("type", "NEUTRAL")).upper()
            v_bar = safe_float(sub_df.loc[idx, "volume"], 0) or 0.0
            v_avg = safe_float(vol_sma_20.iloc[idx], 0) or 0.0
            v_ratio = safe_div(v_bar, v_avg, require_positive_den=True, digits=2)

            if pname in _STRONG_PATTERNS:
                strength = "STRONG"
            elif pname in _MODERATE_PATTERNS:
                strength = "STRONG" if (v_ratio is not None and v_ratio >= 1.5) else "MODERATE"
            else:
                strength = "WEAK"

            bars_ago = (tail_n - 1) - idx
            p_date = pd.to_datetime(p.get("date")).date().isoformat()
            valid_recent.append(
                {
                    "date": p_date,
                    "bars_ago": bars_ago,
                    "pattern": pname,
                    "signal_type": ptype,
                    "strength": strength,
                    "volume_ratio_vs_20d": v_ratio,
                    "description": p.get("description"),
                }
            )

        # Sort most recent first
        valid_recent.sort(key=lambda x: x["bars_ago"])
        bullish_recent = [p for p in valid_recent if p["signal_type"] == "BULLISH" and p["bars_ago"] <= 5]
        bearish_recent = [p for p in valid_recent if p["signal_type"] == "BEARISH" and p["bars_ago"] <= 5]

        if len(bullish_recent) > len(bearish_recent):
            pattern_bias = "BULLISH"
        elif len(bearish_recent) > len(bullish_recent):
            pattern_bias = "BEARISH"
        elif valid_recent:
            pattern_bias = "NEUTRAL"
        else:
            pattern_bias = "NONE"

        return {
            "lookback_sessions": 10,
            "pattern_bias_5d": pattern_bias,
            "recent_patterns_count": len(valid_recent),
            "suppressed_flat_bar_patterns": suppressed_flat_count,
            "patterns": valid_recent[:10],
        }

    def _analyze_support_resistance(
        self,
        ind_df: pd.DataFrame,
        latest: pd.Series,
        n_bars: int,
    ) -> dict[str, Any]:
        """
        Identify strictly causal support and resistance zones using confirmed
        historical swing fractals (t + k <= as_of_idx), structural highs/lows,
        moving averages, and volume-weighted price clusters.
        """
        cur_close = safe_float(latest["close"], 4)
        if cur_close is None or cur_close <= 0:
            return {"support_levels": [], "resistance_levels": [], "position_in_52w_range_pct": None}

        win = ind_df.tail(min(n_bars, 252)).reset_index(drop=True)
        highs = pd.to_numeric(win["high"], errors="coerce").values
        lows = pd.to_numeric(win["low"], errors="coerce").values
        closes = pd.to_numeric(win["close"], errors="coerce").values
        vols = pd.to_numeric(win["volume"], errors="coerce").fillna(0.0).values
        dates = pd.to_datetime(win["trading_date"]).dt.date.values
        m = len(win)

        candidates: list[dict[str, Any]] = []

        # 1. Strictly confirmed swing fractals (pivot bar i requires bars i-k .. i+k all <= m-1)
        k = 3
        for i in range(k, m - k):
            window_h = highs[i - k : i + k + 1]
            window_l = lows[i - k : i + k + 1]
            if highs[i] == np.nanmax(window_h) and np.isfinite(highs[i]):
                candidates.append({"level": float(highs[i]), "weight": 2.0, "source": f"Swing High ({dates[i]})"})
            if lows[i] == np.nanmin(window_l) and np.isfinite(lows[i]):
                candidates.append({"level": float(lows[i]), "weight": 2.0, "source": f"Swing Low ({dates[i]})"})

        # 2. Structural trailing highs/lows
        for lb in (20, 60, 252):
            if m >= lb:
                sub_h = float(np.nanmax(highs[-lb:]))
                sub_l = float(np.nanmin(lows[-lb:]))
                candidates.append({"level": sub_h, "weight": 2.5 if lb == 252 else 1.5, "source": f"{lb}D Rolling High"})
                candidates.append({"level": sub_l, "weight": 2.5 if lb == 252 else 1.5, "source": f"{lb}D Rolling Low"})

        # 3. Dynamic MA levels
        if n_bars >= 50:
            s50 = safe_float(latest.get("sma_50"))
            if s50:
                candidates.append({"level": s50, "weight": 1.5, "source": "SMA 50"})
        if n_bars >= 200:
            s200 = safe_float(latest.get("sma_200"))
            if s200:
                candidates.append({"level": s200, "weight": 2.0, "source": "SMA 200"})

        # 4. Volume-weighted price cluster nodes (top 3 bins)
        valid_mask = np.isfinite(closes) & (closes > 0)
        if valid_mask.sum() >= 30 and vols[valid_mask].sum() > 0:
            p_min, p_max = float(np.min(closes[valid_mask])), float(np.max(closes[valid_mask]))
            if p_max > p_min:
                n_bins = 25
                hist_vol, edges = np.histogram(closes[valid_mask], bins=n_bins, weights=vols[valid_mask])
                top_bins = np.argsort(hist_vol)[::-1][:3]
                for b in top_bins:
                    if hist_vol[b] > 0:
                        mid_p = float((edges[b] + edges[b + 1]) / 2.0)
                        candidates.append({"level": mid_p, "weight": 1.8, "source": "High-Volume Price Cluster"})

        # Cluster candidate levels within 1.5% tolerance into unified zones
        candidates = [c for c in candidates if np.isfinite(c["level"]) and c["level"] > 0]
        candidates.sort(key=lambda x: x["level"])
        zones: list[dict[str, Any]] = []
        for cand in candidates:
            lvl = cand["level"]
            if zones and abs(lvl - zones[-1]["level"]) / zones[-1]["level"] <= 0.015:
                z = zones[-1]
                tot_w = z["weight"] + cand["weight"]
                z["level"] = (z["level"] * z["weight"] + lvl * cand["weight"]) / tot_w
                z["weight"] = tot_w
                z["confirmations"] += 1
                if cand["source"] not in z["sources"]:
                    z["sources"].append(cand["source"])
            else:
                zones.append(
                    {
                        "level": lvl,
                        "weight": cand["weight"],
                        "confirmations": 1,
                        "sources": [cand["source"]],
                    }
                )

        support_levels = []
        resistance_levels = []
        for z in zones:
            lvl = z["level"]
            dist_pct = ((lvl - cur_close) / cur_close) * 100.0
            entry = {
                "level_pkr": safe_float(lvl, 2),
                "distance_pct": safe_float(dist_pct, 2),
                "confirmations": int(z["confirmations"]),
                "strength_score": safe_float(z["weight"], 1),
                "sources": z["sources"][:3],
            }
            if lvl < cur_close * 0.995:
                support_levels.append(entry)
            elif lvl > cur_close * 1.005:
                resistance_levels.append(entry)

        # Nearest levels first
        support_levels.sort(key=lambda x: x["level_pkr"], reverse=True)
        resistance_levels.sort(key=lambda x: x["level_pkr"])

        high_52w = float(np.nanmax(highs))
        low_52w = float(np.nanmin(lows))
        pos_52w = safe_float(((cur_close - low_52w) / (high_52w - low_52w)) * 100.0, 1) if high_52w > low_52w else None

        return {
            "methodology": "Causal pivot fractals (k=3 confirmed <= as_of_date), trailing rolling extrema, SMAs, and volume clusters",
            "support_levels": support_levels[:4],
            "resistance_levels": resistance_levels[:4],
            "nearest_support_pkr": support_levels[0]["level_pkr"] if support_levels else None,
            "nearest_support_distance_pct": support_levels[0]["distance_pct"] if support_levels else None,
            "nearest_resistance_pkr": resistance_levels[0]["level_pkr"] if resistance_levels else None,
            "nearest_resistance_distance_pct": resistance_levels[0]["distance_pct"] if resistance_levels else None,
            "trailing_252d_high_pkr": safe_float(high_52w, 2),
            "trailing_252d_low_pkr": safe_float(low_52w, 2),
            "position_in_252d_range_pct": pos_52w,
        }

    def _analyze_hmm_context(
        self,
        conn: Connection,
        cal_df: pd.DataFrame,
        ind_df: pd.DataFrame,
        mkt_cutoff: date,
    ) -> dict[str, Any]:
        """
        Estimate causal filtered market regime P(S_t | X_{1:t}) via CausalMarketRegimeHMM
        and relate stock returns to KSE-100 market sensitivity.
        """
        idx_df = cal_df.copy()
        idx_dates = pd.to_datetime(idx_df["trading_date"]).dt.date
        train_cutoff = min(mkt_cutoff, HMM_DEFAULT_TRAIN_END)
        cache_key = (train_cutoff.isoformat(), mkt_cutoff.isoformat(), len(idx_df))

        if cache_key in self._hmm_cache:
            reg_df = self._hmm_cache[cache_key]
        else:
            train_slice = idx_df[idx_dates <= train_cutoff].copy()
            if len(train_slice) < 252:
                train_slice = idx_df.copy()
            hmm = CausalMarketRegimeHMM(n_states=3, random_state=42)
            hmm.fit(train_slice)
            reg_df = hmm.filter_causal_probabilities(idx_df)
            self._hmm_cache[cache_key] = reg_df

        latest_reg = reg_df.iloc[-1]

        # Compute stock trailing 60-day beta and correlation vs KSE-100 on aligned trading dates
        stock_ret = ind_df[["trading_date", "close"]].copy()
        stock_ret["trading_date"] = pd.to_datetime(stock_ret["trading_date"]).dt.date
        stock_ret["stk_ret"] = stock_ret["close"].pct_change()

        mkt_ret = idx_df[["trading_date", "close"]].copy()
        mkt_ret["trading_date"] = pd.to_datetime(mkt_ret["trading_date"]).dt.date
        mkt_ret["mkt_ret"] = pd.to_numeric(mkt_ret["close"], errors="coerce").pct_change()

        joined = pd.merge(stock_ret[["trading_date", "stk_ret"]], mkt_ret[["trading_date", "mkt_ret"]], on="trading_date", how="inner").dropna()
        beta_60d = None
        corr_60d = None
        if len(joined) >= 20:
            tail60 = joined.tail(min(len(joined), 60))
            mkt_var = float(tail60["mkt_ret"].var())
            if mkt_var > 0:
                cov = float(tail60[["stk_ret", "mkt_ret"]].cov().iloc[0, 1])
                beta_60d = safe_float(cov / mkt_var, 2)
            corr_val = safe_float(tail60["stk_ret"].corr(tail60["mkt_ret"]), 2)
            corr_60d = corr_val

        return {
            "market_index": "KSE100",
            "hmm_train_cutoff": train_cutoff.isoformat(),
            "regime_date": pd.to_datetime(latest_reg["trading_date"]).date().isoformat(),
            "market_regime": str(latest_reg["hmm_mkt_regime_label"]),
            "probabilities": {
                "bullish": safe_float(latest_reg["hmm_mkt_prob_bullish"], 4),
                "sideways": safe_float(latest_reg["hmm_mkt_prob_sideways"], 4),
                "bearish": safe_float(latest_reg["hmm_mkt_prob_bearish"], 4),
            },
            "regime_duration_sessions": int(safe_float(latest_reg["hmm_mkt_regime_duration"], 0) or 1),
            "regime_entropy": safe_float(latest_reg["hmm_mkt_entropy"], 4),
            "stock_vs_market_60d_beta": beta_60d,
            "stock_vs_market_60d_correlation": corr_60d,
            "leakage_policy": "Strict forward-only filtered P(S_t | X_{1:t}); zero Viterbi/backward smoothing.",
        }

    def _synthesize_assessment(
        self,
        *,
        trend: dict[str, Any],
        momentum: dict[str, Any],
        volatility: dict[str, Any],
        volume: dict[str, Any],
        candlesticks: dict[str, Any],
        support_resistance: dict[str, Any],
        hmm_context: dict[str, Any],
        n_bars: int,
        staleness_cal_days: int,
        price_audit: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Compute transparent deterministic technical bias score in [-100, +100]
        and collect explicit bullish, bearish, and conflicting signals.
        """
        bullish_signals: list[str] = []
        bearish_signals: list[str] = []
        conflicting_signals: list[str] = []

        t_ind = trend["indicators"]
        m_ind = momentum["indicators"]
        v_ind = volume["indicators"]

        # 1. Trend sub-score [-100, +100], weight 0.35
        trend_pts = 0.0
        if trend["short_term_trend"] == "BULLISH":
            trend_pts += 40.0
            bullish_signals.append("Short-term moving averages (EMA 12/26 & EMA 20) are aligned bullishly.")
        elif trend["short_term_trend"] == "BEARISH":
            trend_pts -= 40.0
            bearish_signals.append("Short-term moving averages reflect downward pressure below EMA 20.")

        if trend["long_term_trend"] == "BULLISH":
            trend_pts += 40.0
            bullish_signals.append("Long-term trend structure is bullish (above SMA 50/200).")
        elif trend["long_term_trend"] == "BEARISH":
            trend_pts -= 40.0
            bearish_signals.append("Long-term trend structure is bearish (below SMA 50/200).")

        adx = t_ind.get("adx_14")
        di_dir = trend.get("dmi_direction")
        if adx is not None and adx >= 20.0:
            if di_dir == "BULLISH_DI":
                trend_pts += 20.0
            elif di_dir == "BEARISH_DI":
                trend_pts -= 20.0
        trend_sub = max(-100.0, min(100.0, trend_pts))

        # 2. Momentum sub-score [-100, +100], weight 0.25
        mom_pts = 0.0
        rsi = m_ind.get("rsi_14")
        if rsi is not None:
            if rsi >= 70.0:
                mom_pts += 15.0  # strong upside trend momentum, capped due to overbought exhaustion risk
                conflicting_signals.append(
                    f"RSI (14) at {rsi:.1f} signals strong upside momentum but enters Overbought (>= 70) exhaustion territory."
                )
            elif rsi >= 55.0:
                mom_pts += 40.0
                bullish_signals.append(f"RSI (14) at {rsi:.1f} reflects constructive bullish momentum.")
            elif rsi <= 30.0:
                mom_pts -= 15.0
                conflicting_signals.append(
                    f"RSI (14) at {rsi:.1f} is Oversold (<= 30), signaling heavy selling pressure alongside mean-reversion risk."
                )
            elif rsi <= 45.0:
                mom_pts -= 40.0
                bearish_signals.append(f"RSI (14) at {rsi:.1f} indicates weak/bearish momentum.")

        macd_diff = m_ind.get("macd_diff")
        if macd_diff is not None:
            if macd_diff > 0:
                mom_pts += 35.0
                bullish_signals.append("MACD line sits above its Signal line (positive histogram).")
            else:
                mom_pts -= 35.0
                bearish_signals.append("MACD line remains below its Signal line (negative histogram).")

        if momentum.get("recent_macd_cross"):
            if "BULLISH" in momentum["recent_macd_cross"]:
                mom_pts += 15.0
                bullish_signals.append(f"Recent MACD {momentum['recent_macd_cross']}.")
            else:
                mom_pts -= 15.0
                bearish_signals.append(f"Recent MACD {momentum['recent_macd_cross']}.")

        if momentum.get("rsi_divergence") == "BULLISH_DIVERGENCE":
            mom_pts += 10.0
            bullish_signals.append("Bullish 35-day RSI divergence observed (higher momentum lows on lower prices).")
        elif momentum.get("rsi_divergence") == "BEARISH_DIVERGENCE":
            mom_pts -= 10.0
            bearish_signals.append("Bearish 35-day RSI divergence observed (lower momentum peaks on higher prices).")
        mom_sub = max(-100.0, min(100.0, mom_pts))

        # 3. Volume sub-score [-100, +100], weight 0.15
        vol_pts = 0.0
        if "ACCUMULATION" in (volume.get("obv_trend") or ""):
            vol_pts += 50.0
            bullish_signals.append("OBV stands above its 20-day EMA, indicating net accumulation.")
        elif "DISTRIBUTION" in (volume.get("obv_trend") or ""):
            vol_pts -= 50.0
            bearish_signals.append("OBV sits below its 20-day EMA, indicating net distribution.")

        vp_conf = volume.get("volume_price_confirmation")
        if vp_conf == "HEAVY_VOLUME_ADVANCE":
            vol_pts += 35.0
            bullish_signals.append(f"Latest gain occurred on elevated volume ({v_ind.get('volume_ratio_20d')}x 20-day average).")
        elif vp_conf == "HEAVY_VOLUME_DECLINE":
            vol_pts -= 35.0
            bearish_signals.append(f"Latest decline occurred on elevated volume ({v_ind.get('volume_ratio_20d')}x 20-day average).")

        if volume.get("obv_divergence") == "BULLISH_OBV_DIVERGENCE":
            vol_pts += 15.0
            bullish_signals.append("20-day OBV rising despite softer price action (bullish accumulation divergence).")
        elif volume.get("obv_divergence") == "BEARISH_OBV_DIVERGENCE":
            vol_pts -= 15.0
            bearish_signals.append("20-day OBV falling despite price gains (bearish volume divergence).")
        vol_sub = max(-100.0, min(100.0, vol_pts))

        # 4. Candlestick & S/R proximity sub-score [-100, +100], weight 0.10
        pat_pts = 0.0
        for p in candlesticks.get("patterns", []):
            if p["bars_ago"] <= 3:
                w = 45.0 if p["strength"] == "STRONG" else (25.0 if p["strength"] == "MODERATE" else 0.0)
                if p["signal_type"] == "BULLISH" and w > 0:
                    pat_pts += w
                    bullish_signals.append(f"Candlestick pattern: {p['pattern']} ({p['strength']}, {p['date']}).")
                elif p["signal_type"] == "BEARISH" and w > 0:
                    pat_pts -= w
                    bearish_signals.append(f"Candlestick pattern: {p['pattern']} ({p['strength']}, {p['date']}).")
        near_sup = support_resistance.get("nearest_support_distance_pct")
        near_res = support_resistance.get("nearest_resistance_distance_pct")
        if near_sup is not None and abs(near_sup) <= 2.0:
            pat_pts += 20.0
        if near_res is not None and near_res <= 2.0:
            pat_pts -= 20.0
            conflicting_signals.append(
                f"Price is within {near_res:.1f}% below causal resistance ({support_resistance.get('nearest_resistance_pkr')} PKR)."
            )
        pat_sub = max(-100.0, min(100.0, pat_pts))

        # 5. HMM Market Regime sub-score [-100, +100], weight 0.15
        probs = hmm_context["probabilities"]
        hmm_sub = ((probs.get("bullish") or 0.0) - (probs.get("bearish") or 0.0)) * 100.0
        mkt_regime = hmm_context["market_regime"]
        if mkt_regime == "BULLISH":
            bullish_signals.append(
                f"KSE-100 HMM filtered regime is BULLISH (P={probs['bullish']:.2f}, duration {hmm_context['regime_duration_sessions']}d)."
            )
        elif mkt_regime == "BEARISH":
            bearish_signals.append(
                f"KSE-100 HMM filtered regime is BEARISH (P={probs['bearish']:.2f}, duration {hmm_context['regime_duration_sessions']}d)."
            )

        # Explicit conflict detection across pillars
        if trend["short_term_trend"] == "BULLISH" and trend["long_term_trend"] == "BEARISH":
            conflicting_signals.append("Short-term trend turned BULLISH while long-term primary trend (SMA 50/200) remains BEARISH.")
        elif trend["short_term_trend"] == "BEARISH" and trend["long_term_trend"] == "BULLISH":
            conflicting_signals.append("Short-term pullback is BEARISH inside an intact long-term BULLISH primary trend.")

        if trend["overall_trend"] == "BULLISH" and "DISTRIBUTION" in (volume.get("obv_trend") or ""):
            conflicting_signals.append("Bullish price trend lacks OBV accumulation confirmation (OBV <= EMA 20).")
        elif trend["overall_trend"] == "BEARISH" and "ACCUMULATION" in (volume.get("obv_trend") or ""):
            conflicting_signals.append("Price trend is bearish while cumulative OBV indicates institutional accumulation.")

        if trend["overall_trend"] == "BULLISH" and mkt_regime == "BEARISH":
            conflicting_signals.append("Stock displays bullish technicals against a BEARISH KSE-100 HMM market regime.")
        elif trend["overall_trend"] == "BEARISH" and mkt_regime == "BULLISH":
            conflicting_signals.append("Stock trails with bearish technicals despite a BULLISH KSE-100 HMM market regime.")

        if staleness_cal_days > 5:
            conflicting_signals.append(
                f"Liquidity/staleness caution: latest traded session was {staleness_cal_days} calendar days before cutoff."
            )
        if n_bars < 200:
            conflicting_signals.append(
                f"Limited history ({n_bars} clean trading days < 200): SMA/EMA 200 long-term trend omitted."
            )
        if candlesticks["suppressed_flat_bar_patterns"] > 0:
            conflicting_signals.append(
                f"{candlesticks['suppressed_flat_bar_patterns']} candidate candlestick signals on flat EOD-only bars (High==Low) were excluded."
            )
        if price_audit.get("weekend_phantom_rows_excluded", 0) > 0:
            conflicting_signals.append(
                f"{price_audit['weekend_phantom_rows_excluded']} weekend phantom feed rows were stripped before indicator calculation."
            )

        weights = {
            "trend_structure": 0.35,
            "momentum_signals": 0.25,
            "volume_flow": 0.15,
            "candlestick_and_levels": 0.10,
            "hmm_market_regime": 0.15,
        }
        composite = (
            weights["trend_structure"] * trend_sub
            + weights["momentum_signals"] * mom_sub
            + weights["volume_flow"] * vol_sub
            + weights["candlestick_and_levels"] * pat_sub
            + weights["hmm_market_regime"] * hmm_sub
        )
        technical_score = safe_float(composite, 1)

        if technical_score >= 45.0:
            assessment = "STRONG_BULLISH"
        elif technical_score >= 15.0:
            assessment = "BULLISH"
        elif technical_score <= -45.0:
            assessment = "STRONG_BEARISH"
        elif technical_score <= -15.0:
            assessment = "BEARISH"
        else:
            assessment = "NEUTRAL"

        summary = (
            f"Technical stance is {assessment} (score {technical_score:+.1f}/100): "
            f"{trend['overall_trend']} primary trend ({trend['trend_strength']} strength), "
            f"{momentum['momentum_bias']} momentum (RSI {rsi if rsi is not None else 'N/A'}), "
            f"{volatility['volatility_regime']} volatility, under a {mkt_regime} KSE-100 HMM regime."
        )

        return {
            "bullish_signals": bullish_signals,
            "bearish_signals": bearish_signals,
            "conflicting_signals": conflicting_signals,
            "overall_assessment": assessment,
            "technical_score": technical_score,
            "summary": summary,
            "score_methodology": {
                "scale": "[-100.0, +100.0] deterministic weighted composite",
                "weights": weights,
                "component_scores": {
                    "trend_structure": safe_float(trend_sub, 1),
                    "momentum_signals": safe_float(mom_sub, 1),
                    "volume_flow": safe_float(vol_sub, 1),
                    "candlestick_and_levels": safe_float(pat_sub, 1),
                    "hmm_market_regime": safe_float(hmm_sub, 1),
                },
                "rating_bands": {
                    "STRONG_BULLISH": ">= +45",
                    "BULLISH": "[+15, +45)",
                    "NEUTRAL": "(-15, +15)",
                    "BEARISH": "(-45, -15]",
                    "STRONG_BEARISH": "<= -45",
                },
            },
        }

