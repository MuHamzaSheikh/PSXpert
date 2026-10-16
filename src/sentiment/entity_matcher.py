"""
PSXpert - Financial Entity & Ticker Matcher
Extracts and resolves PSX company tickers and sectors from Pakistani financial news text.
Supports Target-Specific Sentence Extraction (for Aspect-Based Sentiment Analysis).
"""

import re
from typing import Dict, List, Set, Tuple

# Comprehensive mapping of Pakistani corporate entities & aliases to canonical PSX symbols
COMPANY_ALIASES = {
    # Oil & Gas Exploration & Marketing
    "OGDC": ["OGDCL", "OIL AND GAS DEVELOPMENT COMPANY", "OIL & GAS DEVELOPMENT COMPANY", "OGDC"],
    "PPL": ["PAKISTAN PETROLEUM LIMITED", "PAKISTAN PETROLEUM", "PPL"],
    "MARI": ["MARI PETROLEUM", "MARI PETROLEUM COMPANY", "MARI GAS", "MARI"],
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

    # Commercial Banks
    "MEBL": ["MEEZAN BANK", "MEEZAN BANK LIMITED", "MEEZAN", "MEBL"],
    "HBL": ["HABIB BANK", "HABIB BANK LIMITED", "HBL"],
    "UBL": ["UNITED BANK", "UNITED BANK LIMITED", "UBL"],
    "MCB": ["MCB BANK", "MCB BANK LIMITED", "MUSLIM COMMERCIAL BANK", "MCB"],
    "NBP": ["NATIONAL BANK OF PAKISTAN", "NATIONAL BANK", "NBP"],
    "BAFL": ["BANK ALFALAH", "BANK ALFALAH LIMITED", "ALFALAH", "BAFL"],
    "BAHL": ["BANK AL HABIB", "BANK AL HABIB LIMITED", "AL HABIB", "BAHL"],
    "HMB": ["HABIB METROPOLITAN BANK", "HABIB METRO", "HMB"],
    "BOP": ["BANK OF PUNJAB", "THE BANK OF PUNJAB", "BOP"],
    "FABL": ["FAYSAL BANK", "FAYSAL BANK LIMITED", "FABL"],
    "AKBL": ["ASKARI BANK", "ASKARI BANK LIMITED", "AKBL"],

    # Cement
    "LUCK": ["LUCKY CEMENT", "LUCKY CEMENT LIMITED", "LUCKY", "LUCK"],
    "DGKC": ["D.G. KHAN CEMENT", "DG KHAN CEMENT", "DGKC"],
    "MLCF": ["MAPLE LEAF CEMENT", "MAPLE LEAF", "MLCF"],
    "CHCC": ["CHERAT CEMENT", "CHERAT CEMENT COMPANY", "CHCC"],
    "FCCL": ["FAUJI CEMENT", "FAUJI CEMENT COMPANY", "ASKARI CEMENT", "FCCL"],
    "KOHC": ["KOHAT CEMENT", "KOHAT CEMENT COMPANY", "KOHC"],
    "PIOC": ["PIONEER CEMENT", "PIONEER CEMENT LIMITED", "PIOC"],

    # Fertilizer
    "ENGRO": ["ENGRO CORPORATION", "ENGRO CORP", "ENGRO FERTILIZERS", "EFERT", "ENGRO"],
    "FFC": ["FAUJI FERTILIZER COMPANY", "FAUJI FERTILIZER", "FFC"],
    "FFBL": ["FAUJI FERTILIZER BIN QASIM", "FFBL"],
    "FATIMA": ["FATIMA FERTILIZER", "FATIMA FERTILIZER COMPANY", "FATIMA"],

    # Technology & Telecommunications
    "SYS": ["SYSTEMS LIMITED", "SYSTEMS LTD", "SYS"],
    "TRG": ["TRG PAKISTAN", "TRG PAKISTAN LIMITED", "THE RESOURCE GROUP", "TRG"],
    "NETSOL": ["NETSOL TECHNOLOGIES", "NETSOL"],
    "AVN": ["AVANCEON", "AVANCEON LIMITED", "AVN"],
    "PTC": ["PAKISTAN TELECOMMUNICATION COMPANY", "PTCL", "PTC"],
    "WTL": ["WORLDCALL TELECOM", "WORLDCALL", "WTL"],

    # Power & Energy
    "HUBC": ["HUB POWER COMPANY", "HUB POWER", "HUBCO", "HUBC"],
    "KEL": ["K-ELECTRIC", "K ELECTRIC", "KARACHI ELECTRIC", "KESC", "KEL"],
    "KAPCO": ["KOT ADDU POWER", "KOT ADDU POWER COMPANY", "KAPCO"],

    # Automobile & Assemblers
    "INDU": ["INDUS MOTOR COMPANY", "INDUS MOTOR", "TOYOTA PAKISTAN", "INDU"],
    "PSMC": ["PAK SUZUKI MOTOR", "PAK SUZUKI", "PSMC"],
    "HONDA": ["HONDA ATLAS CARS", "HONDA ATLAS", "HACPL"],
    "MTL": ["MILLAT TRACTORS", "MILLAT TRACTORS LIMITED", "MTL"],

    # Pharmaceuticals & Chemicals
    "SEARL": ["THE SEARLE COMPANY", "SEARLE", "SEARL"],
    "ABOT": ["ABBOTT LABORATORIES PAKISTAN", "ABBOTT PAKISTAN", "ABOT"],
    "GLAXO": ["GLAXOSMITHKLINE PAKISTAN", "GSK PAKISTAN", "GLAXO"],
    "EPCL": ["ENGRO POLYMER & CHEMICALS", "ENGRO POLYMER", "EPCL"],
    "LOTCHEM": ["LOTTE CHEMICAL PAKISTAN", "LOTTE CHEMICAL", "LOTCHEM"],

    # Food & Personal Care
    "NESTLE": ["NESTLE PAKISTAN", "NESTLE PAKISTAN LIMITED", "NESTLE"],
    "UNITY": ["UNITY FOODS", "UNITY FOODS LIMITED", "UNITY"],

    # Macro & Indices
    "KSE100": ["KSE-100", "KSE 100", "KSE100 INDEX", "KSE100", "KARACHI SHARE INDEX"],
    "PSX": ["PAKISTAN STOCK EXCHANGE", "KARACHI STOCK EXCHANGE", "PSX", "BOURSE", "EQUITY MARKET"]
}

# Sector identification keywords
SECTOR_KEYWORDS = {
    "COMMERCIAL BANKS": ["BANK", "BANKS", "BANKING", "INTEREST RATE", "POLICY RATE", "SBP", "NPL", "ADVANCES", "DEPOSITS"],
    "OIL & GAS EXPLORATION": ["OIL", "GAS", "CRUDE", "OGDC", "PPL", "MARI", "WELL", "EXPLORATION", "DISCOVERY", "BARREL"],
    "OIL & GAS MARKETING": ["PSO", "SHEL", "PETROL", "DIESEL", "POL PRODUCTS", "OMC", "FUEL MARGIN"],
    "CEMENT": ["CEMENT", "CLINKER", "DISPATCHES", "CONSTRUCTION", "COAL PRICE"],
    "FERTILIZER": ["FERTILIZER", "UREA", "DAP", "GAS SUBSIDY", "FEEDSTOCK"],
    "POWER GENERATION": ["POWER", "ELECTRICITY", "ENERGY", "CIRCULAR DEBT", "TARIFF", "NEPRA", "IPPS"],
    "TECHNOLOGY & COMMUNICATION": ["TECH", "IT EXPORTS", "SOFTWARE", "FREELANCING", "DIGITAL"],
    "REFINERY": ["REFINERY", "BRENT", "FURNACE OIL", "PETROLEUM REFINING"],
    "AUTOMOBILE": ["AUTOMOBILE", "AUTO", "CAR SALES", "TRACTOR", "PAMA", "CKD"],
    "TEXTILE": ["TEXTILE", "COTTON", "YARN", "GARMENTS", "EXPORT SUBSIDY"],
    "PHARMACEUTICAL": ["PHARMA", "PHARMACEUTICAL", "MEDICINE", "DRAP", "DRUG PRICE"]
}


class EntityMatcher:
    def __init__(self):
        # Precompile regexes for exact word boundary matching
        self.compiled_aliases = {}
        for symbol, aliases in COMPANY_ALIASES.items():
            patterns = []
            for alias in aliases:
                escaped = re.escape(alias)
                patterns.append(rf"\b{escaped}\b")
            self.compiled_aliases[symbol] = re.compile("|".join(patterns), re.IGNORECASE)

    def extract_companies(self, text: str) -> List[str]:
        """Identifies all mentioned company/index symbols in text."""
        matched = []
        for symbol, pattern in self.compiled_aliases.items():
            if pattern.search(text):
                matched.append(symbol)
        return matched

    def extract_sectors(self, text: str) -> List[str]:
        """Identifies relevant financial sectors mentioned in text."""
        matched_sectors = []
        upper_text = text.upper()
        for sector, keywords in SECTOR_KEYWORDS.items():
            score = sum(1 for kw in keywords if re.search(rf"\b{re.escape(kw)}\b", upper_text))
            if score >= 1:
                matched_sectors.append(sector)
        return matched_sectors

    def extract_entity_contexts(self, text: str, symbols: List[str]) -> Dict[str, str]:
        """
        Extracts specific context sentences surrounding each mentioned ticker.
        Essential for Target-Specific / Aspect-Based Sentiment Analysis (ABSA)
        when multiple companies are mentioned in the same article.
        """
        # Split text into sentences
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        entity_contexts = {}

        for sym in symbols:
            if sym not in self.compiled_aliases:
                continue
            pattern = self.compiled_aliases[sym]
            relevant_sentences = []
            for sent in sentences:
                if pattern.search(sent):
                    relevant_sentences.append(sent)

            if relevant_sentences:
                entity_contexts[sym] = " ".join(relevant_sentences)
            else:
                # If symbol matched but sentence split was tight, use first 250 chars of article
                entity_contexts[sym] = text[:250]

        return entity_contexts
