"""
PSXpert - Stock-Specific News Impact Engine
Calculates asymmetric, stock-level transmission of macroeconomic, sector,
and corporate news to individual PSX-listed equities.

Key Architectural Principles:
1. Macro-to-Stock Asymmetry: A single news event (e.g., oil price hike, SBP rate hike,
   PKR devaluation) affects different companies in opposite directions.
   - Oil price surge -> Upstream E&P (OGDC, PPL, MARI) POSITIVE; OMCs (PSO) NEGATIVE/MIXED;
     High energy consumers (Cement: LUCK, DGKC) NEGATIVE.
   - SBP Interest Rate hike -> Commercial Banks (HBL, MCB, MEBL) POSITIVE (NIM expansion);
     High-leverage cyclicals (Cements, Textiles, Autos) NEGATIVE (finance cost drag).
   - PKR Depreciation -> IT exporters (SYS, TRG) and Textile exporters (NML) POSITIVE;
     Import-dependent assemblers (INDU, PSMC) and Pharma (SEARL) NEGATIVE.
2. Anti-Leakage Point-In-Time Timestamp Alignment:
   - News published after PSX market close (16:00 PKT) or on weekends/holidays is
     aligned to session t+1.
   - Intraday news (09:15 - 16:00 PKT) or date-only news is conservatively aligned to
     session t+1 for daily prediction to eliminate lookahead bias.
3. Multi-Horizon Aggregation:
   - 1-day shock, 7-day exponentially decayed impact, and 30-day cumulative momentum.
"""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple


# Transmission Sensitivity Matrix: Beta coefficients in [-1.0, +1.0]
# Positive beta = company benefits when theme moves in headline direction
# Negative beta = company suffers when theme moves in headline direction
SECTOR_TRANSMISSION_MATRIX: Dict[str, Dict[str, float]] = {
    # 1. Crude Oil / Energy Benchmark Price Hike
    "OIL_PRICE_SURGE": {
        # Upstream E&P: Dollar-indexed wellhead gas & crude pricing directly boosts revenue
        "OGDC": 1.0,
        "PPL": 1.0,
        "MARI": 0.9,
        "POL": 1.0,
        # Oil Marketing Companies: Higher procurement costs, consumer demand destruction, regulated margins
        "PSO": -0.6,
        "APL": -0.4,
        "SHEL": -0.5,
        "SNGP": -0.3,
        "SSGC": -0.3,
        # Refineries: Inventory gain short term, but higher crude feedstock cost & working capital strain
        "PRL": 0.2,
        "ATRL": 0.3,
        "NRL": 0.1,
        "CNERGY": -0.2,
        # Heavy Energy Consumers: Higher power & transport logistics cost
        "LUCK": -0.7,
        "DGKC": -0.8,
        "MLCF": -0.7,
        "FCCL": -0.7,
        "CHCC": -0.7,
        # Power IPPs: Fuel cost pass-through delayed by circular debt
        "HUBC": -0.4,
        "KEL": -0.5,
        "KAPCO": -0.4,
        # General Market: Macro trade balance deterioration
        "KSE100": -0.3,
    },

    # 2. State Bank Interest Rate Hike / Monetary Tightening / Rising KIBOR
    "RATE_HIKE": {
        # Commercial Banks: Assets reprice faster than liabilities -> Net Interest Margin (NIM) expansion
        "HBL": 1.0,
        "MCB": 1.0,
        "UBL": 1.0,
        "MEBL": 0.9,
        "BAHL": 0.9,
        "BAFL": 0.9,
        "NBP": 0.8,
        "FABL": 0.8,
        "AKBL": 0.8,
        # Highly Leveraged Capital-Intensive Cyclicals: Surging finance costs compress EBITDA/PAT
        "DGKC": -1.0,
        "MLCF": -0.9,
        "LUCK": -0.6,  # Strong cash reserves partially buffer Lucky Cement
        "FCCL": -0.8,
        "CHCC": -0.8,
        "NML": -0.9,
        "GATM": -0.9,
        "PAEL": -0.9,
        "INDU": -0.7,  # Auto consumer leasing collapses
        "PSMC": -0.8,
        "HONDA": -0.8,
        # General Market: Discount rate hike compresses equity PE valuation multiples
        "KSE100": -0.7,
    },

    # 3. State Bank Rate Cut / Monetary Easing
    "RATE_CUT": {
        "HBL": -0.3,
        "MCB": -0.3,
        "UBL": -0.3,
        "MEBL": -0.2,
        "BAHL": -0.2,
        "BAFL": -0.2,
        # Cyclicals celebrate massive finance cost relief
        "DGKC": 1.0,
        "MLCF": 1.0,
        "LUCK": 0.8,
        "FCCL": 0.9,
        "CHCC": 0.9,
        "NML": 1.0,
        "GATM": 0.9,
        "PAEL": 1.0,
        "INDU": 0.9,
        "PSMC": 0.9,
        "HONDA": 0.9,
        "KSE100": 1.0,
    },

    # 4. PKR Currency Depreciation / Rupee Devaluation
    "PKR_DEPRECIATION": {
        # IT Exporters: Revenue in USD, cost structure in PKR -> massive margin expansion
        "SYS": 1.0,
        "TRG": 0.9,
        "NETSOL": 0.9,
        "AVN": 0.8,
        # Textile Exporters: Foreign currency competitiveness boost
        "NML": 0.8,
        "GATM": 0.8,
        "ILP": 0.9,
        # Upstream E&P: Dollar-denominated wellhead contracts
        "OGDC": 0.7,
        "PPL": 0.7,
        "MARI": 0.6,
        # Import-Dependent Cyclicals: Soaring CKD kit costs, API costs, imported coal
        "INDU": -1.0,
        "PSMC": -1.0,
        "HONDA": -1.0,
        "SEARL": -0.9,
        "ABOT": -0.8,
        "GLAXO": -0.8,
        "DGKC": -0.6,
        "MLCF": -0.6,
        "KSE100": -0.5,
    },

    # 5. Inflation Surge (CPI Increase / Utility Tariff Hike)
    "INFLATION_SURGE": {
        "HBL": 0.4,
        "MEBL": 0.4,
        "MCB": 0.4,
        # Food & Consumer: Purchasing power destruction
        "NESTLE": -0.5,
        "UNITY": -0.6,
        "INDU": -0.7,
        "PSMC": -0.7,
        "LUCK": -0.5,
        "DGKC": -0.6,
        "KSE100": -0.6,
    },

    # 6. IMF Bailout Agreement / Sovereign External Inflows / Reserves Boost
    "IMF_INFLOW": {
        "KSE100": 1.0,
        "OGDC": 0.9,  # Enables circular debt settlement
        "PPL": 0.9,
        "PSO": 0.9,
        "HUBC": 0.8,
        "HBL": 0.8,
        "MEBL": 0.8,
        "MCB": 0.8,
        "UBL": 0.8,
        "LUCK": 0.7,
        "SYS": 0.5,
    },

    # 7. Circular Debt Payment / Energy Sector Settlement
    "CIRCULAR_DEBT_PAYMENT": {
        "OGDC": 1.0,
        "PPL": 1.0,
        "PSO": 1.0,
        "HUBC": 1.0,
        "KEL": 0.8,
        "SNGP": 0.8,
        "SSGC": 0.8,
        "KSE100": 0.7,
    },

    # 8. Gas Tariff Hike
    "GAS_TARIFF_HIKE": {
        "OGDC": 0.8,
        "PPL": 0.8,
        "MARI": 0.8,
        "SNGP": 0.7,
        "SSGC": 0.7,
        # Fertilizer: Cost of feedstock increases
        "ENGRO": -0.7,
        "FFC": -0.6,
        "FFBL": -0.8,
        "FATIMA": -0.7,
        # Textile & Industry: Higher production energy bill
        "NML": -0.7,
        "DGKC": -0.5,
    }
}


# Canonical Ticker & Alias Dictionary for PSX Equities
COMPANY_ALIASES: Dict[str, List[str]] = {
    "OGDC": ["OGDCL", "OIL AND GAS DEVELOPMENT COMPANY", "OIL & GAS DEVELOPMENT", "OGDC"],
    "PPL": ["PAKISTAN PETROLEUM LIMITED", "PAKISTAN PETROLEUM", "PPL"],
    "MARI": ["MARI PETROLEUM", "MARI GAS", "MARI"],
    "POL": ["PAKISTAN OILFIELDS LIMITED", "PAKISTAN OILFIELDS", "POL"],
    "PSO": ["PAKISTAN STATE OIL", "PAKISTAN STATE OIL COMPANY", "PSO"],
    "SHEL": ["SHELL PAKISTAN", "SHELL PAKISTAN LIMITED", "WAFI ENERGY SHELL", "SHEL"],
    "APL": ["ATTOCK PETROLEUM", "ATTOCK PETROLEUM LIMITED", "APL"],
    "SNGP": ["SUI NORTHERN GAS PIPELINES", "SUI NORTHERN", "SNGPL", "SNGP"],
    "SSGC": ["SUI SOUTHERN GAS COMPANY", "SUI SOUTHERN", "SSGC"],
    "ATRL": ["ATTOCK REFINERY", "ATTOCK REFINERY LIMITED", "ATRL"],
    "NRL": ["NATIONAL REFINERY", "NATIONAL REFINERY LIMITED", "NRL"],
    "PRL": ["PAKISTAN REFINERY", "PAKISTAN REFINERY LIMITED", "PRL"],
    "CNERGY": ["CNERGYICO PK", "CNERGYICO", "BYCO PETROLEUM", "BYCO", "CNERGY"],
    "MEBL": ["MEEZAN BANK", "MEEZAN BANK LIMITED", "MEEZAN", "MEBL"],
    "HBL": ["HABIB BANK", "HABIB BANK LIMITED", "HBL"],
    "UBL": ["UNITED BANK", "UNITED BANK LIMITED", "UBL"],
    "MCB": ["MCB BANK", "MCB BANK LIMITED", "MUSLIM COMMERCIAL BANK", "MCB"],
    "NBP": ["NATIONAL BANK OF PAKISTAN", "NATIONAL BANK", "NBP"],
    "BAFL": ["BANK ALFALAH", "BANK ALFALAH LIMITED", "ALFALAH", "BAFL"],
    "BAHL": ["BANK AL HABIB", "BANK AL HABIB LIMITED", "AL HABIB", "BAHL"],
    "FABL": ["FAYSAL BANK", "FAYSAL BANK LIMITED", "FABL"],
    "LUCK": ["LUCKY CEMENT", "LUCKY CEMENT LIMITED", "LUCKY", "LUCK"],
    "DGKC": ["D.G. KHAN CEMENT", "DG KHAN CEMENT", "DGKC"],
    "MLCF": ["MAPLE LEAF CEMENT", "MAPLE LEAF", "MLCF"],
    "CHCC": ["CHERAT CEMENT", "CHERAT CEMENT COMPANY", "CHCC"],
    "FCCL": ["FAUJI CEMENT", "FAUJI CEMENT COMPANY", "ASKARI CEMENT", "FCCL"],
    "ENGRO": ["ENGRO CORPORATION", "ENGRO CORP", "ENGRO FERTILIZERS", "EFERT", "ENGRO"],
    "FFC": ["FAUJI FERTILIZER COMPANY", "FAUJI FERTILIZER", "FFC"],
    "FFBL": ["FAUJI FERTILIZER BIN QASIM", "FFBL"],
    "FATIMA": ["FATIMA FERTILIZER", "FATIMA FERTILIZER COMPANY", "FATIMA"],
    "SYS": ["SYSTEMS LIMITED", "SYSTEMS LTD", "SYS"],
    "TRG": ["TRG PAKISTAN", "TRG PAKISTAN LIMITED", "THE RESOURCE GROUP", "TRG"],
    "NETSOL": ["NETSOL TECHNOLOGIES", "NETSOL"],
    "AVN": ["AVANCEON", "AVANCEON LIMITED", "AVN"],
    "HUBC": ["HUB POWER COMPANY", "HUB POWER", "HUBCO", "HUBC"],
    "KEL": ["K-ELECTRIC", "K ELECTRIC", "KARACHI ELECTRIC", "KESC", "KEL"],
    "KAPCO": ["KOT ADDU POWER", "KOT ADDU POWER COMPANY", "KAPCO"],
    "INDU": ["INDUS MOTOR COMPANY", "INDUS MOTOR", "TOYOTA PAKISTAN", "INDU"],
    "PSMC": ["PAK SUZUKI MOTOR", "PAK SUZUKI", "PSMC"],
    "HONDA": ["HONDA ATLAS CARS", "HONDA ATLAS", "HACPL"],
    "SEARL": ["THE SEARLE COMPANY", "SEARLE", "SEARL"],
    "ABOT": ["ABBOTT LABORATORIES PAKISTAN", "ABBOTT PAKISTAN", "ABOT"],
    "GLAXO": ["GLAXOSMITHKLINE PAKISTAN", "GSK PAKISTAN", "GLAXO"],
    "NML": ["NISHAT MILLS", "NISHAT MILLS LIMITED", "NML"],
    "GATM": ["GUL AHMED TEXTILE", "GUL AHMED", "GATM"],
    "ILP": ["INTERLOOP", "INTERLOOP LIMITED", "ILP"],
    "PAEL": ["PAK ELEKTRON", "PEL", "PAEL"],
    "KSE100": ["KSE-100", "KSE 100", "KSE100 INDEX", "PSX", "EQUITY MARKET", "BOURSE"]
}


# Pre-compiled Regex for Entity Matching
ENTITY_PATTERNS = {
    sym: re.compile(r"\b(" + "|".join(re.escape(a) for a in aliases) + r")\b", re.IGNORECASE)
    for sym, aliases in COMPANY_ALIASES.items()
}

# Macro Theme Patterns
THEME_PATTERNS = {
    "OIL_PRICE_SURGE": re.compile(
        r"\b(crude|brent|wti|oil prices?|petroleum|fuel prices?)\b.*\b(surges?|jumps?|rises?|hikes?|gains?|climbs?|rallies|highs?|elevated|expensive)\b|"
        r"\b(surges?|jumps?|rises?|hikes?|rally|high)\b.*\b(crude|brent|wti|oil prices?)\b",
        re.IGNORECASE
    ),
    "OIL_PRICE_DROP": re.compile(
        r"\b(crude|brent|wti|oil prices?)\b.*\b(falls?|drops?|slumps?|plunges?|declines?|slides?|lowers?|tumbles?)\b|"
        r"\b(drop|slump|plunge|decline)\b.*\b(crude|brent|wti|oil prices?)\b",
        re.IGNORECASE
    ),
    "RATE_HIKE": re.compile(
        r"\b(policy rate|interest rates?|monetary policy|state bank|sbp|kibor|discount rate)\b.*\b(hikes?|raises?|tightens?|increases?|hawkish|surges?|up by)\b|"
        r"\b(hikes?|raises?|increases?|tightens?|tightening)\b.*\b(policy rate|interest rates?|kibor|discount rate)\b",
        re.IGNORECASE
    ),
    "RATE_CUT": re.compile(
        r"\b(policy rate|interest rates?|monetary policy|state bank|sbp|kibor|discount rate)\b.*\b(cuts?|lowers?|reduces?|eases?|dovish|slashes?|down by)\b|"
        r"\b(cuts?|easings?|reductions?|slashes?|slash)\b.*\b(policy rate|interest rates?|kibor|discount rate)\b",
        re.IGNORECASE
    ),
    "PKR_DEPRECIATION": re.compile(
        r"\b(rupee|pkr|currency)\b.*\b(depreciates?|falls?|drops?|slumps?|weakens?|plunges?|slides?|record low)\b|"
        r"\b(dollar|usd)\b.*\b(strengthens?|rises?|gains?|jumps?|surges?|hits record high)\b",
        re.IGNORECASE
    ),
    "PKR_APPRECIATION": re.compile(
        r"\b(rupee|pkr|currency)\b.*\b(appreciates?|strengthens?|gains?|recovers?|rallies)\b|"
        r"\b(dollar|usd)\b.*\b(declines?|falls?|weakens?|drops?)\b",
        re.IGNORECASE
    ),
    "INFLATION_SURGE": re.compile(
        r"\b(inflation|cpi|consumer price)\b.*\b(surges?|rises?|jumps?|accelerates?|highs?|elevated|spikes?)\b",
        re.IGNORECASE
    ),
    "IMF_INFLOW": re.compile(
        r"\b(imf|extended fund facility|bailout|reserves|inflow|world bank|adb)\b.*\b(approved|cleared|disburses?|tranche|inflows?|boosts?|pact|deal)\b",
        re.IGNORECASE
    ),
    "CIRCULAR_DEBT_PAYMENT": re.compile(
        r"\b(circular debt|energy debt|dues?|settlement)\b.*\b(settles?|clears?|payment|paid|disburses?|resolves?|slashed)\b",
        re.IGNORECASE
    ),
    "GAS_TARIFF_HIKE": re.compile(
        r"\b(gas tariff|power tariff|electricity tariff|power rate)\b.*\b(hike|increases?|surges?|raised|up by|nepra)\b",
        re.IGNORECASE
    ),
}


class StockNewsImpactEngine:
    """
    Intelligent Stock-Specific News Impact Engine.
    Evaluates asymmetric company transmission, corporate sentiment,
    and anti-leakage time alignment for PSX equities.
    """

    def __init__(self, trading_calendar: Optional[List[str]] = None):
        self.trading_calendar = sorted(trading_calendar) if trading_calendar else []
        self._cal_set = set(self.trading_calendar)

    def extract_mentioned_stocks(self, text: str) -> List[str]:
        """Finds all PSX stock tickers explicitly mentioned in the text."""
        matched = []
        for sym, pattern in ENTITY_PATTERNS.items():
            if sym == "KSE100":
                continue
            if pattern.search(text):
                matched.append(sym)
        return matched

    def detect_macro_themes(self, text: str) -> List[str]:
        """Detects active macroeconomic and commodity themes from text."""
        active = []
        for theme_name, pattern in THEME_PATTERNS.items():
            if pattern.search(text):
                active.append(theme_name)
        return active

    def align_timestamp_to_session(self, published_at_str: str) -> str:
        """
        Anti-leakage timestamp alignment.
        - If published after 16:00 PKT -> aligns to next trading session t+1.
        - If published on weekends/holidays -> aligns to next trading session t+1.
        - If date only (no time) -> aligns to next session t+1 to eliminate lookahead bias.
        """
        raw = str(published_at_str or "").strip()
        if not raw:
            return ""

        date_part = raw[:10]
        has_time = len(raw) >= 16 and (":" in raw[11:16])

        # Parse date
        try:
            pub_date = datetime.strptime(date_part, "%Y-%m-%d").date()
        except ValueError:
            return date_part

        target_date = pub_date

        if has_time:
            time_str = raw[11:16]
            try:
                hour = int(time_str[:2])
                minute = int(time_str[3:5])
                pub_time = time(hour, minute)

                # PSX Trading Session: 09:15 to 16:00
                # Any news after 16:00 cannot affect today's session -> shifts to tomorrow
                # Intraday news after 09:15 also shifts to tomorrow for daily open-to-close predictions
                if pub_time >= time(9, 15):
                    target_date = pub_date + timedelta(days=1)
                else:
                    target_date = pub_date
            except (ValueError, IndexError):
                target_date = pub_date + timedelta(days=1)
        else:
            # Conservative: Daily date-stamped articles are scraped at or after close -> shifts to next session
            target_date = pub_date + timedelta(days=1)

        # Roll forward to the next valid exchange trading session
        target_str = target_date.strftime("%Y-%m-%d")
        if self.trading_calendar:
            # Find first calendar date >= target_str
            for c_date in self.trading_calendar:
                if c_date >= target_str:
                    return c_date
            return target_str

        # Fallback if no calendar provided: skip Saturday and Sunday
        while target_date.weekday() >= 5:  # 5=Sat, 6=Sun
            target_date += timedelta(days=1)
        return target_date.strftime("%Y-%m-%d")

    def evaluate_article_impact(
        self,
        headline: str,
        summary: str = "",
        published_at: str = "",
        base_sentiment_score: float = 0.0,
        base_sentiment_label: str = "Neutral",
        base_confidence: float = 0.5
    ) -> Dict[str, Any]:
        """
        Evaluates full multi-stock asymmetric impact for an article.
        Returns stock-specific impact scores, rationales, and the aligned trading date.
        """
        text = f"{headline} {summary}".strip()
        aligned_session = self.align_timestamp_to_session(published_at)

        direct_stocks = self.extract_mentioned_stocks(text)
        macro_themes = self.detect_macro_themes(text)

        # Normalize base sentiment score in [-1.0, 1.0]
        score = float(base_sentiment_score or 0.0)
        # If score is 0.0 but label is Bullish/Bearish, provide sensible default
        if abs(score) < 1e-4:
            if base_sentiment_label.upper() in ("BULLISH", "POSITIVE"):
                score = 0.65
            elif base_sentiment_label.upper() in ("BEARISH", "NEGATIVE"):
                score = -0.65

        # Invert or adjust for inverse themes:
        # e.g. OIL_PRICE_DROP is negative for oil, but positive for cement
        effective_themes: Dict[str, float] = {}
        for th in macro_themes:
            if th == "OIL_PRICE_DROP":
                effective_themes["OIL_PRICE_SURGE"] = -1.0
            elif th == "RATE_CUT":
                effective_themes["RATE_HIKE"] = -1.0
            elif th == "PKR_APPRECIATION":
                effective_themes["PKR_DEPRECIATION"] = -1.0
            else:
                effective_themes[th] = 1.0

        stock_impacts: Dict[str, Dict[str, Any]] = {}

        # 1. Evaluate Direct Mention Impact
        for sym in direct_stocks:
            # Direct company mentions have high sensitivity (+1.0 direct transmission)
            stock_impacts[sym] = {
                "impact_score": round(score, 4),
                "is_direct_mention": True,
                "confidence": round(base_confidence, 4),
                "transmission_channel": "DIRECT_CORPORATE_MENTION",
                "impact_type": "BULLISH_TAILWIND" if score > 0.05 else ("BEARISH_HEADWIND" if score < -0.05 else "NEUTRAL"),
                "rationale": f"Direct company news event for {sym}. Direct sentiment translated with primary beta=1.0."
            }

        # 2. Evaluate Macroeconomic Spillover & Asymmetry
        for theme_name, theme_direction in effective_themes.items():
            beta_map = SECTOR_TRANSMISSION_MATRIX.get(theme_name, {})
            theme_magnitude = abs(score) if abs(score) > 0.1 else 0.6

            for target_sym, beta in beta_map.items():
                if target_sym == "KSE100":
                    continue
                # Transmitted impact = beta * theme_direction * magnitude
                transmitted_score = round(beta * theme_direction * theme_magnitude, 4)

                if target_sym in stock_impacts:
                    # Blend direct mention with macro theme (70% direct, 30% macro)
                    existing = stock_impacts[target_sym]
                    blended = round(0.70 * existing["impact_score"] + 0.30 * transmitted_score, 4)
                    existing["impact_score"] = blended
                    existing["macro_spillover_theme"] = theme_name
                    existing["macro_beta"] = beta
                    existing["impact_type"] = "BULLISH_TAILWIND" if blended > 0.05 else ("BEARISH_HEADWIND" if blended < -0.05 else "NEUTRAL")
                else:
                    # Pure macro transmission
                    stock_impacts[target_sym] = {
                        "impact_score": transmitted_score,
                        "is_direct_mention": False,
                        "confidence": round(base_confidence * 0.85, 4),
                        "transmission_channel": f"MACRO_SPILLOVER_{theme_name}",
                        "macro_beta": beta,
                        "impact_type": "BULLISH_TAILWIND" if transmitted_score > 0.05 else ("BEARISH_HEADWIND" if transmitted_score < -0.05 else "NEUTRAL"),
                        "rationale": self._build_transmission_rationale(target_sym, theme_name, theme_direction, beta)
                    }

        return {
            "headline": headline,
            "published_at": published_at,
            "aligned_trading_session": aligned_session,
            "base_sentiment_score": score,
            "base_sentiment_label": base_sentiment_label,
            "direct_stocks_mentioned": direct_stocks,
            "macro_themes_detected": macro_themes,
            "impacted_stocks_count": len(stock_impacts),
            "stock_impacts": stock_impacts
        }

    def _build_transmission_rationale(self, symbol: str, theme: str, direction: float, beta: float) -> str:
        """Constructs human-readable economic explanation of asymmetric transmission."""
        if theme == "OIL_PRICE_SURGE":
            if direction > 0:
                if beta > 0:
                    return f"Crude oil benchmark increase expands dollar-indexed wellhead revenues for upstream producer {symbol}."
                else:
                    return f"Crude oil increase escalates input feedstock procurement and logistics expenses for {symbol}."
            else:
                if beta > 0:
                    return f"Crude oil benchmark softening contracts realized wellhead margins for {symbol}."
                else:
                    return f"Lower crude prices reduce procurement costs and working capital strain for {symbol}."

        elif theme == "RATE_HIKE":
            if direction > 0:
                if beta > 0:
                    return f"SBP policy rate hike accelerates floating asset yield repricing, widening Net Interest Margins (NIM) for bank {symbol}."
                else:
                    return f"Monetary tightening sharply increases borrowing debt service charges, eroding profitability for leveraged producer {symbol}."
            else:
                if beta > 0:
                    return f"Monetary easing causes gradual NIM asset yield compression for {symbol}."
                else:
                    return f"Interest rate reduction slashes debt servicing expenses and stimulates capital expenditure for {symbol}."

        elif theme == "PKR_DEPRECIATION":
            if direction > 0:
                if beta > 0:
                    return f"PKR devaluation boosts domestic rupee top-line conversion for dollar-earning exporter {symbol}."
                else:
                    return f"PKR depreciation drives up foreign currency import procurement costs for {symbol}."
            else:
                if beta > 0:
                    return f"Rupee appreciation creates export FX translation headwinds for {symbol}."
                else:
                    return f"Rupee strength softens raw material import import bills for {symbol}."

        elif theme == "CIRCULAR_DEBT_PAYMENT":
            return f"Government circular debt clearance injects immediate liquidity into energy chain operator {symbol}."

        elif theme == "IMF_INFLOW":
            return f"Sovereign reserve expansion and macroeconomic stabilization restore investor risk appetite for {symbol}."

        return f"Macroeconomic development transmits to {symbol} via economic sensitivity beta={beta:.2f}."
