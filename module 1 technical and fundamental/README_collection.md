# Public market-data collection

All new outputs are in `data/collected/public_20261117_142707/`. Existing database files, CSVs and combined_v1/combined_v2 artifacts are not used as write destinations. The collectors do not connect to any database.

## Commands

Run in this Module 1 directory:

```powershell
python -m pytest tests/test_collect_public.py -q
python -m m1.collect_public --as-of 2026-11-17
```

The second command creates a new timestamped run. To recover an interrupted run, use its directory name:

```powershell
python -m m1.collect_public --as-of 2026-11-17 --resume public_20261117_142707
```

Resume verifies stored response checksums and reuses them. It does not refresh already collected endpoints. A new run is needed for a new snapshot. Fundamental collection stops when that endpoint category returns an authentication denial. No credentials or authentication workarounds are used.

Download selected original PSX filings linked from a completed collection:

```powershell
python -m m1.collect_filings public_20261117_142707
```

This command creates `original_documents`. On resume it verifies and reuses already logged files and skips logged failures; it does not overwrite completed PDFs. It selects up to two recent financial results, report transmissions and corporate-action documents per ticker. Requests are rate-limited, constrained to the original PSX download host, and individual PDFs are limited to 20 MB. Failures and size limits are logged; document links remain available for follow-up.

## Outputs and interpretation

- `requests.jsonl`: request status, retrieval timestamp, source URL, raw response path and SHA-256 checksum.
- `raw/`: compressed original JSON/HTML responses and parsed public Investify page properties.
- `stock_price_history.csv.gz`: provider-returned historical prices. This endpoint supplies close, volume and market capitalization; missing open/high/low are never fabricated.
- `kse100_history.csv.gz`: market-index history used for a conservative calendar intersection.
- `price_quality_ledger.csv.gz`: invalid closes, weekends, duplicates, non-calendar dates and current/future-day flags.
- `completed_close_volume_candidates.csv.gz`: date/close-screened candidates, not fully verified OHLCV or adjusted returns.
- `investify_quote_snapshots.csv.gz`: latest OHLCV snapshots, not a historical panel.
- `investify_financial_snapshots.csv.gz`: public ratio values with their provider period labels. Fiscal labels such as 2027 1Q are retained, not incorrectly converted to future calendar publication dates.
- `sarmaaya_announcements.csv.gz` and `investify_announcements.csv.gz`: separate provider records; counts are not cross-provider deduplicated.
- `corporate_action_candidates.csv.gz`: provider-extracted dates and terms. These may include AI extraction; effective/payment dates are not treated as verified ex-dates.
- `filing_document_links.csv.gz`: announcement timestamps and original PDF/image links, including provider-derived financial summaries.
- `original_document_index.csv`: selected original PDFs with checksums and download outcomes. Original documents still require parsing and review.
- `summary.json`, `verification.json`, `REPORT.md`: coverage, quality limitations and verification results.

## Training admission

No freshly scraped record is automatically merged into training or the database. Before doing so, verify actual exchange sessions and historical OHLC, corporate-action ex-dates and factors, financial units and period types, and the availability/revision vintage of each financial value. Match announcement identifiers and source documents before combining providers. In the current public run, detailed Sarmaaya financial statement endpoints and Investify historical charts require authorized access; public financial snapshots cannot replace point-in-time statement history.

Verify the completed collection and downloaded PDFs:

```powershell
python -m m1.verify_public public_20261117_142707
```
