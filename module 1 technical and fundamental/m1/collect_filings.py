"""Download selected original PSX documents linked by the public collection.
This preserves source PDFs; dates extracted by providers remain unverified.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlparse
import pandas as pd
import requests
from .collect_public import ROOT


def select_documents(frame):
    frame=frame[frame.pdf_url.fillna('').str.match(r'^https://dps\.psx\.com\.pk/download/(document|attachment)/[^\s]+\.pdf$')].copy()
    frame=frame.sort_values('announced_at',ascending=False)
    selected=[]
    for symbol,rows in frame.groupby('symbol'):
        categories=[('financial_result',r'financial result|financial statement'),
                    ('report_transmission',r'transmission.*(?:annual|quarterly)|annual report'),
                    ('corporate_action',r'bonus|split|reduction|right share|book closure|closure of share')]
        for kind,pattern in categories:
            take=rows[rows.title.str.contains(pattern,case=False,na=False,regex=True)].head(2)
            selected.extend(dict(**row,selection_category=kind) for row in take.to_dict('records'))
    return pd.DataFrame(selected).drop_duplicates('pdf_url') if selected else pd.DataFrame(columns=list(frame.columns)+['selection_category'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run');args=parser.parse_args()
    if not re.fullmatch(r'public_[0-9]{8}_[0-9]{6}',args.run):raise ValueError('Invalid run name')
    out=ROOT/'data'/'collected'/args.run
    source=out/'filing_document_links.csv.gz'
    docs=select_documents(pd.read_csv(source))
    folder=out/'original_documents';folder.mkdir(exist_ok=True)
    existing=[]
    if (out/'document_downloads.jsonl').exists():
        existing=[json.loads(x) for x in (out/'document_downloads.jsonl').read_text().splitlines() if x.strip()]
    done=set()
    for record in existing:
        if record.get('file'):
            assert hashlib.sha256((out/record['file']).read_bytes()).hexdigest()==record['sha256']
        done.add(record['pdf_url'])
    pending=docs[~docs.pdf_url.isin(done)]
    lock=threading.Lock();next_request=[0]
    def fetch(row):
        url=row['pdf_url'];result={k:row.get(k) for k in ('symbol','announcement_id','title','announced_at','pdf_url','selection_category')}
        result['retrieved_at']=datetime.now(timezone.utc).isoformat()
        with lock:
            pause=max(0,next_request[0]-time.monotonic());next_request[0]=max(next_request[0],time.monotonic())+.5
        if pause:time.sleep(pause)
        try:
            with requests.get(url,headers={'User-Agent':'PSXpert-Research/1.0'},timeout=(10,25),stream=True) as response:
                result['status']=response.status_code
                if response.status_code!=200:return result
                if urlparse(response.url).hostname!='dps.psx.com.pk':
                    result['error']='unexpected_redirect';return result
                body=bytearray()
                for chunk in response.iter_content(65536):
                    body.extend(chunk)
                    if len(body)>20*1024*1024:
                        result['error']='document_exceeds_20MB_limit';return result
                if not body.startswith(b'%PDF'):
                    result['error']='response_not_pdf';return result
                name=hashlib.sha256(url.encode()).hexdigest()[:20]+'.pdf'
                (folder/name).write_bytes(body)
                result.update(file=str((folder/name).relative_to(out)),bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),
                              text_extracted=False,dates_verified=False)
        except requests.RequestException as exc:result['error']=type(exc).__name__
        return result
    results=list(existing)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(fetch,row) for row in pending.to_dict('records')]):
            row=future.result();results.append(row)
            with (out/'document_downloads.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
            if len(results)%25==0:print('Documents',len(results),'of',len(docs),flush=True)
    pd.DataFrame(results).to_csv(out/'original_document_index.csv',index=False)
    summary=dict(selected=len(docs),downloaded=sum('file' in r for r in results),
                 bytes=sum(r.get('bytes',0) for r in results),failed=sum('file' not in r for r in results),
                 policy='Up to two recent financial results, report transmissions and corporate-action documents per stock. Original PDFs retained; provider-derived dates not independently certified.')
    (out/'documents_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    with (out/'REPORT.md').open('a',encoding='utf-8') as f:
        f.write('\n## Original filing documents\n\n'+json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
