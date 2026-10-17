"""
PSXpert - Financial & Geopolitical News Market Impact Analyzer
Analyzes financial and geopolitical news to determine:
1. Category (Geopolitical, Macro/IMF, Energy & Oil, Banking & Rates, Tech & AI, Corporate)
2. Targeted Industries / Sectors
3. Impacted PSX Stocks / Constituent Tickers
4. Economic Transmission Rationale (Why and how this news affects these sectors and stocks)
"""

import re
from typing import Dict, List, Any, Optional

# Industry to constituent PSX equities mapping
SECTOR_TO_STOCKS = {
    "Oil & Gas Exploration": ["OGDC", "PPL", "MARI", "POL"],
    "Refinery": ["PRL", "ATRL", "CNERGY", "NRL"],
    "Oil & Gas Marketing": ["PSO", "SHEL", "APL", "SNGP", "SSGC"],
    "Commercial Banks": ["MEBL", "HBL", "MCB", "UBL", "NBP", "BAFL", "BAHL"],
    "Power Generation": ["HUBC", "KEL", "KAPCO"],
    "Fertilizer": ["ENGROH", "FFC", "FFBL", "FATIMA"],
    "Cement": ["LUCK", "DGKC", "MLCF", "FCCL", "CHCC"],
    "Technology & AI": ["SYS", "TRG", "NETSOL", "AVN"],
    "Automobile": ["INDU", "PSMC", "HONDA", "MTL"],
    "Pharmaceutical": ["ABOT", "SEARL", "GLAXO"],
    "Textile": ["NML", "GATM", "ILP"],
    "General Market / Sovereign": ["KSE100", "OGDC", "HBL", "MEBL", "LUCK"]
}

# Domain keyword patterns for classification
GEOPOLITICAL_PATTERNS = [
    r"\b(war|attack|military|conflict|middle east|gulf|iran|israel|red sea|strait of hormuz|houthis?|sanctions|geopolitical|russia|ukraine|china|taiwan|missile|drone|airstrikes?|ceasefire|diplomacy|fatf|sovereignty)\b"
]

MACRO_PATTERNS = [
    r"\b(imf|extended fund facility|world bank|inflation|cpi|interest rates?|policy rate|sbp|state bank|monetary policy|panda bonds?|eurobonds?|borrowing|privatisation|gdp|growth|trade deficit|current account|reserves|fiscal|taxation|fbr|rupee|pkr|devaluation)\b"
]

ENERGY_PATTERNS = [
    r"\b(crude|brent|wti|oil prices?|petrol|diesel|gas tariff|lng|refinery|circular debt|nepra|electricity|power tariff|fuel margin|omcs?|wellhead|petroleum)\b"
]

BANKING_PATTERNS = [
    r"\b(banks?|banking|deposits?|advances|adr tax|npl|non-performing loans|t-bills?|pibs?|treasury yields?|spreads|margin)\b"
]

TECH_PATTERNS = [
    r"\b(ai|artificial intelligence|tech|technology|software|it exports?|chips?|semiconductor|nasdaq|nikkei|digital|freelanc)\b"
]

CEMENT_PATTERNS = [
    r"\b(cement|clinker|dispatches|construction|coal prices?|housing|infrastructure)\b"
]


class NewsImpactAnalyzer:
    """
    Analyzes news headlines and summaries to identify geopolitical/macro context,
    targeted industries, affected stocks, and transmission rationales.
    """

    def analyze(self, headline: str, summary: str = "", sentiment_label: str = "NEUTRAL", mentioned_symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        text = f"{headline} {summary}".strip()

        if mentioned_symbols is None:
            mentioned_symbols = []

        # 1. Determine Category
        category = "CORPORATE"
        cat_badge = "CORPORATE"

        is_geo = any(re.search(p, text, re.I) for p in GEOPOLITICAL_PATTERNS)
        is_macro = any(re.search(p, text, re.I) for p in MACRO_PATTERNS)
        is_energy = any(re.search(p, text, re.I) for p in ENERGY_PATTERNS)
        is_tech = any(re.search(p, text, re.I) for p in TECH_PATTERNS)
        is_bank = any(re.search(p, text, re.I) for p in BANKING_PATTERNS)
        is_cement = any(re.search(p, text, re.I) for p in CEMENT_PATTERNS)

        if is_geo:
            category = "GEOPOLITICAL"
            cat_badge = "GEOPOLITICAL"
        elif is_macro:
            category = "MACRO_IMF"
            cat_badge = "MACRO / SBP / IMF"
        elif is_energy:
            category = "ENERGY_OIL"
            cat_badge = "ENERGY & OIL"
        elif is_tech:
            category = "TECH_AI"
            cat_badge = "TECH & AI"
        elif is_bank:
            category = "BANKING"
            cat_badge = "BANKING & RATES"
        elif is_cement:
            category = "CEMENT"
            cat_badge = "CEMENT & INFRA"

        # 2. Determine Targeted Industries
        targeted_industries = []
        if is_geo or is_energy:
            if re.search(r"\b(oil|crude|brent|fuel|gas|petroleum|gulf|riyadh|middle east|energy|refinery)\b", text, re.I):
                targeted_industries.extend(["Oil & Gas Exploration", "Refinery", "Oil & Gas Marketing"])
            if re.search(r"\b(power|circular debt|nepra|electricity|tariff)\b", text, re.I):
                targeted_industries.append("Power Generation")

        if is_macro:
            if re.search(r"\b(imf|privatisation|sovereign|growth|panda bonds?|reserves)\b", text, re.I):
                targeted_industries.extend(["Commercial Banks", "General Market / Sovereign"])
            if re.search(r"\b(rate|policy rate|sbp|monetary|interest|inflation)\b", text, re.I):
                targeted_industries.extend(["Commercial Banks", "Cement", "Automobile"])

        if is_tech:
            targeted_industries.append("Technology & AI")

        if is_bank and "Commercial Banks" not in targeted_industries:
            targeted_industries.append("Commercial Banks")

        if is_cement and "Cement" not in targeted_industries:
            targeted_industries.append("Cement")

        if not targeted_industries:
            # Fallback based on mentioned symbols
            for sym in mentioned_symbols:
                for sec, stocks in SECTOR_TO_STOCKS.items():
                    if sym in stocks and sec not in targeted_industries:
                        targeted_industries.append(sec)

        if not targeted_industries:
            targeted_industries = ["General Market / Sovereign"]

        # Deduplicate while preserving order
        dedup_industries = []
        for ind in targeted_industries:
            if ind not in dedup_industries:
                dedup_industries.append(ind)
        targeted_industries = dedup_industries

        # 3. Determine Affected Stocks
        impacted_stocks = []
        # First include specifically mentioned symbols
        for sym in mentioned_symbols:
            if sym not in ["PSX"] and sym not in impacted_stocks:
                impacted_stocks.append(sym)

        # Then include primary sector liquid leaders
        for ind in targeted_industries:
            for s in SECTOR_TO_STOCKS.get(ind, []):
                if s not in impacted_stocks and len(impacted_stocks) < 6:
                    impacted_stocks.append(s)

        if not impacted_stocks:
            impacted_stocks = ["KSE100", "OGDC", "MEBL", "LUCK"]

        # 4. Generate Transmission Impact Rationale
        impact_analysis = self._generate_transmission_rationale(
            category=category,
            headline=headline,
            sentiment=sentiment_label,
            industries=targeted_industries,
            stocks=impacted_stocks[:4]
        )

        return {
            "category": category,
            "category_badge": cat_badge,
            "targeted_industries": targeted_industries,
            "impacted_stocks": impacted_stocks[:6],
            "impact_analysis": impact_analysis
        }

    def _generate_transmission_rationale(
        self,
        category: str,
        headline: str,
        sentiment: str,
        industries: List[str],
        stocks: List[str]
    ) -> str:
        stocks_str = ", ".join(stocks)
        ind_str = ", ".join(industries)

        if category == "GEOPOLITICAL":
            if "oil" in headline.lower() or "crude" in headline.lower() or "gulf" in headline.lower() or "middle east" in headline.lower() or "riyadh" in headline.lower():
                return f"Geopolitical tension in energy supply corridors elevates global crude benchmarks (Brent). Upstream E&P operators ({stocks_str}) benefit from dollar-indexed wellhead gas/oil pricing, while import refiners face feedstock working capital pressures."
            return f"Heightened international geopolitical friction elevates emerging market risk premiums, triggering selective defensive rotation across benchmark leaders ({stocks_str})."

        elif category == "MACRO_IMF":
            if "privatisation" in headline.lower():
                return f"Privatisation proceeds inject sovereign liquidity and reduce state-owned enterprise fiscal drain, re-rating strategic energy and banking equities ({stocks_str})."
            elif "rate" in headline.lower() or "sbp" in headline.lower() or "inflation" in headline.lower():
                if sentiment == "POSITIVE":
                    return f"State Bank monetary easing lowers leverage borrowing costs for capital-intensive cyclicals ({stocks_str}), expanding equity valuation multiples."
                else:
                    return f"Stubborn inflation or delayed rate cuts increase borrowing expenses for leveraged cyclicals, while sustaining net interest margins for banking institutions ({stocks_str})."
            elif "imf" in headline.lower() or "bonds" in headline.lower() or "growth" in headline.lower():
                return f"Multilateral financing anchors sovereign reserves and PKR parity, unlocking liquidity flow to settle long-standing energy circular debt ({stocks_str})."
            return f"Macroeconomic structural indicators directly shift the equity risk premium applied to heavyweights ({stocks_str})."

        elif category == "ENERGY_OIL":
            return f"Energy price shifts and regulatory tariff decisions directly impact cash flows and feedstock costs for {ind_str}. Transmission flows directly to earnings of {stocks_str}."

        elif category == "TECH_AI":
            if sentiment == "NEGATIVE":
                return f"Global technology risk-off sentiment and semiconductor selloffs create sentiment spillover on domestic IT exporters ({stocks_str}), inducing short-term multiple compression."
            return f"Expanding enterprise digital transformation and AI adoption generate sustained revenue tailwinds for export-oriented IT service providers ({stocks_str})."

        elif category == "CEMENT":
            return f"Domestic construction dispatches, government PSDP allocations, and imported coal prices drive operational EBITDA margins for cement manufacturers ({stocks_str})."

        elif category == "BANKING":
            return f"Sovereign bond yield dynamics, deposit cost re-pricing, and advances growth dictate net interest income margins across banking heavyweights ({stocks_str})."

        return f"Company-specific operational announcements and corporate disclosures directly drive forward EPS expectations for {stocks_str}."
