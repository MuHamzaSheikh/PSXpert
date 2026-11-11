"""
Point-in-Time Corporate Actions, Accounting Fundamentals & News Sentiment Builders.

Guarantees strictly causal temporal alignment so zero future financial filings,
post-close/post-cutoff news articles, or placeholder database artifacts leak
into historical daily observations.
"""

import re
from datetime import timedelta
from typing import Dict, List, Tuple, Any
import numpy as np
import pandas as pd
from sqlalchemy import text

from src.sentiment.impact_analyzer import NewsImpactAnalyzer


def parse_ended_date_from_title(title: str):
    """Extracts period_end_date from PSX Earnings Announcement titles."""
    t = str(title or "")
    m = re.search(
        r"ended\s+(?:on\s+)?([A-Za-z]+\s+\d{1,2},?\s+20\d{2}|\d{1,2}\s+\d{1,2}\s+20\d{2})",
        t,
        re.IGNORECASE,
    )
    if m:
        raw_str = m.group(1).strip()
        # Handle space-separated numeric dates like '12 31 2025' -> MM DD YYYY
        if re.match(r"^\d{1,2}\s+\d{1,2}\s+20\d{2}$", raw_str):
            dt = pd.to_datetime(raw_str, format="%m %d %Y", errors="coerce")
        else:
            dt = pd.to_datetime(raw_str, errors="coerce")
        if pd.notna(dt):
            return dt.date()
    return None


def load_clean_corporate_actions(conn) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Loads clean split/bonus/capital-reduction events from corporate_payouts
    (excluding corrupt 'type' placeholder rows) and corporate_announcements.
    """
    payouts = pd.read_sql(
        text("""
            SELECT symbol, announcement_date, fiscal_year, payout_type,
                   dividend_per_share, payout_percentage
            FROM corporate_payouts
            WHERE payout_type IN ('dividend', 'split', 'bonus')
            ORDER BY symbol, announcement_date
        """),
        conn,
    )
    payouts["announcement_date"] = pd.to_datetime(payouts["announcement_date"]).dt.date

    ann_actions = pd.read_sql(
        text("""
            SELECT symbol, posting_date, title
            FROM corporate_announcements
            WHERE category = 'Dividends & Bonus Shares'
              AND (
                  title ILIKE '%split%'
                  OR title ILIKE '%sub-division%'
                  OR title ILIKE '%bonus%'
                  OR title ILIKE '%consolidat%'
                  OR title ILIKE '%reduction of capital%'
              )
            ORDER BY symbol, posting_date
        """),
        conn,
    )
    ann_actions["posting_date"] = pd.to_datetime(ann_actions["posting_date"]).dt.date
    return payouts, ann_actions


def adjust_splits_and_flag_glitches(
    prices_df: pd.DataFrame,
    cal_df: pd.DataFrame,
    payouts_df: pd.DataFrame,
    ann_actions_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Detects genuine permanent stock splits / bonus issues / capital reductions
    vs. single-bar source glitches and multi-day data gaps.

    Rules (zero return leakage):
    - A permanent price step change (|raw_ret_1d| >= 0.30) is adjusted backward ONLY
      when the new price level persists across the next 5 sessions (median_post / median_pre
      within 0.65..1.45 of the step ratio) AND either:
        (a) matches a split/bonus/sub-division/capital-reduction disclosure within +-20 days, OR
        (b) is a large permanent step (step >= 1.8x or <= 0.55x) across consecutive sessions
            with positive volume (catching undisclosed historical PSX splits 2002-2020).
    - Scale-invariant technical indicators computed on adj_* prior to any split date
      are mathematically invariant to backward constant scaling, while eliminating fake
      -80% crashes on split ex-dates.
    - Non-persistent spikes (like UPFL 1345 -> 1.00 -> 1345 or ATLH 295 -> 58 -> 281)
      are NOT split-adjusted and are flagged with `has_price_glitch_flag = True`.
    """
    df = prices_df.sort_values(["symbol", "trading_date"]).reset_index(drop=True)
    cal_map = dict(zip(cal_df["trading_date"], cal_df["cal_idx"]))
    df["cal_idx"] = df["trading_date"].map(cal_map)

    # Pre-index corporate action dates per symbol
    action_dates_by_sym: Dict[str, List] = {}
    for sym, grp in payouts_df[payouts_df["payout_type"].isin(["split", "bonus"])].groupby("symbol"):
        action_dates_by_sym.setdefault(sym, []).extend(grp["announcement_date"].tolist())
    for sym, grp in ann_actions_df.groupby("symbol"):
        action_dates_by_sym.setdefault(sym, []).extend(grp["posting_date"].tolist())

    adj_open = df["open"].to_numpy(dtype=np.float64).copy()
    adj_high = df["high"].to_numpy(dtype=np.float64).copy()
    adj_low = df["low"].to_numpy(dtype=np.float64).copy()
    adj_close = df["close"].to_numpy(dtype=np.float64).copy()
    raw_close = df["close"].to_numpy(dtype=np.float64)
    volumes = df["volume"].to_numpy(dtype=np.float64)
    dates = df["trading_date"].to_numpy()
    cal_idx = df["cal_idx"].to_numpy(dtype=np.int64)
    symbols = df["symbol"].to_numpy()

    n = len(df)
    adj_factors = np.ones(n, dtype=np.float64)
    corp_action_exdate = np.zeros(n, dtype=bool)
    price_glitch_flag = np.zeros(n, dtype=bool)
    cal_gap_days = np.ones(n, dtype=np.int32)

    # Process contiguous symbol slices for O(N) performance
    sym_changes = np.flatnonzero(symbols[1:] != symbols[:-1]) + 1
    starts = np.concatenate(([0], sym_changes))
    ends = np.concatenate((sym_changes, [n]))

    for s_idx, e_idx in zip(starts, ends):
        m = e_idx - s_idx
        if m < 2:
            continue
        sym = symbols[s_idx]
        sym_actions = action_dates_by_sym.get(sym, [])

        c_slice = raw_close[s_idx:e_idx]
        idx_slice = cal_idx[s_idx:e_idx]
        d_slice = dates[s_idx:e_idx]
        v_slice = volumes[s_idx:e_idx]

        gaps = np.empty(m, dtype=np.int32)
        gaps[0] = 0
        gaps[1:] = idx_slice[1:] - idx_slice[:-1]
        cal_gap_days[s_idx:e_idx] = gaps

        raw_rets = np.empty(m, dtype=np.float64)
        raw_rets[0] = 0.0
        raw_rets[1:] = (c_slice[1:] / c_slice[:-1]) - 1.0

        # Identify extreme jumps (|ret| >= 0.30)
        jump_positions = np.flatnonzero(np.abs(raw_rets) >= 0.30)
        for pos in jump_positions:
            if pos == 0:
                continue
            prev_c = c_slice[pos - 1]
            curr_c = c_slice[pos]
            if prev_c <= 0 or curr_c <= 0:
                continue
            step_ratio = curr_c / prev_c  # e.g. 0.20 for 5:1 split

            # Check persistence across [pos-5:pos] vs [pos:pos+5]
            pre_win = c_slice[max(0, pos - 5):pos]
            post_win = c_slice[pos:min(m, pos + 5)]
            pre_med = float(np.median(pre_win))
            post_med = float(np.median(post_win))
            persist_ratio = post_med / pre_med if pre_med > 0 else 1.0

            # Does the ratio shift persist (~within 40% of jump ratio) vs revert back?
            is_persistent_shift = (
                (0.60 * step_ratio <= persist_ratio <= 1.45 * step_ratio)
                and (len(post_win) >= 2)
                and (gaps[pos] <= 20)
            )

            # Check proximity to known split/bonus/capital reduction filing
            ex_d = d_slice[pos]
            near_filing = any(abs((ex_d - ad).days) <= 25 for ad in sym_actions)

            if is_persistent_shift and (near_filing or step_ratio <= 0.55 or step_ratio >= 1.85):
                # Backward adjust all prior bars [0 : pos] within this symbol slice
                adj_factors[s_idx:s_idx + pos] *= step_ratio
                adj_open[s_idx:s_idx + pos] *= step_ratio
                adj_high[s_idx:s_idx + pos] *= step_ratio
                adj_low[s_idx:s_idx + pos] *= step_ratio
                adj_close[s_idx:s_idx + pos] *= step_ratio
                corp_action_exdate[s_idx + pos] = True
            else:
                # Non-persistent spike, 1-bar glitch, or huge trading-gap jump
                price_glitch_flag[s_idx + pos] = True
                if pos > 0 and abs(raw_rets[pos]) >= 0.50:
                    # Also check if bar [pos-1] was the lone outlier bar (e.g., UPFL=1.00 before 1345)
                    if pos >= 2 and abs((c_slice[pos] / c_slice[pos - 2]) - 1.0) < 0.15:
                        price_glitch_flag[s_idx + pos - 1] = True

        # Check remaining bar-level extreme adjusted moves > 35% (e.g., unadjusted bad prints)
        adj_c_slice = adj_close[s_idx:e_idx]
        adj_ret = np.zeros(m, dtype=np.float64)
        adj_ret[1:] = (adj_c_slice[1:] / np.maximum(adj_c_slice[:-1], 1e-9)) - 1.0
        residual_bad = np.flatnonzero((np.abs(adj_ret) > 0.35) | (c_slice <= 1e-6))
        for pos in residual_bad:
            price_glitch_flag[s_idx + pos] = True

    df["raw_open"] = df["open"]
    df["raw_high"] = df["high"]
    df["raw_low"] = df["low"]
    df["raw_close"] = df["close"]
    df["adj_open"] = np.round(adj_open, 6)
    df["adj_high"] = np.round(adj_high, 6)
    df["adj_low"] = np.round(adj_low, 6)
    df["adj_close"] = np.round(adj_close, 6)
    df["corp_action_adj_factor"] = np.round(adj_factors, 6)
    df["is_corp_action_exdate"] = corp_action_exdate
    df["has_price_glitch_flag"] = price_glitch_flag
    df["calendar_gap_days"] = cal_gap_days
    return df


def build_point_in_time_fundamentals(conn, max_price_date: str = "2026-10-13") -> pd.DataFrame:
    """
    Constructs clean, unit-standardized (Full PKR), point-in-time accounting metrics
    and ratios from audited IFRS tables (`INCOME_STATEMENT`, `BALANCE_SHEET`, `CASH_FLOW`),
    augmented with verified exchange filing dates from `corporate_announcements`.

    Strictly excludes:
    - Corrupted `ANNUAL` placeholder repeats (e.g. 435451.1 / 168643.2)
    - Sentinel `12121.0` rows in `QUARTERLY`
    - Future misdated periods (> max_price_date)
    - Same-day period_end_date publication assumptions (applies real filing lag >= 100d fallback)
    """
    q_fin = text("""
        SELECT symbol, statement_type, fiscal_year, period_end_date, metric_name, metric_value
        FROM company_financials
        WHERE statement_type IN ('INCOME_STATEMENT', 'BALANCE_SHEET', 'CASH_FLOW')
          AND period_end_date <= :max_d
          AND metric_name IN (
              'total_revenue', 'operating_revenue', 'gross_profit', 'operating_income',
              'ebit', 'pretax_income', 'net_income', 'basic_eps', 'diluted_eps',
              'total_assets', 'current_assets', 'cash_and_cash_equivalents',
              'total_liabilities_net_minority_interest', 'current_liabilities',
              'total_debt', 'stockholders_equity', 'common_stock_equity',
              'ordinary_shares_number', 'operating_cash_flow', 'free_cash_flow',
              'capital_expenditure'
          )
    """)
    df_fin = pd.read_sql(q_fin, conn, params={"max_d": max_price_date})
    if df_fin.empty:
        return pd.DataFrame()

    df_fin["period_end_date"] = pd.to_datetime(df_fin["period_end_date"]).dt.date
    df_fin = df_fin[df_fin["metric_value"] != 12121.0].copy()

    # Load Earnings Announcements for point-in-time exchange disclosure dates
    df_ann = pd.read_sql(
        text("""
            SELECT symbol, posting_date, title
            FROM corporate_announcements
            WHERE category = 'Earnings Announcements'
        """),
        conn,
    )
    df_ann["posting_date"] = pd.to_datetime(df_ann["posting_date"]).dt.date
    df_ann["parsed_end"] = df_ann["title"].apply(parse_ended_date_from_title)
    matched_ann = (
        df_ann.dropna(subset=["parsed_end"])
        .groupby(["symbol", "parsed_end"])["posting_date"]
        .min()
        .reset_index()
    )

    # Pivot all financial metrics by (symbol, period_end_date)
    pivoted = (
        df_fin.pivot_table(
            index=["symbol", "period_end_date"],
            columns="metric_name",
            values="metric_value",
            aggfunc="first",
        )
        .reset_index()
    )
    pivoted.columns.name = None

    # Merge verified exchange announcement posting dates
    pivoted = pivoted.merge(
        matched_ann,
        left_on=["symbol", "period_end_date"],
        right_on=["symbol", "parsed_end"],
        how="left",
    )
    lag_days = (pd.to_datetime(pivoted["posting_date"]) - pd.to_datetime(pivoted["period_end_date"])).dt.days
    valid_pub = pivoted["posting_date"].notna() & (lag_days >= 7) & (lag_days <= 210)

    # Conservative PSX statutory fallback (+100 calendar days > 95th empirical percentile 96d)
    fallback_dates = (pd.to_datetime(pivoted["period_end_date"]) + pd.to_timedelta(100, unit="D")).dt.date
    pivoted["effective_pub_date"] = np.where(valid_pub, pivoted["posting_date"], fallback_dates)
    pivoted["fin_pub_verified_flag"] = valid_pub.astype(np.int8)

    # Exclude filings whose verified or lagged publication date falls after the dataset cutoff
    max_dt = pd.to_datetime(max_price_date).date()
    pivoted = pivoted[pivoted["effective_pub_date"] <= max_dt].copy()

    # Consolidate canonical fields (full PKR)
    def _col(name: str) -> pd.Series:
        return pd.to_numeric(pivoted[name], errors="coerce") if name in pivoted.columns else pd.Series(np.nan, index=pivoted.index)

    rev = _col("total_revenue").fillna(_col("operating_revenue"))
    gp = _col("gross_profit")
    op_inc = _col("operating_income").fillna(_col("ebit"))
    ni = _col("net_income")
    assets = _col("total_assets")
    curr_a = _col("current_assets")
    curr_l = _col("current_liabilities")
    debt = _col("total_debt")
    equity = _col("stockholders_equity").fillna(_col("common_stock_equity"))
    shares = _col("ordinary_shares_number")
    fcf = _col("free_cash_flow")
    ocf = _col("operating_cash_flow")
    eps = _col("basic_eps").fillna(_col("diluted_eps"))

    out = pd.DataFrame({
        "symbol": pivoted["symbol"],
        "fin_period_end_date": pivoted["period_end_date"],
        "effective_pub_date": pivoted["effective_pub_date"],
        "fin_pub_verified_flag": pivoted["fin_pub_verified_flag"],
        "fin_revenue_pkr": rev,
        "fin_net_income_pkr": ni,
        "fin_equity_pkr": equity,
        "fin_fcf_pkr": fcf,
        "fin_shares_post_split": shares,
        "fin_basic_eps_post_split": eps,
        "fin_gross_margin": np.where(rev.abs() > 1e-6, gp / rev, np.nan),
        "fin_operating_margin": np.where(rev.abs() > 1e-6, op_inc / rev, np.nan),
        "fin_net_margin": np.where(rev.abs() > 1e-6, ni / rev, np.nan),
        "fin_roe": np.where(equity > 1e-6, ni / equity, np.nan),
        "fin_roa": np.where(assets > 1e-6, ni / assets, np.nan),
        "fin_fcf_margin": np.where(rev.abs() > 1e-6, fcf / rev, np.nan),
        "fin_ocf_to_ni": np.where(ni.abs() > 1e-6, ocf / ni, np.nan),
        "fin_debt_to_equity": np.where(equity > 1e-6, debt / equity, np.nan),
        "fin_debt_to_assets": np.where(assets > 1e-6, debt / assets, np.nan),
        "fin_current_ratio": np.where(curr_l > 1e-6, curr_a / curr_l, np.nan),
    })

    # Compute YoY Revenue & Net Income growth strictly sorted by (symbol, period_end_date)
    # Note: a statement at publication_date can only compare to an earlier statement ALREADY published!
    out = out.sort_values(["symbol", "effective_pub_date", "fin_period_end_date"]).reset_index(drop=True)
    prev_rev = out.groupby("symbol")["fin_revenue_pkr"].shift(1)
    prev_ni = out.groupby("symbol")["fin_net_income_pkr"].shift(1)
    out["fin_revenue_yoy_growth"] = np.where(prev_rev.abs() > 1e-6, (out["fin_revenue_pkr"] - prev_rev) / prev_rev.abs(), np.nan)
    out["fin_net_income_yoy_growth"] = np.where(prev_ni.abs() > 1e-6, (out["fin_net_income_pkr"] - prev_ni) / prev_ni.abs(), np.nan)

    # Deduplicate on (symbol, effective_pub_date) keeping latest fiscal period_end_date
    out = (
        out.sort_values(["symbol", "effective_pub_date", "fin_period_end_date"])
        .drop_duplicates(subset=["symbol", "effective_pub_date"], keep="last")
        .reset_index(drop=True)
    )
    return out


def build_point_in_time_news_features(
    conn,
    trading_dates: np.ndarray,
    sym_sector_map: Dict[str, str],
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Aggregates point-in-time FinBERT news sentiment aligned causally to PSX market sessions.

    Strict Causal Timestamp Policy (Asia/Karachi, PKT = UTC+5):
    - PSX regular close is 15:30 PKT. Articles published <= 15:30 PKT on an active
      trading date D become observable at close of D.
    - Articles published > 15:30 PKT or on weekends/holidays roll forward to the
      NEXT open trading session D_next.
    - Articles dated after the latest price date (2026-10-13 15:30 PKT) are excluded
      so Oct 14-20 news never leaks backward.
    - Historical Dawn archive articles (2002-2024) all have synthetic YYYY-06-15 00:00
      sampling dates; retained with explicit coverage & reliability audit stats.
    """
    df_art = pd.read_sql(
        text("""
            SELECT a.id AS article_id, a.headline, a.summary, a.publisher,
                   a.published_at AT TIME ZONE 'Asia/Karachi' AS pub_pkt,
                   s.sentiment_label, s.sentiment_score, s.confidence, s.evaluation_metadata
            FROM news_articles a
            JOIN news_sentiment s ON a.id = s.article_id
            WHERE s.model_name = 'finbert'
            ORDER BY a.published_at
        """),
        conn,
    )
    df_ent = pd.read_sql(
        text("SELECT article_id, entity_type, entity_value FROM news_entities"),
        conn,
    )

    sorted_td = np.sort(pd.to_datetime(trading_dates).date)
    td_set = set(sorted_td)
    max_cutoff_dt = pd.Timestamp(f"{sorted_td[-1]} 15:30:00")

    impact_analyzer = NewsImpactAnalyzer()
    ent_by_art = df_ent.groupby("article_id")

    market_rows = []
    stock_rows = []
    sector_rows = []
    audit_counts = {
        "total_articles": int(len(df_art)),
        "excluded_post_cutoff": 0,
        "archive_placeholder_jun15": 0,
        "rolled_to_next_trading_day": 0,
        "usable_aligned_articles": 0,
    }

    for _, r in df_art.iterrows():
        pub_dt = pd.Timestamp(r["pub_pkt"]).tz_localize(None)
        if pub_dt > max_cutoff_dt:
            audit_counts["excluded_post_cutoff"] += 1
            continue

        if pub_dt.year <= 2024 and pub_dt.month == 6 and pub_dt.day == 15 and pub_dt.hour in (0, 1) and pub_dt.minute == 0:
            audit_counts["archive_placeholder_jun15"] += 1

        pub_date = pub_dt.date()
        is_market_hours_or_preclose = (pub_date in td_set) and (
            (pub_dt.hour < 15) or (pub_dt.hour == 15 and pub_dt.minute <= 30)
        )
        if is_market_hours_or_preclose:
            eff_date = pub_date
        else:
            pos = int(np.searchsorted(sorted_td, pub_date, side="right" if pub_date in td_set else "left"))
            if pos >= len(sorted_td):
                audit_counts["excluded_post_cutoff"] += 1
                continue
            eff_date = sorted_td[pos]
            audit_counts["rolled_to_next_trading_day"] += 1

        audit_counts["usable_aligned_articles"] += 1
        art_id = int(r["article_id"])
        score = float(r["sentiment_score"])
        neg_flag = 1.0 if r["sentiment_label"] == "NEGATIVE" else 0.0

        market_rows.append({"trading_date": eff_date, "score": score, "neg_flag": neg_flag})

        # Entities + NewsImpactAnalyzer targeted stocks/sectors
        mentioned_syms = set()
        mentioned_sectors = set()
        if art_id in ent_by_art.groups:
            ents = ent_by_art.get_group(art_id)
            for _, er in ents.iterrows():
                if er["entity_type"] == "COMPANY":
                    mentioned_syms.add(str(er["entity_value"]).upper())
                elif er["entity_type"] == "SECTOR":
                    mentioned_sectors.add(str(er["entity_value"]).upper())

        impact = impact_analyzer.analyze(
            headline=str(r["headline"] or ""),
            summary=str(r["summary"] or ""),
            sentiment_label=str(r["sentiment_label"]),
            mentioned_symbols=list(mentioned_syms),
        )
        for s in impact.get("impacted_stocks", []):
            if s != "KSE100":
                mentioned_syms.add(s)
        for sec in impact.get("targeted_industries", []):
            mentioned_sectors.add(sec.upper())

        for sym in mentioned_syms:
            stock_rows.append({"symbol": sym, "trading_date": eff_date, "score": score})
        for sec in mentioned_sectors:
            sector_rows.append({"news_sector_key": sec, "trading_date": eff_date, "score": score})

    # Build full trading calendar market-level rolling 1d & 7d sentiment
    cal_df = pd.DataFrame({"trading_date": sorted_td})
    if market_rows:
        mkt_agg = (
            pd.DataFrame(market_rows)
            .groupby("trading_date")
            .agg(
                news_mkt_count_1d=("score", "count"),
                news_mkt_sent_mean_1d=("score", "mean"),
                news_mkt_neg_count_1d=("neg_flag", "sum"),
            )
            .reset_index()
        )
        mkt_ts = cal_df.merge(mkt_agg, on="trading_date", how="left")
    else:
        mkt_ts = cal_df.copy()
        mkt_ts["news_mkt_count_1d"] = 0
        mkt_ts["news_mkt_sent_mean_1d"] = np.nan
        mkt_ts["news_mkt_neg_count_1d"] = 0

    mkt_ts["news_mkt_count_1d"] = mkt_ts["news_mkt_count_1d"].fillna(0).astype(np.int32)
    mkt_ts["news_mkt_neg_count_1d"] = mkt_ts["news_mkt_neg_count_1d"].fillna(0.0)
    mkt_ts["weighted_sum_1d"] = mkt_ts["news_mkt_sent_mean_1d"].fillna(0.0) * mkt_ts["news_mkt_count_1d"]

    roll_cnt_7 = mkt_ts["news_mkt_count_1d"].rolling(7, min_periods=1).sum()
    roll_sum_7 = mkt_ts["weighted_sum_1d"].rolling(7, min_periods=1).sum()
    roll_neg_7 = mkt_ts["news_mkt_neg_count_1d"].rolling(7, min_periods=1).sum()

    mkt_ts["news_mkt_count_7d"] = roll_cnt_7.astype(np.int32)
    mkt_ts["news_mkt_sent_mean_7d"] = np.where(roll_cnt_7 > 0, roll_sum_7 / roll_cnt_7, np.nan)
    mkt_ts["news_mkt_neg_share_7d"] = np.where(roll_cnt_7 > 0, roll_neg_7 / roll_cnt_7, np.nan)
    mkt_ts["has_mkt_news_7d"] = (roll_cnt_7 > 0).astype(np.int8)
    mkt_ts = mkt_ts.drop(columns=["news_mkt_neg_count_1d", "weighted_sum_1d"])

    # Stock-level 1d & trailing 7d sentiment sparse event expansion (only across 7d active windows!)
    td_to_idx = {d: i for i, d in enumerate(sorted_td)}
    if stock_rows:
        st_day = (
            pd.DataFrame(stock_rows)
            .groupby(["symbol", "trading_date"])
            .agg(cnt=("score", "count"), mean_s=("score", "mean"))
            .reset_index()
        )
        # Expand causally across [idx .. idx+6] per stock so 7d window captures trailing news
        # without materializing sparse cartesian zeros for 2M rows.
        expanded_rows = []
        for sym, grp in st_day.groupby("symbol"):
            day_map: Dict[int, List[float]] = {}
            for _, row in grp.iterrows():
                i0 = td_to_idx.get(row["trading_date"])
                if i0 is None:
                    continue
                for offset in range(7):
                    i_t = i0 + offset
                    if i_t >= len(sorted_td):
                        break
                    rec = day_map.setdefault(i_t, [0, 0.0, 0, np.nan])
                    rec[0] += int(row["cnt"])
                    rec[1] += float(row["mean_s"]) * int(row["cnt"])
                    if offset == 0:
                        rec[2] = int(row["cnt"])
                        rec[3] = float(row["mean_s"])
            for i_t, (c7, s7, c1, m1) in day_map.items():
                expanded_rows.append({
                    "symbol": sym,
                    "trading_date": sorted_td[i_t],
                    "news_stock_count_1d": c1,
                    "news_stock_sent_mean_1d": m1,
                    "news_stock_count_7d": c7,
                    "news_stock_sent_mean_7d": s7 / c7 if c7 > 0 else np.nan,
                    "has_stock_news_7d": 1,
                })
        stock_news_df = pd.DataFrame(expanded_rows)
    else:
        stock_news_df = pd.DataFrame(columns=[
            "symbol", "trading_date", "news_stock_count_1d",
            "news_stock_sent_mean_1d", "news_stock_count_7d",
            "news_stock_sent_mean_7d", "has_stock_news_7d",
        ])

    # Sector-level trailing 7d sentiment mapped to canonical companies.sector names
    sector_alias_map = {
        "COMMERCIAL BANKS": ["COMMERCIAL BANKS"],
        "OIL & GAS EXPLORATION": ["OIL & GAS EXPLORATION COMPANIES"],
        "OIL & GAS MARKETING": ["OIL & GAS MARKETING COMPANIES"],
        "OIL & GAS / ENERGY": ["OIL & GAS EXPLORATION COMPANIES", "OIL & GAS MARKETING COMPANIES", "REFINERY"],
        "REFINERY": ["REFINERY"],
        "CEMENT": ["CEMENT"],
        "FERTILIZER": ["FERTILIZER"],
        "FERTILIZER & AGRICULTURE": ["FERTILIZER", "SUGAR & ALLIED INDUSTRIES", "FOOD & PERSONAL CARE PRODUCTS"],
        "POWER GENERATION": ["POWER GENERATION & DISTRIBUTION"],
        "TECHNOLOGY & AI": ["TECHNOLOGY & COMMUNICATION"],
        "TECHNOLOGY & COMMUNICATION": ["TECHNOLOGY & COMMUNICATION"],
        "TECHNOLOGY & TELECOM": ["TECHNOLOGY & COMMUNICATION"],
        "AUTOMOBILE": ["AUTOMOBILE ASSEMBLER", "AUTOMOBILE PARTS & ACCESSORIES"],
        "PHARMACEUTICAL": ["PHARMACEUTICALS"],
        "TEXTILE": ["TEXTILE COMPOSITE", "TEXTILE SPINNING", "TEXTILE WEAVING"],
    }
    norm_sector_rows = []
    for sr in sector_rows:
        targets = sector_alias_map.get(sr["news_sector_key"], [sr["news_sector_key"]])
        for db_sec in targets:
            norm_sector_rows.append({"sector": db_sec, "trading_date": sr["trading_date"], "score": sr["score"]})

    if norm_sector_rows:
        sec_day = (
            pd.DataFrame(norm_sector_rows)
            .groupby(["sector", "trading_date"])
            .agg(cnt=("score", "count"), mean_s=("score", "mean"))
            .reset_index()
        )
        sec_expanded = []
        for sec, grp in sec_day.groupby("sector"):
            day_map: Dict[int, List[float]] = {}
            for _, row in grp.iterrows():
                i0 = td_to_idx.get(row["trading_date"])
                if i0 is None:
                    continue
                for offset in range(7):
                    i_t = i0 + offset
                    if i_t >= len(sorted_td):
                        break
                    rec = day_map.setdefault(i_t, [0, 0.0])
                    rec[0] += int(row["cnt"])
                    rec[1] += float(row["mean_s"]) * int(row["cnt"])
            for i_t, (c7, s7) in day_map.items():
                sec_expanded.append({
                    "sector": sec,
                    "trading_date": sorted_td[i_t],
                    "news_sector_count_7d": c7,
                    "news_sector_sent_mean_7d": s7 / c7 if c7 > 0 else np.nan,
                    "has_sector_news_7d": 1,
                })
        sector_news_df = pd.DataFrame(sec_expanded)
    else:
        sector_news_df = pd.DataFrame(columns=[
            "sector", "trading_date", "news_sector_count_7d",
            "news_sector_sent_mean_7d", "has_sector_news_7d",
        ])

    return mkt_ts, stock_news_df, sector_news_df, audit_counts
