"""Point-in-time Fundamental Analysis Engine for PSX equities."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.analysis.common import (
    get_company_metadata,
    resolve_effective_as_of_date,
    safe_div,
    safe_float,
    sanitize_for_json,
)
from src.predictive_data.point_in_time import (
    load_clean_corporate_actions,
    parse_ended_date_from_title,
)

logger = logging.getLogger(__name__)

# Statutory SECP/PSX reporting fallback lag when no matching earnings announcement exists
DEFAULT_PUBLICATION_LAG_DAYS = 100
MIN_SECTOR_PEERS = 2

_CORE_IFRS_METRICS = (
    "total_revenue",
    "operating_revenue",
    "gross_profit",
    "operating_income",
    "ebit",
    "ebitda",
    "interest_expense",
    "net_interest_income",
    "pretax_income",
    "net_income",
    "net_income_common_stockholders",
    "basic_eps",
    "diluted_eps",
    "basic_average_shares",
    "ordinary_shares_number",
    "total_assets",
    "current_assets",
    "cash_and_cash_equivalents",
    "current_liabilities",
    "total_liabilities_net_minority_interest",
    "total_debt",
    "common_stock_equity",
    "stockholders_equity",
    "operating_cash_flow",
    "capital_expenditure",
    "free_cash_flow",
    "cash_dividends_paid",
    "common_stock_dividend_paid",
)


class FundamentalAnalysisEngine:
    """
    Independent, strictly point-in-time Fundamental Analysis Engine for PSX stocks.

    Uses audited IFRS INCOME_STATEMENT, BALANCE_SHEET, and CASH_FLOW rows paired with
    reconstructed PSX Earnings Announcement public disclosure dates, split-validated
    corporate_payouts, and comparable-period sector medians.
    """

    def analyze(
        self,
        conn: Connection,
        symbol: str,
        as_of_date: Optional[date | datetime | str] = None,
    ) -> dict[str, Any]:
        """Run full 7-pillar point-in-time fundamental analysis for `symbol` up to `as_of_date`."""
        sym = symbol.strip().upper()
        meta = get_company_metadata(conn, sym)
        req_cutoff, mkt_cutoff = resolve_effective_as_of_date(conn, sym, as_of_date)

        is_bank = (meta.get("sector_category") or "").strip().lower() == "banks" or (
            (meta.get("sector") or "").strip().upper() == "COMMERCIAL BANKS"
        )

        # Latest point-in-time price snapshot & market cap
        mkt_snap = self._load_market_snapshot(conn, sym, mkt_cutoff)

        # Load corporate splits & dividends <= mkt_cutoff
        payouts_df, _ = load_clean_corporate_actions(conn)
        sym_payouts = self._load_clean_dividends(conn, sym, mkt_cutoff, payouts_df)

        # Load PIT IFRS statements for target stock
        sym_periods = self._load_pit_statements_for_symbols(conn, [sym], mkt_cutoff).get(sym, [])

        data_quality_notes: list[str] = [
            "Only audited IFRS statements (INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW) in full PKR are used; legacy ANNUAL/QUARTERLY tables containing placeholder sentinels (e.g., 12121.0) are excluded."
        ]

        if not sym_periods:
            return self._build_missing_statements_response(
                sym=sym,
                meta=meta,
                req_cutoff=req_cutoff,
                mkt_cutoff=mkt_cutoff,
                mkt_snap=mkt_snap,
                sym_payouts=sym_payouts,
                notes=data_quality_notes,
            )

        # Identify latest disclosed period and latest complete period (handles partial filings like OGDC 2025-06-30)
        latest_any = sym_periods[-1]
        complete_periods = [p for p in sym_periods if p["has_complete_core"]]
        latest_complete = complete_periods[-1] if complete_periods else latest_any
        prior_complete = complete_periods[-2] if len(complete_periods) >= 2 else None

        if latest_any["period_end_date"] != latest_complete["period_end_date"]:
            data_quality_notes.append(
                f"Latest disclosed period ({latest_any['period_end_date']}, pub {latest_any['effective_pub_date']}) is partial (missing balance sheet/revenue); core balance-sheet and margin ratios use latest complete period ({latest_complete['period_end_date']}, pub {latest_complete['effective_pub_date']})."
            )
        if latest_complete["eps_source"] == "derived_net_income_over_shares":
            data_quality_notes.append(
                f"Reported IFRS basic_eps was missing for {latest_complete['period_end_date']}; basic EPS was derived cleanly as Net Income / Ordinary Shares."
            )
        if is_bank:
            data_quality_notes.append(
                "Commercial Bank IFRS format: Operating Margin, Current Ratio, and Interest Coverage are marked Not Applicable (None) because banking operations report Net Interest Income rather than industrial working capital/interest coverage."
            )

        # 7 Analytical Domains
        profitability = self._analyze_profitability(latest_complete, is_bank=is_bank)
        valuation = self._analyze_valuation(
            latest_complete=latest_complete,
            mkt_snap=mkt_snap,
            sym_payouts=sym_payouts,
            mkt_cutoff=mkt_cutoff,
        )
        financial_health = self._analyze_financial_health(latest_complete, is_bank=is_bank)
        growth = self._analyze_growth(sym_periods, complete_periods)
        cash_flow = self._analyze_cash_flow(complete_periods)
        dividends = self._analyze_dividends(
            sym_payouts=sym_payouts,
            complete_periods=complete_periods,
            mkt_snap=mkt_snap,
            mkt_cutoff=mkt_cutoff,
            notes=data_quality_notes,
        )
        sector_comparison = self._analyze_sector_comparison(
            conn=conn,
            sym=sym,
            meta=meta,
            target_period=latest_complete,
            target_metrics={
                "profitability": profitability,
                "valuation": valuation,
                "financial_health": financial_health,
                "growth": growth,
                "dividends": dividends,
            },
            is_bank=is_bank,
            mkt_cutoff=mkt_cutoff,
        )

        # Transparent synthesis & scoring
        synthesis = self._synthesize_assessment(
            meta=meta,
            is_bank=is_bank,
            latest_complete=latest_complete,
            profitability=profitability,
            valuation=valuation,
            financial_health=financial_health,
            growth=growth,
            cash_flow=cash_flow,
            dividends=dividends,
            sector_comparison=sector_comparison,
        )

        # Check stale announcements (> 450 days since latest complete period_end_date)
        days_since_pe = (mkt_cutoff - latest_complete["period_end_date"]).days
        if days_since_pe > 460:
            data_quality_notes.append(
                f"Latest complete statement period ({latest_complete['period_end_date']}) is {days_since_pe} calendar days before cutoff."
            )

        data_freshness = {
            "requested_as_of_date": req_cutoff.isoformat(),
            "market_cutoff_date": mkt_cutoff.isoformat(),
            "latest_price_date": mkt_snap.get("trading_date"),
            "latest_statement_period_end": latest_complete["period_end_date"].isoformat(),
            "latest_statement_effective_pub_date": latest_complete["effective_pub_date"].isoformat(),
            "publication_date_verified_via_announcement": bool(latest_complete["pub_verified"]),
            "available_complete_annual_periods": len(complete_periods),
            "days_since_latest_complete_period_end": int(days_since_pe),
            "is_stale": days_since_pe > 460,
        }

        data_source_references = {
            "financials_table": "company_financials (INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW)",
            "publication_lag_source": "corporate_announcements (Earnings Announcements) with +100d SECP statutory fallback",
            "dividends_source": "corporate_payouts (payout_type='dividend', face-value validated) & CASH_FLOW.cash_dividends_paid",
            "valuation_price_source": "stock_prices (KSE100 calendar-aligned close & market_cap <= as_of_date)",
            "sector_source": "companies.sector (same sector, comparable period_end_date within 370 days)",
        }

        result = {
            "symbol": sym,
            "company_name": meta.get("company_name"),
            "sector": meta.get("sector"),
            "sector_category": meta.get("sector_category"),
            "is_kse100": bool(meta.get("is_kse100")),
            "analysis_type": "FUNDAMENTAL",
            "status": "OK",
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "as_of_date": mkt_cutoff.isoformat(),
            "data_cutoff_timestamp": max(
                mkt_snap.get("trading_date") or mkt_cutoff.isoformat(),
                latest_complete["effective_pub_date"].isoformat(),
            ),
            "market_snapshot": mkt_snap,
            "reporting_period_context": {
                "latest_complete_period_end": latest_complete["period_end_date"].isoformat(),
                "effective_publication_date": latest_complete["effective_pub_date"].isoformat(),
                "pub_verified": bool(latest_complete["pub_verified"]),
                "latest_disclosed_period_end": latest_any["period_end_date"].isoformat(),
                "currency_unit": "PKR",
                "historical_periods_summary": [
                    {
                        "period_end_date": p["period_end_date"].isoformat(),
                        "effective_pub_date": p["effective_pub_date"].isoformat(),
                        "pub_verified": p["pub_verified"],
                        "total_revenue_pkr": safe_float(p["total_revenue"], 0),
                        "net_income_pkr": safe_float(p["net_income"], 0),
                        "basic_eps_pkr": safe_float(p["effective_eps"], 4),
                        "common_stock_equity_pkr": safe_float(p["common_stock_equity"], 0),
                        "operating_cash_flow_pkr": safe_float(p["operating_cash_flow"], 0),
                        "free_cash_flow_pkr": safe_float(p["effective_fcf"], 0),
                    }
                    for p in complete_periods
                ],
            },
            "profitability": profitability,
            "valuation": valuation,
            "financial_health": financial_health,
            "growth": growth,
            "cash_flow_analysis": cash_flow,
            "dividend_analysis": dividends,
            "sector_comparison": sector_comparison,
            "strengths": synthesis["strengths"],
            "weaknesses": synthesis["weaknesses"],
            "conflicting_signals": synthesis["conflicting_signals"],
            "overall_assessment": synthesis["overall_assessment"],
            "fundamental_score": synthesis["fundamental_score"],
            "score_methodology": synthesis["score_methodology"],
            "summary": synthesis["summary"],
            "data_quality_notes": data_quality_notes,
            "data_freshness": data_freshness,
            "data_source_references": data_source_references,
        }
        return sanitize_for_json(result)

    def _build_missing_statements_response(
        self,
        *,
        sym: str,
        meta: dict[str, Any],
        req_cutoff: date,
        mkt_cutoff: date,
        mkt_snap: dict[str, Any],
        sym_payouts: dict[str, Any],
        notes: list[str],
    ) -> dict[str, Any]:
        notes = list(notes)
        notes.append(
            f"No audited IFRS financial statements (INCOME_STATEMENT/BALANCE_SHEET/CASH_FLOW) were disclosed for {sym} on or before {mkt_cutoff}."
        )
        ttm_div = sym_payouts.get("ttm_adjusted_dps_pkr")
        price_val = mkt_snap.get("close_pkr")
        ann_div_yield = (
            safe_float((ttm_div / price_val) * 100.0, 2)
            if ttm_div is not None and price_val and price_val > 0
            else None
        )
        return sanitize_for_json(
            {
                "symbol": sym,
                "company_name": meta.get("company_name"),
                "sector": meta.get("sector"),
                "sector_category": meta.get("sector_category"),
                "is_kse100": bool(meta.get("is_kse100")),
                "analysis_type": "FUNDAMENTAL",
                "status": "NO_FINANCIAL_STATEMENTS",
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                "as_of_date": mkt_cutoff.isoformat(),
                "data_cutoff_timestamp": mkt_snap.get("trading_date") or mkt_cutoff.isoformat(),
                "market_snapshot": mkt_snap,
                "reporting_period_context": None,
                "profitability": {"status": "UNAVAILABLE", "reason": "No IFRS financial statements in warehouse."},
                "valuation": {
                    "pe_ratio": None,
                    "pb_ratio": None,
                    "dividend_yield_pct": ann_div_yield,
                    "status": "PARTIAL_PRICE_ONLY",
                },
                "financial_health": {"status": "UNAVAILABLE", "reason": "No IFRS balance sheet in warehouse."},
                "growth": {"status": "UNAVAILABLE", "reason": "No IFRS multi-year income statements."},
                "cash_flow_analysis": {"status": "UNAVAILABLE", "reason": "No IFRS cash flow statement."},
                "dividend_analysis": {
                    "status": "ANNOUNCEMENTS_ONLY" if sym_payouts["events"] else "NO_DIVIDEND_HISTORY",
                    "ttm_announced_dps_pkr": ttm_div,
                    "announced_dividend_yield_pct": ann_div_yield,
                    "payout_events_count": len(sym_payouts["events"]),
                    "recent_payout_events": sym_payouts["events"][:10],
                },
                "sector_comparison": {
                    "status": "INSUFFICIENT_SECTOR_DATA",
                    "reason": "Target equity has no IFRS disclosures and/or unclassified sector.",
                },
                "strengths": [],
                "weaknesses": [],
                "conflicting_signals": [f"Financial statements unavailable for {sym} <= {mkt_cutoff}; fundamental valuation & health ratios omitted rather than fabricated."],
                "overall_assessment": "INSUFFICIENT_FUNDAMENTAL_DATA",
                "fundamental_score": None,
                "score_methodology": None,
                "summary": f"Fundamental assessment unavailable for {sym}: no audited IFRS financial disclosures on or before {mkt_cutoff}.",
                "data_quality_notes": notes,
                "data_freshness": {
                    "requested_as_of_date": req_cutoff.isoformat(),
                    "market_cutoff_date": mkt_cutoff.isoformat(),
                    "latest_price_date": mkt_snap.get("trading_date"),
                    "available_complete_annual_periods": 0,
                    "is_stale": True,
                },
                "data_source_references": {
                    "financials_table": "company_financials (0 rows found for symbol)",
                    "dividends_source": "corporate_payouts",
                    "valuation_price_source": "stock_prices",
                },
            }
        )

    def _load_market_snapshot(self, conn: Connection, symbol: str, cutoff: date) -> dict[str, Any]:
        row = conn.execute(
            text(
                """
                SELECT sp.trading_date, sp.close, sp.volume, sp.market_cap
                FROM stock_prices sp
                JOIN market_indices mi ON mi.trading_date = sp.trading_date AND mi.index_symbol = 'KSE100'
                WHERE UPPER(sp.symbol) = :sym AND sp.trading_date <= :cutoff AND sp.close > 0
                ORDER BY sp.trading_date DESC, sp.source_id DESC
                LIMIT 1
                """
            ),
            {"sym": symbol, "cutoff": cutoff},
        ).mappings().first()

        if not row:
            return {"trading_date": None, "close_pkr": None, "volume": None, "market_cap_pkr": None}

        mcap = safe_float(row["market_cap"], 0)
        return {
            "trading_date": row["trading_date"].isoformat() if isinstance(row["trading_date"], date) else str(row["trading_date"]),
            "close_pkr": safe_float(row["close"], 4),
            "volume": int(safe_float(row["volume"], 0) or 0),
            "market_cap_pkr": mcap if (mcap is not None and mcap > 0) else None,
        }

    def _load_clean_dividends(
        self,
        conn: Connection,
        symbol: str,
        cutoff: date,
        clean_actions_payouts: pd.DataFrame,
    ) -> dict[str, Any]:
        """
        Load cash dividends <= cutoff from corporate_payouts, repairing any
        face-value scraper mismatches (where dividend_per_share deviates from
        payout_percentage * face_value / 100) and adjusting pre-split DPS to
        current cutoff-date share basis for yield compatibility.
        """
        rows = conn.execute(
            text(
                """
                SELECT announcement_date, fiscal_year, dividend_per_share, payout_percentage, face_value
                FROM corporate_payouts
                WHERE UPPER(symbol) = :sym
                  AND payout_type = 'dividend'
                  AND announcement_date <= :cutoff
                ORDER BY announcement_date DESC
                """
            ),
            {"sym": symbol, "cutoff": cutoff},
        ).mappings().all()

        # Future-relative-to-announcement splits known on or before cutoff
        sym_splits = clean_actions_payouts[
            (clean_actions_payouts["symbol"].str.upper() == symbol)
            & (clean_actions_payouts["payout_type"] == "split")
            & (pd.to_datetime(clean_actions_payouts["announcement_date"]).dt.date <= cutoff)
        ].copy()

        split_events: list[tuple[date, float]] = []
        for _, sp in sym_splits.iterrows():
            sp_date = pd.to_datetime(sp["announcement_date"]).date()
            pct = safe_float(sp.get("payout_percentage"))
            # In corporate_payouts, 400% bonus/split = 5x shares (1 + pct/100)
            if pct and pct > 0:
                factor = 1.0 + (pct / 100.0)
                split_events.append((sp_date, factor))

        ttm_start = cutoff - timedelta(days=365)
        events: list[dict[str, Any]] = []
        ttm_sum = 0.0
        corrected_count = 0

        for r in rows:
            ann_d = r["announcement_date"]
            if isinstance(ann_d, datetime):
                ann_d = ann_d.date()
            elif isinstance(ann_d, str):
                ann_d = date.fromisoformat(ann_d[:10])

            raw_dps = safe_float(r["dividend_per_share"])
            pct = safe_float(r["payout_percentage"])
            fv = safe_float(r["face_value"])

            expected_dps = (pct * fv / 100.0) if (pct is not None and fv is not None and fv > 0) else None
            was_corrected = False
            if expected_dps is not None and expected_dps > 0:
                if raw_dps is None or abs(raw_dps - expected_dps) > 0.05:
                    eff_dps = expected_dps
                    was_corrected = True
                    corrected_count += 1
                else:
                    eff_dps = raw_dps
            else:
                eff_dps = raw_dps

            if eff_dps is None or eff_dps <= 0:
                continue

            # Divide pre-split DPS by any split factor occurring strictly between ann_d and cutoff
            adj_factor = 1.0
            for sp_d, fac in split_events:
                if ann_d < sp_d <= cutoff:
                    adj_factor *= fac
            split_adj_dps = eff_dps / adj_factor

            if ttm_start < ann_d <= cutoff:
                ttm_sum += split_adj_dps

            events.append(
                {
                    "announcement_date": ann_d.isoformat(),
                    "fiscal_year": int(r["fiscal_year"]) if r["fiscal_year"] is not None else None,
                    "raw_dps_pkr": safe_float(raw_dps, 4),
                    "validated_dps_pkr": safe_float(eff_dps, 4),
                    "split_adjusted_dps_pkr": safe_float(split_adj_dps, 4),
                    "payout_percentage": pct,
                    "face_value": fv,
                    "dps_corrected_for_face_value": was_corrected,
                }
            )

        return {
            "events": events,
            "ttm_adjusted_dps_pkr": safe_float(ttm_sum, 4) if events else None,
            "corrected_face_value_count": corrected_count,
        }

    def _load_pit_statements_for_symbols(
        self,
        conn: Connection,
        symbols: list[str],
        cutoff: date,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Load audited IFRS statements for `symbols` and reconstruct effective
        public disclosure dates via corporate_announcements <= cutoff, returning
        only periods publicly disclosed on or before `cutoff`.
        """
        if not symbols:
            return {}
        upper_syms = [s.strip().upper() for s in symbols]

        is_pg = getattr(conn, "dialect", None) is not None and conn.dialect.name == "postgresql"
        if is_pg:
            fin_rows = pd.read_sql(
                text(
                    """
                    SELECT UPPER(symbol) AS symbol, period_end_date, metric_name, metric_value
                    FROM company_financials
                    WHERE UPPER(symbol) = ANY(:syms)
                      AND statement_type IN ('INCOME_STATEMENT', 'BALANCE_SHEET', 'CASH_FLOW')
                      AND metric_name = ANY(:metrics)
                      AND period_end_date <= :cutoff
                    ORDER BY symbol, period_end_date ASC
                    """
                ),
                conn,
                params={"syms": upper_syms, "metrics": list(_CORE_IFRS_METRICS), "cutoff": cutoff},
            )
        else:
            s_ph = ",".join(f":s_{i}" for i in range(len(upper_syms)))
            m_ph = ",".join(f":m_{i}" for i in range(len(_CORE_IFRS_METRICS)))
            p = {"cutoff": cutoff}
            for i, s in enumerate(upper_syms):
                p[f"s_{i}"] = s
            for i, m in enumerate(_CORE_IFRS_METRICS):
                p[f"m_{i}"] = m
            fin_rows = pd.read_sql(
                text(
                    f"""
                    SELECT UPPER(symbol) AS symbol, period_end_date, metric_name, metric_value
                    FROM company_financials
                    WHERE UPPER(symbol) IN ({s_ph})
                      AND statement_type IN ('INCOME_STATEMENT', 'BALANCE_SHEET', 'CASH_FLOW')
                      AND metric_name IN ({m_ph})
                      AND period_end_date <= :cutoff
                    ORDER BY symbol, period_end_date ASC
                    """
                ),
                conn,
                params=p,
            )
        if fin_rows.empty:
            return {}

        if is_pg:
            ann_rows = pd.read_sql(
                text(
                    """
                    SELECT UPPER(symbol) AS symbol, posting_date, title
                    FROM corporate_announcements
                    WHERE UPPER(symbol) = ANY(:syms)
                      AND category = 'Earnings Announcements'
                      AND posting_date <= :cutoff
                    ORDER BY symbol, posting_date ASC
                    """
                ),
                conn,
                params={"syms": upper_syms, "cutoff": cutoff},
            )
        else:
            s_ph = ",".join(f":s_{i}" for i in range(len(upper_syms)))
            p_ann = {"cutoff": cutoff}
            for i, s in enumerate(upper_syms):
                p_ann[f"s_{i}"] = s
            ann_rows = pd.read_sql(
                text(
                    f"""
                    SELECT UPPER(symbol) AS symbol, posting_date, title
                    FROM corporate_announcements
                    WHERE UPPER(symbol) IN ({s_ph})
                      AND category = 'Earnings Announcements'
                      AND posting_date <= :cutoff
                    ORDER BY symbol, posting_date ASC
                    """
                ),
                conn,
                params=p_ann,
            )

        # Map (symbol, ended_period_date) -> earliest earnings announcement posting_date
        ann_lookup: dict[tuple[str, date], date] = {}
        if not ann_rows.empty:
            for _, ar in ann_rows.iterrows():
                post_d = pd.to_datetime(ar["posting_date"]).date()
                ended = parse_ended_date_from_title(str(ar["title"]))
                if ended is None:
                    continue
                ended_d = ended.date() if isinstance(ended, pd.Timestamp) else ended
                if not (ended_d <= post_d <= ended_d + timedelta(days=180)):
                    continue
                key = (ar["symbol"], ended_d)
                if key not in ann_lookup or post_d < ann_lookup[key]:
                    ann_lookup[key] = post_d

        # Pivot per (symbol, period_end_date)
        fin_rows["period_end_date"] = pd.to_datetime(fin_rows["period_end_date"]).dt.date
        piv = fin_rows.pivot_table(
            index=["symbol", "period_end_date"],
            columns="metric_name",
            values="metric_value",
            aggfunc="first",
        ).reset_index()

        out: dict[str, list[dict[str, Any]]] = {}
        for _, row in piv.iterrows():
            sym = str(row["symbol"])
            pe = row["period_end_date"]

            pub_d = ann_lookup.get((sym, pe))
            pub_verified = False
            if pub_d is not None:
                pub_verified = True
            else:
                pub_d = pe + timedelta(days=DEFAULT_PUBLICATION_LAG_DAYS)

            # Strict point-in-time public availability enforcement
            if pub_d > cutoff:
                continue

            def _get(name: str) -> Optional[float]:
                return safe_float(row[name]) if name in row.index else None

            rev = _get("total_revenue")
            if rev is None:
                rev = _get("operating_revenue")

            ni = _get("net_income")
            if ni is None:
                ni = _get("net_income_common_stockholders")

            equity = _get("common_stock_equity")
            if equity is None:
                equity = _get("stockholders_equity")

            shares = _get("ordinary_shares_number")
            if shares is None or shares <= 0:
                shares = _get("basic_average_shares")

            rep_eps = _get("basic_eps")
            if rep_eps is not None:
                eff_eps = rep_eps
                eps_source = "reported_ifrs_basic_eps"
            elif ni is not None and shares is not None and shares > 0:
                eff_eps = ni / shares
                eps_source = "derived_net_income_over_shares"
            else:
                eff_eps = None
                eps_source = "unavailable"

            ocf = _get("operating_cash_flow")
            capex = _get("capital_expenditure")
            fcf = _get("free_cash_flow")
            if fcf is None and ocf is not None and capex is not None:
                fcf = ocf - abs(capex)

            cash_div = _get("cash_dividends_paid")
            if cash_div is None:
                cash_div = _get("common_stock_dividend_paid")

            ebit_val = _get("ebit")
            op_inc = _get("operating_income")
            assets = _get("total_assets")
            debt = _get("total_debt")
            cur_a = _get("current_assets")
            cur_l = _get("current_liabilities")

            has_complete_core = (
                rev is not None
                and ni is not None
                and equity is not None
                and assets is not None
            )

            rec = {
                "symbol": sym,
                "period_end_date": pe,
                "effective_pub_date": pub_d,
                "pub_verified": pub_verified,
                "total_revenue": rev,
                "gross_profit": _get("gross_profit"),
                "operating_income": op_inc,
                "ebit": ebit_val,
                "ebitda": _get("ebitda"),
                "interest_expense": _get("interest_expense"),
                "net_interest_income": _get("net_interest_income"),
                "net_income": ni,
                "basic_eps": rep_eps,
                "diluted_eps": _get("diluted_eps"),
                "effective_eps": eff_eps,
                "eps_source": eps_source,
                "shares": shares,
                "total_assets": assets,
                "common_stock_equity": equity,
                "total_debt": debt,
                "current_assets": cur_a,
                "current_liabilities": cur_l,
                "cash_and_equivalents": _get("cash_and_cash_equivalents"),
                "operating_cash_flow": ocf,
                "capital_expenditure": capex,
                "effective_fcf": fcf,
                "cash_dividends_paid": cash_div,
                "has_complete_core": has_complete_core,
            }
            out.setdefault(sym, []).append(rec)

        for sym_k in out:
            out[sym_k].sort(key=lambda x: x["period_end_date"])
        return out

    def _analyze_profitability(self, stmt: dict[str, Any], *, is_bank: bool) -> dict[str, Any]:
        ni = stmt["net_income"]
        rev = stmt["total_revenue"]
        equity = stmt["common_stock_equity"]
        assets = stmt["total_assets"]
        op_inc = stmt["operating_income"]
        gp = stmt["gross_profit"]

        roe = safe_div(ni, equity, require_positive_den=True)
        roa = safe_div(ni, assets, require_positive_den=True)
        net_margin = safe_div(ni, rev, require_positive_den=True)
        op_margin = None if is_bank else safe_div(op_inc, rev, require_positive_den=True)
        gross_margin = None if is_bank else safe_div(gp, rev, require_positive_den=True)

        missing_reasons: dict[str, str] = {}
        if equity is None or equity <= 0:
            missing_reasons["roe_pct"] = "Common equity is missing or non-positive."
        if is_bank:
            missing_reasons["operating_margin_pct"] = "Not applicable under banking IFRS statement format."
            missing_reasons["gross_margin_pct"] = "Not applicable under banking IFRS statement format."
        elif op_margin is None:
            missing_reasons["operating_margin_pct"] = "operating_income or total_revenue unavailable."

        return {
            "period_end_date": stmt["period_end_date"].isoformat(),
            "effective_pub_date": stmt["effective_pub_date"].isoformat(),
            "eps_pkr": safe_float(stmt["effective_eps"], 4),
            "diluted_eps_pkr": safe_float(stmt["diluted_eps"], 4),
            "eps_source": stmt["eps_source"],
            "roe_pct": safe_float(roe * 100.0, 2) if roe is not None else None,
            "roa_pct": safe_float(roa * 100.0, 2) if roa is not None else None,
            "net_margin_pct": safe_float(net_margin * 100.0, 2) if net_margin is not None else None,
            "operating_margin_pct": safe_float(op_margin * 100.0, 2) if op_margin is not None else None,
            "gross_margin_pct": safe_float(gross_margin * 100.0, 2) if gross_margin is not None else None,
            "net_income_pkr": safe_float(ni, 0),
            "revenue_pkr": safe_float(rev, 0),
            "missing_reasons": missing_reasons,
        }

    def _analyze_valuation(
        self,
        *,
        latest_complete: dict[str, Any],
        mkt_snap: dict[str, Any],
        sym_payouts: dict[str, Any],
        mkt_cutoff: date,
    ) -> dict[str, Any]:
        price = mkt_snap.get("close_pkr")
        mcap = mkt_snap.get("market_cap_pkr")
        ni = latest_complete["net_income"]
        equity = latest_complete["common_stock_equity"]
        eff_eps = latest_complete["effective_eps"]
        shares = latest_complete["shares"]

        basis_notes: list[str] = []
        # Split-invariant Market Cap / Net Income primary valuation
        if mcap is not None and mcap > 0:
            pe = safe_div(mcap, ni, require_positive_den=True, digits=2)
            pb = safe_div(mcap, equity, require_positive_den=True, digits=2)
            valuation_basis = "market_cap_based (split_invariant)"
            effective_mcap = mcap
        elif price is not None and price > 0 and shares is not None and shares > 0:
            effective_mcap = price * shares
            pe = safe_div(price, eff_eps, require_positive_den=True, digits=2)
            pb = safe_div(effective_mcap, equity, require_positive_den=True, digits=2)
            valuation_basis = "price_x_shares_fallback"
            basis_notes.append("stock_prices.market_cap unavailable; fell back to close * IFRS shares.")
        else:
            effective_mcap = None
            pe = None
            pb = None
            valuation_basis = "unavailable"
            basis_notes.append("Insufficient market price/capitalization data to compute P/E or P/B.")

        if ni is not None and ni <= 0:
            basis_notes.append("Net income <= 0 PKR: P/E ratio is undefined (None).")
        if equity is not None and equity <= 0:
            basis_notes.append("Book equity <= 0 PKR: P/B ratio is undefined (None).")

        earnings_yield_pct = safe_float((1.0 / pe) * 100.0, 2) if (pe is not None and pe > 0) else None

        # Dividend yield: prefer TTM announced DPS / current price when payouts exist, fallback to cash_dividends_paid / market_cap
        ttm_dps = sym_payouts.get("ttm_adjusted_dps_pkr")
        announced_yield = (
            safe_float((ttm_dps / price) * 100.0, 2)
            if (ttm_dps is not None and ttm_dps > 0 and price is not None and price > 0)
            else None
        )
        cash_div = latest_complete["cash_dividends_paid"]
        cf_yield = (
            safe_float((abs(cash_div) / effective_mcap) * 100.0, 2)
            if (cash_div is not None and abs(cash_div) > 0 and effective_mcap and effective_mcap > 0)
            else None
        )
        if announced_yield is not None:
            div_yield = announced_yield
            div_yield_basis = "ttm_announced_dps_over_price"
        elif cf_yield is not None:
            div_yield = cf_yield
            div_yield_basis = "annual_cash_dividends_over_market_cap"
        elif cash_div == 0.0:
            div_yield = 0.0
            div_yield_basis = "confirmed_zero_cash_dividends"
        else:
            div_yield = None
            div_yield_basis = "unavailable"

        return {
            "price_date": mkt_snap.get("trading_date"),
            "price_pkr": price,
            "market_cap_pkr": safe_float(effective_mcap, 0),
            "valuation_basis": valuation_basis,
            "pe_ratio": pe,
            "pb_ratio": pb,
            "earnings_yield_pct": earnings_yield_pct,
            "dividend_yield_pct": div_yield,
            "dividend_yield_basis": div_yield_basis,
            "announced_ttm_dividend_yield_pct": announced_yield,
            "cash_flow_implied_dividend_yield_pct": cf_yield,
            "notes": basis_notes,
        }

    def _analyze_financial_health(self, stmt: dict[str, Any], *, is_bank: bool) -> dict[str, Any]:
        debt = stmt["total_debt"]
        equity = stmt["common_stock_equity"]
        assets = stmt["total_assets"]
        cur_a = stmt["current_assets"]
        cur_l = stmt["current_liabilities"]
        ebit = stmt["ebit"]
        op_inc = stmt["operating_income"]
        int_exp = stmt["interest_expense"]

        de = safe_div(debt, equity, require_positive_den=True, digits=3)
        da = safe_div(debt, assets, require_positive_den=True, digits=3)
        eq_to_assets = safe_div(equity, assets, require_positive_den=True, digits=3)

        missing_reasons: dict[str, str] = {}
        if debt is None:
            missing_reasons["debt_to_equity"] = "total_debt not reported on IFRS balance sheet."

        if is_bank:
            cur_ratio = None
            int_cov = None
            int_cov_source = "not_applicable_bank"
            missing_reasons["current_ratio"] = "Banks do not segregate current vs non-current assets/liabilities."
            missing_reasons["interest_coverage_ratio"] = "Interest/markup expense is core cost of funds for banks."
        else:
            cur_ratio = safe_div(cur_a, cur_l, require_positive_den=True, digits=2)
            if cur_ratio is None:
                missing_reasons["current_ratio"] = "current_assets or current_liabilities unavailable."

            numerator = ebit if ebit is not None else op_inc
            if int_exp is None:
                int_cov = None
                int_cov_source = "unavailable_missing_interest_expense"
                missing_reasons["interest_coverage_ratio"] = "interest_expense not reported on IFRS income statement."
            elif abs(int_exp) == 0.0:
                int_cov = None
                int_cov_source = "zero_interest_expense"
                missing_reasons["interest_coverage_ratio"] = "Reported interest_expense is 0 PKR (virtually unlevered)."
            elif numerator is None:
                int_cov = None
                int_cov_source = "unavailable_missing_ebit"
                missing_reasons["interest_coverage_ratio"] = "EBIT and operating_income unavailable."
            else:
                int_cov = safe_float(numerator / abs(int_exp), 2)
                int_cov_source = "ebit_over_interest_expense" if ebit is not None else "operating_income_over_interest_expense"

        return {
            "period_end_date": stmt["period_end_date"].isoformat(),
            "debt_to_equity": de,
            "debt_to_assets": da,
            "equity_to_assets": eq_to_assets,
            "current_ratio": cur_ratio,
            "interest_coverage_ratio": int_cov,
            "interest_coverage_source": int_cov_source,
            "total_debt_pkr": safe_float(debt, 0),
            "common_equity_pkr": safe_float(equity, 0),
            "cash_and_equivalents_pkr": safe_float(stmt["cash_and_equivalents"], 0),
            "missing_reasons": missing_reasons,
        }

    def _analyze_growth(
        self,
        all_periods: list[dict[str, Any]],
        complete_periods: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if len(complete_periods) < 2:
            return {
                "status": "INSUFFICIENT_PERIODS",
                "periods_count": len(complete_periods),
                "revenue_growth_yoy_pct": None,
                "net_income_growth_yoy_pct": None,
                "eps_growth_yoy_pct": None,
                "notes": ["Fewer than 2 complete disclosed annual periods available as of cutoff."],
            }

        cur = complete_periods[-1]
        prev = complete_periods[-2]
        gap_days = (cur["period_end_date"] - prev["period_end_date"]).days
        is_approx_1y = 300 <= gap_days <= 430

        def _yoy_pct(v_cur: Optional[float], v_prev: Optional[float]) -> Optional[float]:
            if v_cur is None or v_prev is None or v_prev == 0:
                return None
            return safe_float(((v_cur - v_prev) / abs(v_prev)) * 100.0, 2)

        rev_g = _yoy_pct(cur["total_revenue"], prev["total_revenue"]) if is_approx_1y else None
        ni_g = _yoy_pct(cur["net_income"], prev["net_income"]) if is_approx_1y else None
        eps_g = _yoy_pct(cur["effective_eps"], prev["effective_eps"]) if is_approx_1y else None

        notes: list[str] = []
        rev_cagr = None
        ni_cagr = None
        if not is_approx_1y:
            years = gap_days / 365.25
            notes.append(
                f"Prior complete period ({prev['period_end_date']}) is {gap_days}d ({years:.1f}Y) before {cur['period_end_date']} due to an incomplete intermediate filing; strictly 1Y YoY metrics are suppressed unless available in the 1Y window."
            )
            # Recover strictly 1Y YoY figures from any partial period within 300-430 days if populated
            for p in reversed(all_periods[:-1]):
                if 300 <= (cur["period_end_date"] - p["period_end_date"]).days <= 430:
                    if rev_g is None:
                        rev_g = _yoy_pct(cur["total_revenue"], p["total_revenue"])
                    if ni_g is None and cur["net_income"] is not None and p["net_income"] is not None and p["net_income"] != 0:
                        ni_g = _yoy_pct(cur["net_income"], p["net_income"])
                        notes.append(f"Net Income 1Y YoY uses disclosed {p['period_end_date']} net income ({ni_g:+.1f}%).")
                    if eps_g is None:
                        eps_g = _yoy_pct(cur["effective_eps"], p["effective_eps"])
                    break

        if len(complete_periods) >= 3:
            first = complete_periods[0]
            span_yrs = (cur["period_end_date"] - first["period_end_date"]).days / 365.25
            if span_yrs >= 1.8:
                if cur["total_revenue"] and first["total_revenue"] and cur["total_revenue"] > 0 and first["total_revenue"] > 0:
                    rev_cagr = safe_float(((cur["total_revenue"] / first["total_revenue"]) ** (1.0 / span_yrs) - 1.0) * 100.0, 2)
                if cur["net_income"] and first["net_income"] and cur["net_income"] > 0 and first["net_income"] > 0:
                    ni_cagr = safe_float(((cur["net_income"] / first["net_income"]) ** (1.0 / span_yrs) - 1.0) * 100.0, 2)

        return {
            "status": "OK",
            "comparison_current_period": cur["period_end_date"].isoformat(),
            "comparison_prior_period": prev["period_end_date"].isoformat(),
            "comparison_span_days": int(gap_days),
            "is_1y_comparable": is_approx_1y,
            "revenue_growth_yoy_pct": rev_g,
            "net_income_growth_yoy_pct": ni_g,
            "eps_growth_yoy_pct": eps_g,
            "multi_year_revenue_cagr_pct": rev_cagr,
            "multi_year_net_income_cagr_pct": ni_cagr,
            "notes": notes,
        }

    def _analyze_cash_flow(self, complete_periods: list[dict[str, Any]]) -> dict[str, Any]:
        cf_periods = [p for p in complete_periods if p["operating_cash_flow"] is not None or p["effective_fcf"] is not None]
        if not cf_periods:
            return {"status": "UNAVAILABLE", "operating_cash_flow_pkr": None, "free_cash_flow_pkr": None}

        latest = cf_periods[-1]
        ocf = latest["operating_cash_flow"]
        capex = latest["capital_expenditure"]
        fcf = latest["effective_fcf"]
        rev = latest["total_revenue"]
        ni = latest["net_income"]

        fcf_margin_pct = safe_float(safe_div(fcf, rev, require_positive_den=True) * 100.0, 2) if (fcf is not None and rev and rev > 0) else None
        ocf_to_ni = safe_div(ocf, ni, require_positive_den=True, digits=2)

        ocf_vals = [p["operating_cash_flow"] for p in cf_periods if p["operating_cash_flow"] is not None]
        fcf_vals = [p["effective_fcf"] for p in cf_periods if p["effective_fcf"] is not None]
        pos_fcf_years = sum(1 for v in fcf_vals if v > 0)

        cf_trend = "SINGLE_PERIOD"
        if len(ocf_vals) >= 2:
            if ocf_vals[-1] > ocf_vals[0] * 1.15 and ocf_vals[-1] > 0:
                cf_trend = "IMPROVING"
            elif ocf_vals[-1] < ocf_vals[0] * 0.85:
                cf_trend = "DECLINING"
            else:
                cf_trend = "STABLE"

        return {
            "status": "OK",
            "period_end_date": latest["period_end_date"].isoformat(),
            "operating_cash_flow_pkr": safe_float(ocf, 0),
            "capital_expenditure_pkr": safe_float(capex, 0),
            "free_cash_flow_pkr": safe_float(fcf, 0),
            "fcf_margin_pct": fcf_margin_pct,
            "ocf_to_net_income_ratio": ocf_to_ni,
            "cash_flow_trend": cf_trend,
            "positive_fcf_periods": f"{pos_fcf_years}/{len(fcf_vals)}",
            "history": [
                {
                    "period_end_date": p["period_end_date"].isoformat(),
                    "operating_cash_flow_pkr": safe_float(p["operating_cash_flow"], 0),
                    "capital_expenditure_pkr": safe_float(p["capital_expenditure"], 0),
                    "free_cash_flow_pkr": safe_float(p["effective_fcf"], 0),
                }
                for p in cf_periods
            ],
        }

    def _analyze_dividends(
        self,
        *,
        sym_payouts: dict[str, Any],
        complete_periods: list[dict[str, Any]],
        mkt_snap: dict[str, Any],
        mkt_cutoff: date,
        notes: list[str],
    ) -> dict[str, Any]:
        events = sym_payouts["events"]
        ttm_dps = sym_payouts["ttm_adjusted_dps_pkr"]
        if sym_payouts["corrected_face_value_count"] > 0:
            notes.append(
                f"{sym_payouts['corrected_face_value_count']} dividend record(s) in corporate_payouts had scraper DPS/face-value mismatch and were normalized using payout_percentage * face_value / 100."
            )

        # Combine with multi-year IFRS CASH_FLOW.cash_dividends_paid for full 4-5Y consistency check
        cf_div_history = []
        paid_years = 0
        consecutive_paid = 0
        for p in complete_periods:
            cd = p["cash_dividends_paid"]
            ni = p["net_income"]
            fcf = p["effective_fcf"]
            paid_amt = abs(cd) if cd is not None else None
            payout_ratio = safe_float((paid_amt / ni) * 100.0, 1) if (paid_amt is not None and ni and ni > 0) else None
            fcf_cov = safe_div(fcf, paid_amt, require_positive_den=True, digits=2) if (paid_amt is not None and paid_amt > 0) else None
            cf_div_history.append(
                {
                    "period_end_date": p["period_end_date"].isoformat(),
                    "cash_dividends_paid_pkr": safe_float(paid_amt, 0),
                    "payout_ratio_pct": payout_ratio,
                    "fcf_dividend_coverage": fcf_cov,
                }
            )
            if paid_amt is not None and paid_amt > 0:
                paid_years += 1
                consecutive_paid += 1
            else:
                consecutive_paid = 0

        if not events:
            notes.append(
                "No cash dividend announcements found in corporate_payouts <= cutoff (table mainly archives FY2025-2026 payouts); multi-year dividend record uses CASH_FLOW.cash_dividends_paid."
            )

        price = mkt_snap.get("close_pkr")
        mcap = mkt_snap.get("market_cap_pkr")
        ann_yield = safe_float((ttm_dps / price) * 100.0, 2) if (ttm_dps and price and price > 0) else None
        latest_cf_paid = cf_div_history[-1]["cash_dividends_paid_pkr"] if cf_div_history else None
        cf_yield = safe_float((latest_cf_paid / mcap) * 100.0, 2) if (latest_cf_paid is not None and mcap and mcap > 0) else None

        if paid_years == len(complete_periods) and len(complete_periods) >= 3:
            consistency = "CONSISTENT_PAYER"
        elif paid_years >= 2:
            consistency = "REGULAR_PAYER"
        elif paid_years == 1 or len(events) > 0:
            consistency = "OCCASIONAL_PAYER"
        else:
            consistency = "NO_DIVIDENDS_RECORDED"

        return {
            "consistency": consistency,
            "ifrs_periods_with_cash_dividends": f"{paid_years}/{len(complete_periods)}",
            "consecutive_recent_ifrs_years_paid": consecutive_paid,
            "ttm_announced_dps_pkr": ttm_dps,
            "announced_ttm_dividend_yield_pct": ann_yield,
            "latest_cash_flow_dividends_pkr": latest_cf_paid,
            "latest_cash_payout_ratio_pct": cf_div_history[-1]["payout_ratio_pct"] if cf_div_history else None,
            "latest_fcf_dividend_coverage": cf_div_history[-1]["fcf_dividend_coverage"] if cf_div_history else None,
            "cash_flow_implied_yield_pct": cf_yield,
            "annual_cash_flow_dividends": cf_div_history,
            "recent_announcements": events[:10],
        }

    def _analyze_sector_comparison(
        self,
        *,
        conn: Connection,
        sym: str,
        meta: dict[str, Any],
        target_period: dict[str, Any],
        target_metrics: dict[str, Any],
        is_bank: bool,
        mkt_cutoff: date,
    ) -> dict[str, Any]:
        sector = (meta.get("sector") or "").strip()
        if not meta.get("has_classified_sector"):
            return {
                "status": "INSUFFICIENT_SECTOR_DATA",
                "sector": sector or "OTHER / UNCLASSIFIED",
                "reason": "Stock sector is unclassified ('OTHER / UNCLASSIFIED'); sector peer comparison omitted.",
                "comparable_peers_count": 0,
            }

        peer_rows = conn.execute(
            text(
                """
                SELECT UPPER(symbol) AS symbol
                FROM companies
                WHERE sector = :sec AND UPPER(symbol) != :sym
                ORDER BY symbol
                """
            ),
            {"sec": sector, "sym": sym},
        ).scalars().all()

        if len(peer_rows) < MIN_SECTOR_PEERS:
            return {
                "status": "INSUFFICIENT_SECTOR_DATA",
                "sector": sector,
                "reason": f"Sector '{sector}' has fewer than {MIN_SECTOR_PEERS} other listed peers in companies table ({len(peer_rows)}).",
                "comparable_peers_count": len(peer_rows),
            }

        peer_stmts = self._load_pit_statements_for_symbols(conn, list(peer_rows), mkt_cutoff)
        target_pe = target_period["period_end_date"]

        # Select peers whose latest complete statement falls within +/- 370 days of target's period_end_date
        comparable_peers: list[dict[str, Any]] = []
        for psym, plist in peer_stmts.items():
            comp_list = [p for p in plist if p["has_complete_core"]]
            if not comp_list:
                continue
            cand = None
            for p in reversed(comp_list):
                if abs((p["period_end_date"] - target_pe).days) <= 370:
                    cand = p
                    break
            if cand is None:
                continue
            prev_cand = comp_list[comp_list.index(cand) - 1] if comp_list.index(cand) >= 1 else None
            snap = self._load_market_snapshot(conn, psym, mkt_cutoff)
            comparable_peers.append((psym, cand, prev_cand, snap))

        if len(comparable_peers) < MIN_SECTOR_PEERS:
            return {
                "status": "INSUFFICIENT_SECTOR_DATA",
                "sector": sector,
                "reason": f"Sector '{sector}' has only {len(comparable_peers)} peer(s) with comparable IFRS reporting dates (<= 370d gap from {target_pe}) on or before {mkt_cutoff}; minimum {MIN_SECTOR_PEERS} required.",
                "comparable_peers_count": len(comparable_peers),
            }

        peer_metric_lists: dict[str, list[float]] = {
            "roe_pct": [],
            "roa_pct": [],
            "net_margin_pct": [],
            "operating_margin_pct": [],
            "pe_ratio": [],
            "pb_ratio": [],
            "debt_to_equity": [],
            "current_ratio": [],
            "interest_coverage_ratio": [],
            "revenue_growth_yoy_pct": [],
            "cash_flow_implied_yield_pct": [],
        }
        peer_details: list[dict[str, Any]] = []

        for psym, cand, prev_cand, snap in comparable_peers:
            ni = cand["net_income"]
            rev = cand["total_revenue"]
            eq = cand["common_stock_equity"]
            assets = cand["total_assets"]
            mcap = snap.get("market_cap_pkr")
            price = snap.get("close_pkr")
            shares = cand["shares"]
            eff_mcap = mcap if (mcap and mcap > 0) else (price * shares if price and shares else None)

            p_roe = safe_div(ni, eq, require_positive_den=True)
            p_roa = safe_div(ni, assets, require_positive_den=True)
            p_nm = safe_div(ni, rev, require_positive_den=True)
            p_om = None if is_bank else safe_div(cand["operating_income"], rev, require_positive_den=True)
            p_pe = safe_div(eff_mcap, ni, require_positive_den=True) if eff_mcap else None
            p_pb = safe_div(eff_mcap, eq, require_positive_den=True) if eff_mcap else None
            p_de = safe_div(cand["total_debt"], eq, require_positive_den=True)
            p_cr = None if is_bank else safe_div(cand["current_assets"], cand["current_liabilities"], require_positive_den=True)
            num_ic = cand["ebit"] if cand["ebit"] is not None else cand["operating_income"]
            p_ic = (
                None
                if (is_bank or cand["interest_expense"] is None or abs(cand["interest_expense"]) == 0)
                else safe_div(num_ic, abs(cand["interest_expense"]))
            )
            p_rev_g = None
            if prev_cand and prev_cand["total_revenue"] and cand["total_revenue"] is not None:
                if 300 <= (cand["period_end_date"] - prev_cand["period_end_date"]).days <= 430:
                    p_rev_g = ((cand["total_revenue"] - prev_cand["total_revenue"]) / abs(prev_cand["total_revenue"])) * 100.0
            p_div_y = None
            if eff_mcap and eff_mcap > 0 and cand["cash_dividends_paid"] is not None:
                p_div_y = (abs(cand["cash_dividends_paid"]) / eff_mcap) * 100.0

            if p_roe is not None:
                peer_metric_lists["roe_pct"].append(p_roe * 100.0)
            if p_roa is not None:
                peer_metric_lists["roa_pct"].append(p_roa * 100.0)
            if p_nm is not None:
                peer_metric_lists["net_margin_pct"].append(p_nm * 100.0)
            if p_om is not None:
                peer_metric_lists["operating_margin_pct"].append(p_om * 100.0)
            if p_pe is not None and 0 < p_pe < 200:
                peer_metric_lists["pe_ratio"].append(p_pe)
            if p_pb is not None and 0 < p_pb < 50:
                peer_metric_lists["pb_ratio"].append(p_pb)
            if p_de is not None:
                peer_metric_lists["debt_to_equity"].append(p_de)
            if p_cr is not None:
                peer_metric_lists["current_ratio"].append(p_cr)
            if p_ic is not None:
                peer_metric_lists["interest_coverage_ratio"].append(p_ic)
            if p_rev_g is not None:
                peer_metric_lists["revenue_growth_yoy_pct"].append(p_rev_g)
            if p_div_y is not None:
                peer_metric_lists["cash_flow_implied_yield_pct"].append(p_div_y)

            peer_details.append(
                {
                    "symbol": psym,
                    "period_end_date": cand["period_end_date"].isoformat(),
                    "effective_pub_date": cand["effective_pub_date"].isoformat(),
                }
            )

        target_map = {
            "roe_pct": target_metrics["profitability"].get("roe_pct"),
            "roa_pct": target_metrics["profitability"].get("roa_pct"),
            "net_margin_pct": target_metrics["profitability"].get("net_margin_pct"),
            "operating_margin_pct": target_metrics["profitability"].get("operating_margin_pct"),
            "pe_ratio": target_metrics["valuation"].get("pe_ratio"),
            "pb_ratio": target_metrics["valuation"].get("pb_ratio"),
            "debt_to_equity": target_metrics["financial_health"].get("debt_to_equity"),
            "current_ratio": target_metrics["financial_health"].get("current_ratio"),
            "interest_coverage_ratio": target_metrics["financial_health"].get("interest_coverage_ratio"),
            "revenue_growth_yoy_pct": target_metrics["growth"].get("revenue_growth_yoy_pct"),
            "cash_flow_implied_yield_pct": target_metrics["dividends"].get("cash_flow_implied_yield_pct"),
        }

        lower_is_better = {"pe_ratio", "pb_ratio", "debt_to_equity"}
        benchmarks: dict[str, Any] = {}
        for k, vals in peer_metric_lists.items():
            t_val = target_map.get(k)
            if len(vals) < MIN_SECTOR_PEERS:
                continue
            med = float(np.median(vals))
            status = None
            diff = None
            if t_val is not None:
                diff = safe_float(t_val - med, 2)
                if k in lower_is_better:
                    status = "FAVORABLE_BELOW_MEDIAN" if t_val < med * 0.95 else ("ELEVATED_ABOVE_MEDIAN" if t_val > med * 1.05 else "IN_LINE_WITH_SECTOR")
                else:
                    status = "OUTPERFORMING_ABOVE_MEDIAN" if t_val > med * 1.05 else ("LAGGING_BELOW_MEDIAN" if t_val < med * 0.95 else "IN_LINE_WITH_SECTOR")

            benchmarks[k] = {
                "company_value": safe_float(t_val, 2),
                "sector_median": safe_float(med, 2),
                "diff_vs_median": diff,
                "peers_with_metric": len(vals),
                "relative_position": status,
            }

        return {
            "status": "OK",
            "sector": sector,
            "comparison_window_rule": f"Peers within +/-370 calendar days of target period_end_date ({target_pe}), disclosed <= {mkt_cutoff}",
            "comparable_peers_count": len(comparable_peers),
            "comparable_peers": peer_details,
            "benchmarks": benchmarks,
        }

    def _synthesize_assessment(
        self,
        *,
        meta: dict[str, Any],
        is_bank: bool,
        latest_complete: dict[str, Any],
        profitability: dict[str, Any],
        valuation: dict[str, Any],
        financial_health: dict[str, Any],
        growth: dict[str, Any],
        cash_flow: dict[str, Any],
        dividends: dict[str, Any],
        sector_comparison: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Compute transparent deterministic Fundamental Score in [0, 100] from
        applicable domains (renormalized over available pillar weights) plus
        explicit strengths, weaknesses, and conflicting signals.
        """
        strengths: list[str] = []
        weaknesses: list[str] = []
        conflicts: list[str] = []

        # Pillar 1: Profitability [0..100] (weight 0.30)
        prof_pts: list[float] = []
        roe = profitability.get("roe_pct")
        roa = profitability.get("roa_pct")
        nm = profitability.get("net_margin_pct")
        om = profitability.get("operating_margin_pct")
        if roe is not None:
            prof_pts.append(max(0.0, min(100.0, (roe / 25.0) * 100.0)))
            if roe >= 18.0:
                strengths.append(f"Strong Return on Equity (ROE = {roe:.1f}%).")
            elif roe < 8.0:
                weaknesses.append(f"Subdued Return on Equity (ROE = {roe:.1f}%).")
        if roa is not None:
            roa_target = 2.0 if is_bank else 12.0
            prof_pts.append(max(0.0, min(100.0, (roa / roa_target) * 100.0)))
        if nm is not None:
            prof_pts.append(max(0.0, min(100.0, (nm / 20.0) * 100.0)))
            if nm >= 15.0:
                strengths.append(f"High Net Margin of {nm:.1f}%.")
            elif nm < 4.0:
                weaknesses.append(f"Thin Net Margin ({nm:.1f}%).")
        if om is not None and not is_bank:
            prof_pts.append(max(0.0, min(100.0, (om / 25.0) * 100.0)))
        prof_score = float(np.mean(prof_pts)) if prof_pts else None

        # Pillar 2: Valuation [0..100] (weight 0.20)
        val_pts: list[float] = []
        pe = valuation.get("pe_ratio")
        pb = valuation.get("pb_ratio")
        bm = sector_comparison.get("benchmarks", {}) if sector_comparison.get("status") == "OK" else {}
        if pe is not None:
            # PSX normalized P/E attractiveness anchor (~4x very cheap=95, ~10x=65, ~20x=30)
            s_pe = max(5.0, min(95.0, 110.0 - pe * 4.5))
            val_pts.append(s_pe)
            if pe <= 8.0:
                strengths.append(f"Low P/E multiple ({pe:.2f}x; Earnings Yield {valuation.get('earnings_yield_pct')}%).")
            elif pe >= 18.0:
                weaknesses.append(f"Elevated P/E valuation ({pe:.2f}x).")
        elif latest_complete["net_income"] is not None and latest_complete["net_income"] <= 0:
            val_pts.append(15.0)
            weaknesses.append("Negative or zero earnings renders P/E unavailable.")

        if pb is not None:
            s_pb = max(10.0, min(95.0, 100.0 - pb * 22.0))
            val_pts.append(s_pb)
            if "pb_ratio" in bm and bm["pb_ratio"].get("relative_position") == "FAVORABLE_BELOW_MEDIAN":
                strengths.append(
                    f"P/B ({pb:.2f}x) trades below sector median ({bm['pb_ratio']['sector_median']:.2f}x)."
                )
        val_score = float(np.mean(val_pts)) if val_pts else None

        # Pillar 3: Financial Health [0..100] (weight 0.20)
        hlth_pts: list[float] = []
        de = financial_health.get("debt_to_equity")
        cr = financial_health.get("current_ratio")
        ic = financial_health.get("interest_coverage_ratio")
        if de is not None:
            hlth_pts.append(max(10.0, min(100.0, 100.0 - de * 40.0)))
            if de <= 0.35:
                strengths.append(f"Conservative leverage (Debt/Equity = {de:.2f}x).")
            elif de >= 1.5 and not is_bank:
                weaknesses.append(f"Elevated leverage (Debt/Equity = {de:.2f}x).")
        if cr is not None and not is_bank:
            hlth_pts.append(max(10.0, min(100.0, (cr / 2.0) * 100.0)))
            if cr >= 1.5:
                strengths.append(f"Healthy short-term liquidity (Current Ratio = {cr:.2f}x).")
            elif cr < 1.0:
                weaknesses.append(f"Tight working capital liquidity (Current Ratio = {cr:.2f}x < 1.0).")
        if ic is not None and not is_bank:
            hlth_pts.append(max(5.0, min(100.0, (ic / 8.0) * 100.0)))
            if ic >= 6.0:
                strengths.append(f"Strong Interest Coverage Ratio of {ic:.1f}x.")
            elif ic < 2.0:
                weaknesses.append(f"Thin Interest Coverage Ratio ({ic:.2f}x).")
        hlth_score = float(np.mean(hlth_pts)) if hlth_pts else None

        # Pillar 4: Growth [0..100] (weight 0.15)
        gr_pts: list[float] = []
        rev_g = growth.get("revenue_growth_yoy_pct")
        ni_g = growth.get("net_income_growth_yoy_pct")
        eps_g = growth.get("eps_growth_yoy_pct")
        if rev_g is not None:
            gr_pts.append(max(0.0, min(100.0, 50.0 + rev_g * 1.2)))
            if rev_g >= 15.0:
                strengths.append(f"Solid revenue growth ({rev_g:+.1f}% YoY).")
            elif rev_g < -5.0:
                weaknesses.append(f"Revenue contraction ({rev_g:+.1f}% YoY).")
        if ni_g is not None:
            gr_pts.append(max(0.0, min(100.0, 50.0 + ni_g * 1.0)))
            if ni_g >= 15.0:
                strengths.append(f"Strong net profit expansion ({ni_g:+.1f}% YoY).")
            elif ni_g < -10.0:
                weaknesses.append(f"Net income declined ({ni_g:+.1f}% YoY).")
        gr_score = float(np.mean(gr_pts)) if gr_pts else None

        # Pillar 5: Cash Flow & Dividends [0..100] (weight 0.15)
        cf_pts: list[float] = []
        fcf = cash_flow.get("free_cash_flow_pkr")
        ocf_ni = cash_flow.get("ocf_to_net_income_ratio")
        div_y = valuation.get("dividend_yield_pct")
        if ocf_ni is not None:
            cf_pts.append(max(10.0, min(100.0, ocf_ni * 70.0)))
            if ocf_ni >= 1.0:
                strengths.append(f"High cash conversion (OCF / Net Income = {ocf_ni:.2f}x).")
            elif ocf_ni < 0.6:
                weaknesses.append(f"Weak earnings cash conversion (OCF / Net Income = {ocf_ni:.2f}x).")
        if fcf is not None:
            cf_pts.append(80.0 if fcf > 0 else 25.0)
            if fcf < 0:
                weaknesses.append(f"Negative Free Cash Flow ({fcf / 1e9:+.2f}B PKR).")
        if div_y is not None:
            cf_pts.append(max(20.0, min(100.0, 30.0 + div_y * 6.0)))
            if div_y >= 6.0:
                strengths.append(f"Attractive dividend yield of {div_y:.2f}%.")
        cf_score = float(np.mean(cf_pts)) if cf_pts else None

        raw_weights = {
            "profitability": (0.30, prof_score),
            "valuation": (0.20, val_score),
            "financial_health": (0.20, hlth_score),
            "growth": (0.15, gr_score),
            "cash_flow_and_dividends": (0.15, cf_score),
        }
        avail = {k: (w, s) for k, (w, s) in raw_weights.items() if s is not None}
        w_sum = sum(w for w, _ in avail.values())
        fund_score = safe_float(sum((w / w_sum) * s for w, s in avail.values()), 1) if w_sum > 0 else None

        # Conflict checks
        if roe is not None and roe >= 18.0 and pe is not None and pe >= 18.0:
            conflicts.append("High profitability (ROE >= 18%) is partially priced in by an elevated P/E multiple.")
        if pe is not None and pe <= 6.5 and ((ni_g is not None and ni_g < -10.0) or (rev_g is not None and rev_g < -5.0)):
            conflicts.append("Optically cheap P/E multiple coincides with contracting earnings/revenue (value-trap risk).")
        if latest_complete["net_income"] and latest_complete["net_income"] > 0 and fcf is not None and fcf < 0:
            conflicts.append("Company is accounting-profitable while generating negative Free Cash Flow.")
        if om is not None and not is_bank and bm.get("net_margin_pct", {}).get("relative_position") == "OUTPERFORMING_ABOVE_MEDIAN" and pe is not None and bm.get("pe_ratio", {}).get("relative_position") == "ELEVATED_ABOVE_MEDIAN":
            conflicts.append("Superior sector margins command a valuation premium vs sector P/E median.")
        if sector_comparison.get("status") == "INSUFFICIENT_SECTOR_DATA":
            conflicts.append(sector_comparison.get("reason"))

        if fund_score is None:
            assessment = "INSUFFICIENT_DATA"
        elif fund_score >= 72.0:
            assessment = "STRONG"
        elif fund_score >= 55.0:
            assessment = "CONSTRUCTIVE"
        elif fund_score >= 40.0:
            assessment = "MODERATE"
        else:
            assessment = "WEAK"

        sec_note = (
            f"vs {sector_comparison['comparable_peers_count']} {meta.get('sector')} peers"
            if sector_comparison.get("status") == "OK"
            else "without sufficient sector benchmark"
        )
        summary = (
            f"Fundamental quality is {assessment} (score {fund_score if fund_score is not None else 'N/A'}/100, {sec_note}): "
            f"ROE {roe if roe is not None else 'N/A'}%, Net Margin {nm if nm is not None else 'N/A'}%, "
            f"P/E {pe if pe is not None else 'N/A'}x, P/B {pb if pb is not None else 'N/A'}x, "
            f"Dividend Yield {div_y if div_y is not None else 'N/A'}%."
        )

        return {
            "strengths": strengths,
            "weaknesses": weaknesses,
            "conflicting_signals": conflicts,
            "overall_assessment": assessment,
            "fundamental_score": fund_score,
            "summary": summary,
            "score_methodology": {
                "scale": "[0.0, 100.0] weighted over applicable IFRS domains (renormalized for banking N/A ratios)",
                "weights": {k: w for k, (w, _) in raw_weights.items()},
                "component_scores": {k: safe_float(s, 1) for k, (_, s) in raw_weights.items()},
                "rating_bands": {
                    "STRONG": ">= 72",
                    "CONSTRUCTIVE": "[55, 72)",
                    "MODERATE": "[40, 55)",
                    "WEAK": "< 40",
                },
            },
        }

