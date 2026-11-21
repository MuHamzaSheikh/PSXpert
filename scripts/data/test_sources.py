import requests
import re
import json
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

print("=== 1. Checking Sarmaaya ===")
try:
    r = requests.get('https://sarmaaya.pk/stocks/OGDC', headers=headers, timeout=10)
    print("Sarmaaya /stocks/OGDC status:", r.status_code, "len:", len(r.text))
    urls = re.findall(r'https?://[^\s"\'<>]+', r.text)
    api_urls = [u for u in urls if 'api' in u.lower() or 'stocks' in u.lower()]
    print("Found API/stock links in Sarmaaya page:", len(api_urls))
    for u in list(set(api_urls))[:10]:
        print("  ", u)
except Exception as e:
    print("Sarmaaya error:", e)

print("\n=== 2. Checking Investify ===")
try:
    r2 = requests.get('https://investify.pk/stocks/OGDC', headers=headers, timeout=10)
    print("Investify /stocks/OGDC status:", r2.status_code, "len:", len(r2.text))
except Exception as e:
    print("Investify error:", e)

print("\n=== 3. Checking DPS PSX ===")
try:
    # Check DPS PSX financial results endpoints
    r3 = requests.get('https://dps.psx.com.pk/company/OGDC', headers=headers, timeout=10)
    print("DPS /company/OGDC status:", r3.status_code, "len:", len(r3.text))
    # Look for year patterns in DPS
    years = re.findall(r'\b(19\d\d|20\d\d)\b', r3.text)
    year_counts = {y: years.count(y) for y in sorted(set(years))}
    print("Years found in DPS OGDC page:", sorted([y for y, c in year_counts.items() if c > 3]))
except Exception as e:
    print("DPS error:", e)

print("\n=== 4. Checking SCS Trade (scstrade.com) ===")
try:
    r4 = requests.get('https://www.scstrade.com/stockscreening/SS_CompanySnapShot.aspx?symbol=OGDC', headers=headers, timeout=10)
    print("SCSTrade status:", r4.status_code, "len:", len(r4.text))
    years_scs = re.findall(r'\b(20\d\d)\b', r4.text)
    print("Years found in SCSTrade:", sorted(set(years_scs)))
except Exception as e:
    print("SCSTrade error:", e)

print("\n=== 5. Checking State Bank of Pakistan (SBP) Financial Statement Analysis ===")
try:
    r5 = requests.get('https://www.sbp.org.pk/publications/fsa/index.htm', headers=headers, timeout=10)
    print("SBP FSA publication status:", r5.status_code, "len:", len(r5.text))
    soup5 = BeautifulSoup(r5.text, 'html.parser')
    fsa_links = [a['href'] for a in soup5.find_all('a', href=True) if 'fsa' in a['href'].lower() or '.pdf' in a['href'].lower() or '.xls' in a['href'].lower()]
    print("SBP FSA links found:", len(fsa_links))
    for l in fsa_links[:10]:
        print("  ", l)
except Exception as e:
    print("SBP error:", e)
