"""
PSXpert - Automated Data Cleaning & Normalization Pipeline
Cleans and normalizes raw PSX datasets into verified, production-ready tables in data/cleaned/.
Leaves raw original files in data/ completely untouched as immutable backups.
"""

import csv
import json
import math
import os
import re
from datetime import datetime, timedelta

DATA_DIR = "data"
OUTPUT_DIR = os.path.join(DATA_DIR, "cleaned")

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def parse_float(val, default=None):
    if val is None:
        return default
    s = str(val).strip().replace(',', '')
    if not s or s.lower() in ('null', 'none', 'nan', 'n/a', '-'):
        return default
    try:
        return float(s)
    except ValueError:
        return default

def parse_int(val, default=0):
    f = parse_float(val, None)
    if f is None or math.isnan(f):
        return default
    return int(round(f))

def clean_calendar(calendar_path):
    """Loads and validates official exchange trading calendar."""
    print("-> Cleaning Trading Calendar...")
    valid_dates = set()
    cleaned_rows = []
    
    with open(calendar_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            d_str = row['date'].strip()
            close_val = parse_float(row.get('close'))
            change_val = parse_float(row.get('change'), 0.0)
            change_pct = parse_float(row.get('change_pct'), 0.0)
            
            if d_str and close_val is not None and close_val > 0:
                valid_dates.add(d_str)
                cleaned_rows.append({
                    'date': d_str,
                    'symbol': 'KSE100',
                    'close': close_val,
                    'change': change_val,
                    'change_pct': change_pct
                })
                
    cleaned_rows.sort(key=lambda x: x['date'])
    out_path = os.path.join(OUTPUT_DIR, "kse100_calendar_clean.csv")
    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['date', 'symbol', 'close', 'change', 'change_pct'])
        writer.writeheader()
        writer.writerows(cleaned_rows)
        
    print(f"   Calendar: {len(cleaned_rows)} valid exchange sessions saved to {out_path}")
    return valid_dates

def clean_companies(companies_path, constituents_path):
    """Standardizes company directory and sector classifications."""
    print("-> Cleaning Companies Directory...")
    companies = {}
    
    # 1. Read directory
    if os.path.exists(companies_path):
        with open(companies_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sym = row['symbol'].strip().upper()
                companies[sym] = {
                    'symbol': sym,
                    'company_name': row.get('name', '').strip(),
                    'isin': row.get('isin', '').strip(),
                    'sector': row.get('sectorName', '').strip().upper(),
                    'sector_category': row.get('sectorCategory', '').strip(),
                    'is_shariah': 1 if str(row.get('isShariah')).lower() in ('true', '1') else 0,
                    'is_kse100': 1
                }
                
    # 2. Enrich from constituents
    if os.path.exists(constituents_path):
        with open(constituents_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sym = row['symbol'].strip().upper()
                if sym in companies:
                    if str(row.get('isShariah')).lower() in ('true', '1'):
                        companies[sym]['is_shariah'] = 1
                else:
                    companies[sym] = {
                        'symbol': sym,
                        'company_name': sym,
                        'isin': '',
                        'sector': 'UNCLASSIFIED',
                        'sector_category': '',
                        'is_shariah': 1 if str(row.get('isShariah')).lower() in ('true', '1') else 0,
                        'is_kse100': 1
                    }
                    
    sorted_comps = sorted(companies.values(), key=lambda x: x['symbol'])
    out_path = os.path.join(OUTPUT_DIR, "kse100_companies_clean.csv")
    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['symbol', 'company_name', 'isin', 'sector', 'sector_category', 'is_shariah', 'is_kse100'])
        writer.writeheader()
        writer.writerows(sorted_comps)
        
    print(f"   Companies: {len(sorted_comps)} companies cleaned.")
    return {c['symbol']: c for c in sorted_comps}

def clean_payouts(payouts_path):
    """Filters out corrupt placeholder headers and normalizes corporate payouts."""
    print("-> Cleaning Corporate Payouts...")
    valid_payouts = []
    bad_rows_count = 0
    payout_events_by_symbol = {} # symbol -> list of events
    
    with open(payouts_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ptype = row.get('payout_type', '').strip().lower()
            sym = row.get('symbol', '').strip().upper()
            adate = row.get('announcement_date', '').strip()
            
            # Filter corrupt placeholder rows where payout_type == 'type'
            if not ptype or ptype in ('type', 'null', 'none') or not sym:
                bad_rows_count += 1
                continue
                
            div_val = parse_float(row.get('dividend_per_share_pkr'), 0.0)
            pct_val = parse_float(row.get('payout_percentage'), 0.0)
            face_val = parse_float(row.get('face_value_pkr'), 10.0)
            
            event = {
                'symbol': sym,
                'company_name': row.get('company_name', '').strip(),
                'sector': row.get('sector', '').strip().upper(),
                'announcement_date': adate,
                'fiscal_year': row.get('fiscal_year', '').strip(),
                'payout_type': ptype,
                'dividend_per_share_pkr': div_val,
                'payout_percentage': pct_val,
                'face_value_pkr': face_val
            }
            valid_payouts.append(event)
            payout_events_by_symbol.setdefault(sym, []).append(event)
            
    valid_payouts.sort(key=lambda x: (x['symbol'], x['announcement_date']))
    out_path = os.path.join(OUTPUT_DIR, "kse100_corporate_payouts_clean.csv")
    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ['symbol', 'company_name', 'sector', 'announcement_date', 'fiscal_year', 'payout_type', 'dividend_per_share_pkr', 'payout_percentage', 'face_value_pkr']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(valid_payouts)
        
    print(f"   Payouts: {len(valid_payouts)} genuine payout records kept. Dropped {bad_rows_count} corrupt placeholder rows.")
    return payout_events_by_symbol, len(valid_payouts), bad_rows_count

def build_announcement_filing_dates(announcements_path):
    """Maps symbols and fiscal periods to exact verified announcement posting dates."""
    print("-> Indexing Corporate Announcements for Point-in-Time Dates...")
    filing_dates = {} # (symbol, year, period_type) -> posting_date
    
    if not os.path.exists(announcements_path):
        return filing_dates
        
    with open(announcements_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sym = row.get('symbol', '').strip().upper()
            pdate = row.get('posting_date', '').strip()
            cat = row.get('category', '').strip().lower()
            title = row.get('announcement_title', '').strip().lower()
            
            if not sym or not pdate:
                continue
                
            # Search for fiscal year 2000-2026
            year_match = re.search(r'20\d\d', title)
            if not year_match:
                continue
            yr = int(year_match.group(0))
            
            # Determine period type (annual vs quarterly)
            if 'annual' in title or 'financial results for the year' in title or 'annual report' in title:
                key = (sym, yr, 'ANNUAL')
                if key not in filing_dates or pdate < filing_dates[key]:
                    filing_dates[key] = pdate
            elif 'quarter' in title or '1st quarter' in title or 'half year' in title or '3rd quarter' in title:
                # Store by quarter if detected
                q = 'Q1' if 'first' in title or '1st' in title else ('Q2' if 'second' in title or '2nd' in title or 'half' in title else ('Q3' if 'third' in title or '3rd' in title else 'Q'))
                key = (sym, yr, q)
                if key not in filing_dates or pdate < filing_dates[key]:
                    filing_dates[key] = pdate
                    
    print(f"   Announcements: Indexed {len(filing_dates)} distinct PIT earnings publication dates.")
    return filing_dates

def clean_fundamentals(annual_path, quarterly_path, filing_dates):
    """Cleans fundamental balance sheet & income statements, purges sentinels, enforces PIT dates."""
    print("-> Cleaning Fundamental Disclosures...")
    sentinel_annual_dropped = 0
    clean_annual = []
    
    with open(annual_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            # Check for dummy sentinel values
            has_sentinel = any(val in str(v) for v in row.values() for val in ('12121', '435451', '168643'))
            pend = row.get('period_end_date', '').strip()
            if has_sentinel or pend > '2026-10-13':
                sentinel_annual_dropped += 1
                continue
                
            sym = row.get('symbol', '').strip().upper()
            fyear = parse_int(row.get('fiscal_year'), 0)
            
            # Determine true publication date
            pub_date = filing_dates.get((sym, fyear, 'ANNUAL'))
            if not pub_date and pend:
                # Default conservative statutory lag: 90 days after period end
                try:
                    dt = datetime.strptime(pend, '%Y-%m-%d')
                    pub_date = (dt + timedelta(days=90)).strftime('%Y-%m-%d')
                except:
                    pub_date = pend
                    
            row['publication_date'] = pub_date
            clean_annual.append(row)
            
    # Save clean annual
    annual_fields = ['symbol', 'company_name', 'sector', 'periodicity', 'fiscal_year', 'period_end_date', 'publication_date'] + [col for col in fieldnames if col not in ('symbol', 'company_name', 'sector', 'periodicity', 'fiscal_year', 'period_end_date')]
    out_ann_path = os.path.join(OUTPUT_DIR, "kse100_fundamentals_annual_clean.csv")
    with open(out_ann_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=annual_fields)
        writer.writeheader()
        writer.writerows(clean_annual)
        
    print(f"   Annual: {len(clean_annual)} clean statements saved (dropped {sentinel_annual_dropped} sentinel/corrupt rows).")
    
    # Quarterly
    sentinel_qtr_dropped = 0
    clean_qtr = []
    with open(quarterly_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        q_fieldnames = reader.fieldnames
        for row in reader:
            has_sentinel = any(val in str(v) for v in row.values() for val in ('12121', '435451', '168643'))
            pend = row.get('period_end_date', '').strip()
            if has_sentinel or pend > '2026-10-13':
                sentinel_qtr_dropped += 1
                continue
                
            sym = row.get('symbol', '').strip().upper()
            fyear = parse_int(row.get('fiscal_year'), 0)
            fqtr = row.get('fiscal_quarter', '').strip().upper()
            
            pub_date = filing_dates.get((sym, fyear, fqtr))
            if not pub_date and pend:
                try:
                    dt = datetime.strptime(pend, '%Y-%m-%d')
                    pub_date = (dt + timedelta(days=45)).strftime('%Y-%m-%d')
                except:
                    pub_date = pend
                    
            row['publication_date'] = pub_date
            clean_qtr.append(row)
            
    q_fields = ['symbol', 'company_name', 'sector', 'periodicity', 'fiscal_year', 'fiscal_quarter', 'period_end_date', 'publication_date'] + [col for col in q_fieldnames if col not in ('symbol', 'company_name', 'sector', 'periodicity', 'fiscal_year', 'fiscal_quarter', 'period_end_date')]
    out_qtr_path = os.path.join(OUTPUT_DIR, "kse100_fundamentals_quarterly_clean.csv")
    with open(out_qtr_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=q_fields)
        writer.writeheader()
        writer.writerows(clean_qtr)
        
    print(f"   Quarterly: {len(clean_qtr)} clean statements saved (dropped {sentinel_qtr_dropped} sentinel/corrupt rows).")
    return len(clean_annual), sentinel_annual_dropped, len(clean_qtr), sentinel_qtr_dropped

def clean_stock_prices(prices_path, valid_calendar_dates, payouts_by_symbol):
    """
    Cleans 475k historical stock prices:
    - Drops weekend & non-exchange holiday rows
    - Drops non-positive closes (<= 0)
    - Enforces OHLC envelope rules
    - Computes cumulative dividend/split adjusted close & open
    - Computes 1-day log returns and active trade indicators
    """
    print("-> Cleaning Historical Stock Prices & Building Adjusted Prices...")
    
    # 1. Group rows by symbol
    by_symbol = {}
    total_raw = 0
    dropped_non_calendar = 0
    dropped_non_pos = 0
    
    with open(prices_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_raw += 1
            d_str = row['date'].strip()
            sym = row['symbol'].strip().upper()
            
            # Check calendar
            if d_str not in valid_calendar_dates:
                dropped_non_calendar += 1
                continue
                
            close_val = parse_float(row.get('close'))
            if close_val is None or close_val <= 0:
                dropped_non_pos += 1
                continue
                
            vol_val = parse_int(row.get('volume'), 0)
            mcap_val = parse_float(row.get('marketCap'), 0.0)
            sector_val = row.get('sector', '').strip().upper()
            
            # Open/High/Low approximation or true values
            open_val = parse_float(row.get('open'), close_val)
            high_val = parse_float(row.get('high'), close_val)
            low_val = parse_float(row.get('low'), close_val)
            
            # Enforce OHLC envelope
            true_high = max(high_val, open_val, close_val)
            true_low = min(low_val, open_val, close_val)
            
            by_symbol.setdefault(sym, []).append({
                'symbol': sym,
                'date': d_str,
                'open': open_val,
                'high': true_high,
                'low': true_low,
                'close': close_val,
                'volume': vol_val,
                'market_cap': mcap_val,
                'sector': sector_val
            })
            
    print(f"   Raw rows processed: {total_raw}")
    print(f"   Dropped non-calendar rows (weekends/holidays): {dropped_non_calendar}")
    print(f"   Dropped non-positive closes: {dropped_non_pos}")
    
    # 2. Process each symbol chronologically to calculate adjustments and returns
    all_cleaned_prices = []
    envelope_adjusted = 0
    flat_bars = 0
    
    for sym, rows in by_symbol.items():
        # Sort chronologically
        rows.sort(key=lambda x: x['date'])
        
        # Build adjustment factors from payouts
        # Payout events for this symbol
        payouts = payouts_by_symbol.get(sym, [])
        payout_map = {} # date -> list of events
        for p in payouts:
            pdate = p['announcement_date']
            if pdate:
                payout_map.setdefault(pdate, []).append(p)
                
        # Backward cumulative adjustment
        # Adj factor initially 1.0 at terminal date
        # If dividend D on date t: factor prior to t is multiplied by (1 - D / Close_{t-1})
        n = len(rows)
        adj_factors = [1.0] * n
        current_factor = 1.0
        
        for i in range(n - 1, 0, -1):
            curr_date = rows[i]['date']
            prev_close = rows[i - 1]['close']
            
            if curr_date in payout_map and prev_close > 0:
                for ev in payout_map[curr_date]:
                    pt = ev['payout_type']
                    div = ev['dividend_per_share_pkr']
                    pct = ev['payout_percentage']
                    
                    if pt == 'dividend' and div > 0 and div < prev_close:
                        current_factor *= (1.0 - (div / prev_close))
                    elif pt == 'bonus' and pct > 0:
                        current_factor /= (1.0 + (pct / 100.0))
                    elif pt == 'split' and pct > 0:
                        current_factor /= pct
                        
            adj_factors[i - 1] = current_factor
            
        # Attach adjusted metrics and log returns
        for i in range(n):
            r = rows[i]
            af = adj_factors[i]
            adj_close = round(r['close'] * af, 4)
            adj_open = round(r['open'] * af, 4)
            adj_high = round(r['high'] * af, 4)
            adj_low = round(r['low'] * af, 4)
            
            # Log return
            if i > 0 and rows[i - 1]['close'] > 0:
                ret_1d = round(math.log(r['close'] / rows[i - 1]['close']), 6)
            else:
                ret_1d = 0.0
                
            # Active trade indicator (real volume traded)
            is_active = 1 if r['volume'] > 0 else 0
            is_flat = 1 if (i > 0 and r['close'] == rows[i - 1]['close'] and r['volume'] == 0) else 0
            if is_flat:
                flat_bars += 1
            
            all_cleaned_prices.append({
                'symbol': r['symbol'],
                'trading_date': r['date'],
                'open': r['open'],
                'high': r['high'],
                'low': r['low'],
                'close': r['close'],
                'adjusted_open': adj_open,
                'adjusted_high': adj_high,
                'adjusted_low': adj_low,
                'adjusted_close': adj_close,
                'volume': r['volume'],
                'market_cap': r['market_cap'],
                'log_return_1d': ret_1d,
                'is_active_trade': is_active,
                'sector': r['sector']
            })
            
    # Sort all by date, then symbol
    all_cleaned_prices.sort(key=lambda x: (x['trading_date'], x['symbol']))
    
    out_path = os.path.join(OUTPUT_DIR, "kse100_stocks_historical_clean.csv")
    fieldnames = [
        'symbol', 'trading_date', 'open', 'high', 'low', 'close',
        'adjusted_open', 'adjusted_high', 'adjusted_low', 'adjusted_close',
        'volume', 'market_cap', 'log_return_1d', 'is_active_trade', 'sector'
    ]
    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_cleaned_prices)
        
    print(f"   Cleaned Prices: {len(all_cleaned_prices)} valid rows saved to {out_path}.")
    print(f"   Flat bar sessions flagged: {flat_bars} ({flat_bars/len(all_cleaned_prices)*100:.2f}%)")
    
    return {
        'total_raw_rows': total_raw,
        'valid_cleaned_rows': len(all_cleaned_prices),
        'dropped_non_calendar': dropped_non_calendar,
        'dropped_non_positive_close': dropped_non_pos,
        'flat_bar_sessions_flagged': flat_bars
    }

def main():
    print("=" * 60)
    print("PSXPERT DATA CLEANING & ETL NORMALIZATION PIPELINE")
    print("=" * 60)
    start_time = datetime.now()
    ensure_dir(OUTPUT_DIR)
    
    # 1. Clean Calendar
    cal_path = os.path.join(DATA_DIR, "kse100_index_history_2002_2026.csv")
    valid_dates = clean_calendar(cal_path)
    
    # 2. Clean Companies Directory
    comp_path = os.path.join(DATA_DIR, "psx_companies_directory.csv")
    const_path = os.path.join(DATA_DIR, "kse100_constituents.csv")
    companies = clean_companies(comp_path, const_path)
    
    # 3. Clean Corporate Payouts
    payouts_path = os.path.join(DATA_DIR, "kse100_corporate_payouts_2001_2026.csv")
    payouts_by_sym, kept_payouts, dropped_payouts = clean_payouts(payouts_path)
    
    # 4. Index Corporate Announcements
    ann_path = os.path.join(DATA_DIR, "kse100_corporate_announcements.csv")
    filing_dates = build_announcement_filing_dates(ann_path)
    
    # 5. Clean Fundamentals
    ann_fund_path = os.path.join(DATA_DIR, "kse100_fundamentals_annual.csv")
    qtr_fund_path = os.path.join(DATA_DIR, "kse100_fundamentals_quarterly.csv")
    ann_kept, ann_dropped, qtr_kept, qtr_dropped = clean_fundamentals(ann_fund_path, qtr_fund_path, filing_dates)
    
    # 6. Clean Stock Prices
    prices_path = os.path.join(DATA_DIR, "kse100_stocks_historical_2002_2026.csv")
    price_stats = clean_stock_prices(prices_path, valid_dates, payouts_by_sym)
    
    # 7. Write Audit Manifest
    duration = (datetime.now() - start_time).total_seconds()
    audit_manifest = {
        'timestamp': datetime.now().isoformat(),
        'execution_duration_seconds': duration,
        'summary': {
            'official_exchange_sessions': len(valid_dates),
            'companies_count': len(companies),
            'stock_prices': price_stats,
            'payouts': {
                'valid_events_kept': kept_payouts,
                'placeholder_rows_dropped': dropped_payouts
            },
            'fundamentals': {
                'annual_statements_kept': ann_kept,
                'annual_sentinels_dropped': ann_dropped,
                'quarterly_statements_kept': qtr_kept,
                'quarterly_sentinels_dropped': qtr_dropped
            }
        },
        'output_directory': OUTPUT_DIR,
        'output_files': [
            'kse100_calendar_clean.csv',
            'kse100_companies_clean.csv',
            'kse100_corporate_payouts_clean.csv',
            'kse100_fundamentals_annual_clean.csv',
            'kse100_fundamentals_quarterly_clean.csv',
            'kse100_stocks_historical_clean.csv'
        ]
    }
    
    audit_path = os.path.join(OUTPUT_DIR, "CLEANING_AUDIT_REPORT.json")
    with open(audit_path, 'w', encoding='utf-8') as f:
        json.dump(audit_manifest, f, indent=2)
        
    print("\n" + "=" * 60)
    print(f"PIPELINE COMPLETED SUCCESSFULLY in {duration:.2f}s!")
    print(f"Audit report written to: {audit_path}")
    print("=" * 60)

if __name__ == "__main__":
    main()
