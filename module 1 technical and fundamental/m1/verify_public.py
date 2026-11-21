"""Verify staged public-data checksums and basic quality invariants."""
import argparse
import gzip
import hashlib
import json
import re
import pandas as pd
from .collect_public import ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run');args=parser.parse_args()
    if not re.fullmatch(r'public_[0-9]{8}_[0-9]{6}',args.run):raise ValueError('Invalid run name')
    root=ROOT/'data'/'collected'/args.run
    summary=json.loads((root/'summary.json').read_text())
    events=[json.loads(x) for x in (root/'requests.jsonl').read_text().splitlines()]
    count=0
    for event in events:
        if 'raw_file' not in event:continue
        with gzip.open(root/event['raw_file'],'rb') as f:body=f.read()
        assert hashlib.sha256(body).hexdigest()==event['sha256'],event['key']
        count+=1
    prices=pd.read_csv(root/'completed_close_volume_candidates.csv.gz')
    assert not prices.duplicated(['symbol','trading_date']).any()
    assert pd.to_datetime(prices.trading_date).lt(summary['as_of']).all()
    assert pd.to_datetime(prices.trading_date).dt.weekday.lt(5).all()
    assert pd.to_numeric(prices.close).gt(0).all()
    quotes=pd.read_csv(root/'investify_quote_snapshots.csv.gz')
    history=pd.read_csv(root/'stock_price_history.csv.gz')
    history['day']=pd.to_datetime(history.date,utc=True).dt.strftime('%Y-%m-%d')
    joined=quotes.merge(history[history.day.eq(summary['as_of'])],on='symbol',suffixes=('_inv','_sar'))
    joined['close_agrees']=(pd.to_numeric(joined.c)-pd.to_numeric(joined.close)).abs().le(.005)
    joined['volume_agrees']=pd.to_numeric(joined.v).eq(pd.to_numeric(joined.volume))
    joined[['symbol','c','close','v','volume','close_agrees','volume_agrees']].to_csv(root/'latest_snapshot_crosscheck.csv',index=False)
    docs=[]
    if (root/'document_downloads.jsonl').exists():
        docs=[json.loads(x) for x in (root/'document_downloads.jsonl').read_text().splitlines()]
    verified=0
    for doc in docs:
        if not doc.get('file'):continue
        body=(root/doc['file']).read_bytes()
        assert body.startswith(b'%PDF')
        assert hashlib.sha256(body).hexdigest()==doc['sha256']
        verified+=1
    result=dict(raw_bodies_checksum_verified=count,unique_completed_price_candidates=len(prices),
        quote_overlap_symbols=len(joined),latest_close_agrees=int(joined.close_agrees.sum()),
        latest_volume_agrees=int(joined.volume_agrees.sum()),original_pdf_checksums_verified=verified,
        database_access='none',existing_artifacts_written=False,historical_ohlc_verified=False,financial_vintages_verified=False)
    (root/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
