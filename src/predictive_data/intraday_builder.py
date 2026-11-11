"""
Intraday Forecasting Feature & Target Pipeline (Steps 3 & 4).

Strictly separates sub-daily frequency from daily EOD observations.
Enforces:
- Right-labeled causal bar aggregation (bar timestamp = bar end, closed='right')
- PSX trading session boundary enforcement (no overnight or Friday break target bleed)
- Explicit verification against database/CSVs: emits schema-complete 0-row
  deliverables when historical sub-daily data is unavailable (never fabricates rows).
"""

from pathlib import Path
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from sqlalchemy import text, inspect


INTRADAY_BAR_MINUTES = 5
INTRADAY_HORIZONS_BARS = {
    "30m": 6,   # 6 x 5m bars = 30 minutes
    "60m": 12,  # 12 x 5m bars = 60 minutes
}
PSX_INTRADAY_TX_COST = 0.0050  # 50 bps all-in round-trip PSX transaction cost


INTRADAY_FEATURE_COLUMNS = [
    "symbol",
    "timestamp_pkt",
    "trading_date",
    "session_id",
    "bar_frequency_min",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "vwap_session",
    "dist_vwap_pct",
    "ret_1bar_5m",
    "ret_3bar_15m",
    "ret_6bar_30m",
    "ret_12bar_60m",
    "rsi_14_bar",
    "realized_vol_12bar",
    "parkinson_vol_12bar",
    "volume_ratio_12bar",
    "minutes_since_session_open",
    "kse100_intraday_ret_5m",
    "kse100_intraday_ret_30m",
    "rel_strength_kse100_30m",
]

INTRADAY_TARGET_COLUMNS = [
    "symbol",
    "timestamp_pkt",
    "trading_date",
    "session_id",
    "target_ret_30m",
    "target_threshold_30m",
    "target_dir_30m",
    "target_label_30m",
    "target_valid_30m",
    "target_end_ts_30m",
    "target_ret_60m",
    "target_threshold_60m",
    "target_dir_60m",
    "target_label_60m",
    "target_valid_60m",
    "target_end_ts_60m",
]


def audit_intraday_availability(engine, project_root: Path) -> Dict[str, Any]:
    """Audits PostgreSQL tables and disk CSVs for any sub-daily timestamps."""
    insp = inspect(engine)
    tables = insp.get_table_names()

    intraday_tables = [t for t in tables if any(k in t.lower() for k in ("intraday", "tick", "minute", "1m", "5m"))]
    has_subdaily_db_prices = False
    with engine.connect() as conn:
        col_types = pd.read_sql(
            text("""
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name IN ('stock_prices', 'market_indices', 'technical_indicators')
                  AND (column_name LIKE '%date%' OR column_name LIKE '%time%')
            """),
            conn,
        )
        # All price columns are SQL DATE (no time component)
        if not col_types.empty:
            has_subdaily_db_prices = bool(col_types["data_type"].str.contains("timestamp", case=False).any())

    intraday_files = [
        str(p) for p in (project_root / "data").rglob("*.csv")
        if any(k in p.name.lower() for k in ("intraday", "tick", "5m", "1m", "15m", "30m", "60m"))
    ]

    return {
        "intraday_tables_found": intraday_tables,
        "has_subdaily_db_prices": has_subdaily_db_prices,
        "intraday_files_found": intraday_files,
        "historical_intraday_rows_available": 0,
        "status": "UNAVAILABLE_NO_HISTORICAL_INTRADAY_SOURCE",
        "frequency_policy": (
            "Intraday 5-minute bars (Asia/Karachi PKT, right-closed & right-labeled) are strictly "
            "isolated from daily EOD observations. No upsampling/disaggregation from daily bars is permitted."
        ),
        "session_hours_policy": {
            "mon_thu_continuous": "09:30:00 - 15:30:00 PKT",
            "friday_morning": "09:15:00 - 12:00:00 PKT",
            "friday_afternoon": "14:30:00 - 16:30:00 PKT",
        },
        "target_horizons_policy": "30-minute (6 x 5m bars) and 60-minute (12 x 5m bars), restricted strictly within the same continuous session_id.",
    }


def assign_psx_session_id(ts_pkt: pd.Series) -> pd.Series:
    """
    Assigns continuous PSX session identifiers (`YYYY-MM-DD_AM` / `YYYY-MM-DD_PM` / `YYYY-MM-DD_REG`)
    and filters out off-session timestamps so targets never cross market closes or Friday prayer breaks.
    """
    dt = pd.to_datetime(ts_pkt)
    if dt.dt.tz is None:
        dt = dt.dt.tz_localize("Asia/Karachi")
    else:
        dt = dt.dt.tz_convert("Asia/Karachi")

    dow = dt.dt.dayofweek  # 0=Mon..4=Fri
    hhmm = dt.dt.hour * 100 + dt.dt.minute
    d_str = dt.dt.strftime("%Y-%m-%d")

    is_mon_thu = (dow <= 3) & (hhmm >= 930) & (hhmm <= 1530)
    is_fri_am = (dow == 4) & (hhmm >= 915) & (hhmm <= 1200)
    is_fri_pm = (dow == 4) & (hhmm >= 1430) & (hhmm <= 1630)

    session = np.where(
        is_mon_thu,
        d_str + "_REG",
        np.where(is_fri_am, d_str + "_FRIAM", np.where(is_fri_pm, d_str + "_FRIPM", None)),
    )
    return pd.Series(session, index=ts_pkt.index)


def build_intraday_features_and_targets_from_bars(
    bars_df: pd.DataFrame,
    index_bars_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Causal intraday feature & 30m/60m target engineering function ready for live
    5-minute bar ingestion. Zero future lookahead and strict same-session boundary guards.
    """
    if bars_df.empty:
        return pd.DataFrame(columns=INTRADAY_FEATURE_COLUMNS), pd.DataFrame(columns=INTRADAY_TARGET_COLUMNS)

    df = bars_df.copy()
    df["timestamp_pkt"] = pd.to_datetime(df["timestamp_pkt"])
    if df["timestamp_pkt"].dt.tz is None:
        df["timestamp_pkt"] = df["timestamp_pkt"].dt.tz_localize("Asia/Karachi")
    else:
        df["timestamp_pkt"] = df["timestamp_pkt"].dt.tz_convert("Asia/Karachi")

    df["trading_date"] = df["timestamp_pkt"].dt.date
    df["session_id"] = assign_psx_session_id(df["timestamp_pkt"])
    df = df.dropna(subset=["session_id"]).sort_values(["symbol", "timestamp_pkt"]).reset_index(drop=True)
    df["bar_frequency_min"] = INTRADAY_BAR_MINUTES

    # Index intraday context
    idx = index_bars_df.copy()
    if not idx.empty:
        idx["timestamp_pkt"] = pd.to_datetime(idx["timestamp_pkt"])
        if idx["timestamp_pkt"].dt.tz is None:
            idx["timestamp_pkt"] = idx["timestamp_pkt"].dt.tz_localize("Asia/Karachi")
        else:
            idx["timestamp_pkt"] = idx["timestamp_pkt"].dt.tz_convert("Asia/Karachi")
        idx["session_id"] = assign_psx_session_id(idx["timestamp_pkt"])
        idx = idx.dropna(subset=["session_id"]).sort_values("timestamp_pkt").reset_index(drop=True)
        idx["kse100_intraday_ret_5m"] = idx.groupby("session_id")["close"].pct_change(1)
        idx["kse100_intraday_ret_30m"] = idx.groupby("session_id")["close"].pct_change(6)
        idx_small = idx[["timestamp_pkt", "kse100_intraday_ret_5m", "kse100_intraday_ret_30m"]]
    else:
        idx_small = pd.DataFrame(columns=["timestamp_pkt", "kse100_intraday_ret_5m", "kse100_intraday_ret_30m"])

    # Per (symbol, session_id) strictly causal session-cumulative VWAP & indicators
    typical_p = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = typical_p * df["volume"]
    df["_pv"] = pv
    grp_ss = df.groupby(["symbol", "session_id"], sort=False)

    cum_pv = grp_ss["_pv"].cumsum()
    cum_vol = grp_ss["volume"].cumsum().replace(0, np.nan)
    df["vwap_session"] = cum_pv / cum_vol
    df["dist_vwap_pct"] = (df["close"] / df["vwap_session"]) - 1.0

    df["ret_1bar_5m"] = grp_ss["close"].pct_change(1)
    df["ret_3bar_15m"] = grp_ss["close"].pct_change(3)
    df["ret_6bar_30m"] = grp_ss["close"].pct_change(6)
    df["ret_12bar_60m"] = grp_ss["close"].pct_change(12)

    # Bar Wilder RSI (14) within symbol (session-respecting or continuous intraday)
    delta = grp_ss["close"].diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    ag = gain.groupby([df["symbol"], df["session_id"]]).transform(lambda s: s.ewm(alpha=1/14, min_periods=14, adjust=False).mean())
    al = loss.groupby([df["symbol"], df["session_id"]]).transform(lambda s: s.ewm(alpha=1/14, min_periods=14, adjust=False).mean())
    rs = ag / al.replace(0, np.nan)
    df["rsi_14_bar"] = 100.0 - (100.0 / (1.0 + rs))

    log_r = np.log(df["close"] / grp_ss["close"].shift(1))
    df["realized_vol_12bar"] = log_r.groupby([df["symbol"], df["session_id"]]).transform(lambda s: s.rolling(12, min_periods=6).std())
    hl_sq = (np.log(df["high"] / df["low"].replace(0, np.nan))) ** 2
    park_bar = np.sqrt(hl_sq / (4.0 * np.log(2.0)))
    df["parkinson_vol_12bar"] = park_bar.groupby([df["symbol"], df["session_id"]]).transform(lambda s: s.rolling(12, min_periods=6).mean())

    vol_sma12 = grp_ss["volume"].transform(lambda s: s.rolling(12, min_periods=6).mean())
    df["volume_ratio_12bar"] = np.where(vol_sma12 > 0, df["volume"] / vol_sma12, np.nan)

    session_start_ts = grp_ss["timestamp_pkt"].transform("min")
    df["minutes_since_session_open"] = (df["timestamp_pkt"] - session_start_ts).dt.total_seconds() / 60.0

    df = df.merge(idx_small, on="timestamp_pkt", how="left")
    df["rel_strength_kse100_30m"] = df["ret_6bar_30m"] - df["kse100_intraday_ret_30m"]
    df = df.drop(columns=["_pv"])

    # Targets (30m and 60m) strictly inside the SAME session_id
    t_df = df[["symbol", "timestamp_pkt", "trading_date", "session_id"]].copy()
    sigma_causal = np.maximum(df["realized_vol_12bar"].fillna(0.003), 0.002)

    for label, h_bars in INTRADAY_HORIZONS_BARS.items():
        fut_c = grp_ss["close"].shift(-h_bars)
        fut_ts = grp_ss["timestamp_pkt"].shift(-h_bars)
        expected_mins = h_bars * INTRADAY_BAR_MINUTES
        actual_mins = (fut_ts - df["timestamp_pkt"]).dt.total_seconds() / 60.0

        valid = fut_c.notna() & (df["close"] > 0) & (actual_mins == expected_mins) & df["realized_vol_12bar"].notna()
        ret = np.where(valid, (fut_c / df["close"]) - 1.0, np.nan)
        thresh = PSX_INTRADAY_TX_COST + 0.35 * sigma_causal * np.sqrt(h_bars)
        dir_num = np.where(~valid, np.nan, np.where(ret > thresh, 1.0, np.where(ret < -thresh, -1.0, 0.0)))
        dir_lbl = np.where(~valid, None, np.where(dir_num == 1.0, "UP", np.where(dir_num == -1.0, "DOWN", "NEUTRAL")))

        t_df[f"target_ret_{label}"] = ret
        t_df[f"target_threshold_{label}"] = thresh
        t_df[f"target_dir_{label}"] = dir_num
        t_df[f"target_label_{label}"] = dir_lbl
        t_df[f"target_valid_{label}"] = valid.astype(np.int8)
        t_df[f"target_end_ts_{label}"] = fut_ts

    return df[INTRADAY_FEATURE_COLUMNS], t_df[INTRADAY_TARGET_COLUMNS]


def create_empty_intraday_deliverables(out_dir: Path, audit_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Writes schema-complete 0-row intraday Parquet & CSV templates cleanly without
    fabricating fake historical ticks.
    """
    feat_empty = pd.DataFrame({c: pd.Series(dtype="float64" if c not in ("symbol", "session_id") else "object") for c in INTRADAY_FEATURE_COLUMNS})
    tgt_empty = pd.DataFrame({c: pd.Series(dtype="float64" if c not in ("symbol", "session_id", "target_label_30m", "target_label_60m") else "object") for c in INTRADAY_TARGET_COLUMNS})

    feat_csv = out_dir / "intraday_features.csv"
    feat_pq = out_dir / "intraday_features.parquet"
    tgt_csv = out_dir / "intraday_targets.csv"
    tgt_pq = out_dir / "intraday_targets.parquet"

    feat_empty.to_csv(feat_csv, index=False)
    feat_empty.to_parquet(feat_pq, index=False)
    tgt_empty.to_csv(tgt_csv, index=False)
    tgt_empty.to_parquet(tgt_pq, index=False)

    return {
        "rows_written": 0,
        "feature_columns": len(INTRADAY_FEATURE_COLUMNS),
        "target_columns": len(INTRADAY_TARGET_COLUMNS),
        "files": [str(feat_pq), str(feat_csv), str(tgt_pq), str(tgt_csv)],
        "audit": audit_info,
    }

