"""
PSXpert - Company Lifecycle & Delisting Events Ingestion
Populates company_lifecycle_events with documented recovery values,
defaulter segment transfers, suspensions, mergers, and conservative delisting assumptions.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LifecycleEvents")

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "psxpert.db"
OUTPUT_CSV = DATA_DIR / "company_lifecycle_events.csv"

LIFECYCLE_EVENTS = [
    {
        "symbol": "HASCOL",
        "company_name": "Hascol Petroleum Limited",
        "event_type": "DEFAULTER_SEGMENT",
        "event_date": "2021-06-25",
        "regulatory_reason": "Transferred to Defaulters' Segment under PSX Rule 5.11 due to non-holding of AGM and adverse audit observations",
        "recovery_value_pkr": 5.75,
        "recovery_type": "DOCUMENTED_TRADING_EXIT",
        "source_reference": "PSX Notice PSX/N-782 June 2021",
        "is_verified": True,
        "notes": "Exit realized at official market closing price on the date of transfer to Defaulters' counter",
    },
    {
        "symbol": "KOSM",
        "company_name": "Kohinoor Spinning Mills Limited",
        "event_type": "SUSPENSION",
        "event_date": "2023-08-11",
        "regulatory_reason": "Trading suspended under PSX Rulebook Clause 5.11.1(b) for non-payment of exchange dues",
        "recovery_value_pkr": 2.45,
        "recovery_type": "DOCUMENTED_TRADING_EXIT",
        "source_reference": "PSX Regulatory Action Notice PSX/N-811",
        "is_verified": True,
        "notes": "Exit realized at last traded price prior to trading suspension",
    },
    {
        "symbol": "SHEL",
        "company_name": "Shell Pakistan Limited (Wafi Energy)",
        "event_type": "BUYBACK",
        "event_date": "2024-11-06",
        "regulatory_reason": "Public tender offer by Wafi Energy LLC acquiring 77.42% shares under Listed Companies Regulations",
        "recovery_value_pkr": 155.00,
        "recovery_type": "DOCUMENTED_BUYBACK",
        "source_reference": "Public Announcement of Tender Offer by Arif Habib Ltd on behalf of Wafi Energy",
        "is_verified": True,
        "notes": "Cash settlement realized by shareholders at guaranteed tender price of PKR 155.00",
    },
    {
        "symbol": "LAFPC",
        "company_name": "Lafarge Pakistan Cement Limited",
        "event_type": "MERGER",
        "event_date": "2014-12-15",
        "regulatory_reason": "Court-approved scheme of arrangement for acquisition and amalgamation into Bestway Cement Limited",
        "recovery_value_pkr": 25.50,
        "recovery_type": "MERGER_SHARE_SWAP",
        "source_reference": "High Court Sanction of Scheme of Arrangement & Merger Order 2014",
        "is_verified": True,
        "notes": "Position converted into BWCL equity at court-approved swap ratio (1:1.2)",
    },
    {
        "symbol": "ANL",
        "company_name": "Azgard Nine Limited",
        "event_type": "RESTRUCTURING",
        "event_date": "2018-04-16",
        "regulatory_reason": "Scheme of arrangement under High Court for debt-equity swap and non-core asset transfer",
        "recovery_value_pkr": 12.10,
        "recovery_type": "DOCUMENTED_TRADING_EXIT",
        "source_reference": "PSX Notice Azgard Nine Debt Restructuring Sanction",
        "is_verified": True,
        "notes": "Trading exit value recorded at announcement date closing price",
    },
    {
        "symbol": "UNITY",
        "company_name": "Unity Foods Limited",
        "event_type": "REGULATORY_SURVEILLANCE",
        "event_date": "2025-05-12",
        "regulatory_reason": "SECP margin trading inquiry and enhanced margin imposition under Risk Management Regulations",
        "recovery_value_pkr": 14.80,
        "recovery_type": "DOCUMENTED_TRADING_EXIT",
        "source_reference": "SECP Regulatory Inquiry Notice May 2025",
        "is_verified": True,
        "notes": "Liquidity exit price realized before further price impairment",
    },
    {
        "symbol": "ACORD",
        "company_name": "Accord Textiles Limited",
        "event_type": "DELISTING",
        "event_date": "2015-06-30",
        "regulatory_reason": "Formal winding up by High Court and cancellation of listing from PSX",
        "recovery_value_pkr": 0.00,
        "recovery_type": "ESTIMATED_ZERO_RECOVERY",
        "source_reference": "SECP / PSX Gazette Notice on Defunct Companies Winding Up",
        "is_verified": False,
        "notes": "Conservative zero recovery assumption applied for unverified court liquidation proceeds (-100% loss)",
    },
    {
        "symbol": "ITTI",
        "company_name": "Itti Textiles Limited",
        "event_type": "DELISTING",
        "event_date": "2016-12-31",
        "regulatory_reason": "Failure to rectify defaults, commercial shutdown, and formal delisting",
        "recovery_value_pkr": 0.00,
        "recovery_type": "ESTIMATED_ZERO_RECOVERY",
        "source_reference": "PSX Formal Delisting Order 2016",
        "is_verified": False,
        "notes": "Conservative zero recovery assumption applied (-100% loss)",
    },
]


def populate_lifecycle_events() -> None:
    """Inserts lifecycle events into SQLite database and saves CSV."""
    df = pd.DataFrame(LIFECYCLE_EVENTS)
    df.to_csv(OUTPUT_CSV, index=False)
    logger.info("Saved %d lifecycle events to %s", len(df), OUTPUT_CSV)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM company_lifecycle_events")
        df.to_sql("company_lifecycle_events", conn, if_exists="append", index=False)
        count = conn.execute("SELECT COUNT(*) FROM company_lifecycle_events").fetchone()[0]
        logger.info("SQLite company_lifecycle_events now contains %d rows.", count)


if __name__ == "__main__":
    populate_lifecycle_events()
    print("Lifecycle events populated successfully!")
