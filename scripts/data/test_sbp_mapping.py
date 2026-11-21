import pandas as pd
import re

# Load KSE-100 companies
companies = pd.read_csv('data/processed/companies_clean.csv')
kse100 = companies[companies['is_kse100'] == True].copy()

# Load SBP orgs from 2014-23 sheet
df_sbp = pd.read_excel('data/raw/sbp_fsa_archive_2005_2023.xlsx', sheet_name='2014-23', usecols=['Sector/Organization Name'])
sbp_orgs = sorted(df_sbp['Sector/Organization Name'].dropna().unique())

# Also load Financial Sector file
wb_fin = pd.read_excel('data/raw/sbp_fsa_financial_sector_2021_2025.xlsx', sheet_name=None)
print("Financial sector sheets:", list(wb_fin.keys()))

def clean_name(s):
    s = s.lower()
    s = re.sub(r'\(.*?\)', '', s)
    s = re.sub(r'\b(ltd|limited|co|corp|corporation|pakistan|bank)\b', '', s)
    return s.strip()

print(f"\nAnalyzing KSE-100 mapping against {len(sbp_orgs)} SBP non-financial organizations...")
mapped = {}
unmapped = []

for idx, row in kse100.iterrows():
    sym = row['symbol']
    cname = row['company_name']
    sector = row['sector']
    
    # Try exact or partial matches
    c_clean = clean_name(cname)
    best = None
    for org in sbp_orgs:
        org_clean = clean_name(re.sub(r'^\d+\s*-\s*', '', org))
        # direct contains or high overlap
        words = [w for w in c_clean.split() if len(w) > 3]
        if words and all(w in org_clean for w in words):
            best = org
            break
        elif words and words[0] in org_clean and (len(words) == 1 or words[1] in org_clean):
            best = org
            break
            
    if best:
        mapped[sym] = (cname, best)
    else:
        unmapped.append((sym, cname, sector))

print(f"Directly mapped: {len(mapped)}")
print(f"Unmapped / Financial sector: {len(unmapped)}")
print("\nUnmapped sample:")
for u in unmapped[:15]:
    print(" ", u)
