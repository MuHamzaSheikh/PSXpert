"""Collect public Sarmaaya and Investify data into a new staging run only.
No database connections, credential use, source-data edits or model training.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlencode

import pandas as pd
import requests

ROOT=Path(__file__).resolve().parents[1]
API='https://beta-restapi.sarmaaya.pk/api'
INV='https://www.investify.pk'


def extract_props(html):
    chunks=[]
    for match in re.finditer(r'self\.__next_f\.push\((\[1,.*?\])\)',html):
        try: chunks.append(json.loads(match.group(1))[1])
        except (ValueError,IndexError): continue
    payload=''.join(chunks)
    for match in re.finditer(r'\{"stock":',payload):
        try: obj,_=json.JSONDecoder().raw_decode(payload[match.start():])
        except ValueError: continue
        if isinstance(obj,dict) and 'initialFundamental' in obj:
            return {k:obj.get(k) for k in ('stock','initialFundamental','initialProfile','announcements','corporateCalendar','indices')}
    return {}


def statement_records(body,symbol,statement,periodicity,url,retrieved):
    rows=[]
    response=body.get('response',{}) if isinstance(body,dict) else {}
    if not isinstance(response,dict):return rows
    for metric,info in response.items():
        if not isinstance(info,dict):continue
        for item in info.get('data',[]):
            if not isinstance(item,dict):continue
            value=item.get('value')
            # Repeated 12.230 values appear across unrelated historical metrics. Keep raw; quarantine.
            suspect=str(value).strip() in ('12.230','12.23','12121','12121.0')
            rows.append(dict(symbol=symbol,statement=statement,periodicity=periodicity,metric=metric,
                metric_code=info.get('metric'),display_type=info.get('displayType'),value_raw=value,
                period_end=item.get('date'),fiscal_year=item.get('year'),fiscal_period=item.get('fiscalPeriod'),
                provider_report_date=item.get('epsReportDate'),provider_created_at=item.get('createdAt'),
                provider_updated_at=item.get('updatedAt'),source_url=url,retrieved_at=retrieved,
                suspected_placeholder=suspect,unit_status='provider scale not independently verified',
                training_eligible=False,eligibility_reason='possible placeholder' if suspect else 'publication vintage and units require verification'))
    return rows


def flatten_ratios(obj,path=''):
    rows=[]
    if isinstance(obj,dict):
        if 'period' in obj and 'value' in obj:
            return [dict(metric=path,period=obj['period'],value=obj['value'])]
        for k,v in obj.items():rows.extend(flatten_ratios(v,f'{path}.{k}'.strip('.')))
    return rows


class Collector:
    def __init__(self,out,as_of,delay=.5):
        self.out=out;self.as_of=as_of;self.delay=delay
        self.lock=threading.Lock();self.next_request=0;self.local=threading.local()
        self.rows={};self.requests=[]
        manifest=out/'requests.jsonl'
        if manifest.exists():
            self.requests=[json.loads(line) for line in manifest.read_text(encoding='utf-8').splitlines() if line.strip()]
        self.cached={x['key']:x for x in self.requests}
        self.fundamentals_blocked=any('/stocks/fundamentals/' in x['url'] and x.get('status') in (401,403) for x in self.requests)

    def get(self,url,key,html=False):
        cached=self.cached.get(key)
        if cached:
            if cached.get('status')!=200:return None,cached
            path=self.out/cached['raw_file']
            with gzip.open(path,'rb') as f:content=f.read()
            if hashlib.sha256(content).hexdigest()!=cached['sha256']:raise ValueError('Cached response checksum mismatch')
            if html:return content.decode('utf-8',errors='replace'),cached
            return json.loads(content),cached
        if self.fundamentals_blocked and '/stocks/fundamentals/' in url:
            return None,dict(url=url,key=key,retrieved_at=datetime.now(timezone.utc).isoformat(),
                             skipped='fundamentals endpoint requires authentication')
        if not hasattr(self.local,'session'):
            self.local.session=requests.Session()
            self.local.session.headers.update({'User-Agent':'PSXpert-Research/1.0 (historical data collection)',
                                               'Accept':'application/json,text/html;q=0.9'})
        event={'url':url,'key':key,'retrieved_at':datetime.now(timezone.utc).isoformat()}
        content=b''
        for attempt in range(3):
            with self.lock:
                wait=max(0,self.next_request-time.monotonic());self.next_request=max(self.next_request,time.monotonic())+self.delay
            if wait:time.sleep(wait)
            try:
                r=self.local.session.get(url,timeout=(10,30))
                event.update(status=r.status_code,attempts=attempt+1,content_type=r.headers.get('Content-Type'),final_url=r.url)
                content=r.content
                if r.status_code in (429,500,502,503,504) and attempt<2:
                    retry=r.headers.get('Retry-After','')
                    time.sleep(min(30,int(retry)) if retry.isdigit() else 2**(attempt+1));continue
                break
            except requests.RequestException as exc:
                event.update(error=type(exc).__name__,attempts=attempt+1)
                if attempt<2:time.sleep(2**attempt)
        name=key+('.html.gz' if html else '.json.gz')
        path=self.out/'raw'/name;path.parent.mkdir(parents=True,exist_ok=True)
        if content:
            with gzip.open(path,'wb') as f:f.write(content)
            event.update(raw_file=str(path.relative_to(self.out)),sha256=hashlib.sha256(content).hexdigest(),bytes=len(content))
        event['access_restricted']=event.get('status') in (401,403)
        if event['access_restricted'] and '/stocks/fundamentals/' in url:self.fundamentals_blocked=True
        with self.lock:
            self.requests.append(event)
            with (self.out/'requests.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(event)+'\n')
        if event.get('status')!=200:return None,event
        if html:return content.decode('utf-8',errors='replace'),event
        try:
            obj=json.loads(content)
            if isinstance(obj,dict) and obj.get('success') is False:return None,event
            return obj,event
        except ValueError:return None,event

    def add(self,kind,rows):
        with self.lock:self.rows.setdefault(kind,[]).extend(rows)

    def symbol(self,symbol):
        profile,meta=self.get(f'{API}/stocks/{symbol}',f'sarmaaya/{symbol}/profile')
        p=profile.get('response',{}) if isinstance(profile,dict) else {}
        if not isinstance(p,dict):p={}
        self.add('company_profiles',[dict(symbol=symbol,**{k:v for k,v in p.items() if k!='symbol'},source_url=meta['url'],retrieved_at=meta['retrieved_at'])])
        body,meta=self.get(f'{API}/stocks/price-history/{symbol}?days=15000',f'sarmaaya/{symbol}/history')
        prices=[]
        for row in (body or {}).get('response',[]):
            if not isinstance(row,dict):continue
            prices.append(dict(symbol=symbol,date=row.get('date'),close=row.get('price',row.get('close')),
                open=row.get('open'),high=row.get('high'),low=row.get('low'),volume=row.get('volume'),
                market_cap=row.get('marketCap'),source='sarmaaya',source_url=meta['url'],retrieved_at=meta['retrieved_at']))
        self.add('stock_price_history',prices)
        isin=p.get('isin')
        nfund=0
        if isin:
            for periodicity in ('ANN','QTR'):
                for statement in ('income-statement','balance-sheet','cashflow','ratios'):
                    url=f'{API}/stocks/fundamentals/{statement}?'+urlencode(dict(isin=isin,periodicity=periodicity))
                    body,meta=self.get(url,f'sarmaaya/{symbol}/{periodicity}_{statement}')
                    rows=statement_records(body,symbol,statement,periodicity,url,meta['retrieved_at'])
                    nfund+=len(rows);self.add('financial_metrics',rows)
        url=f'{API}/stocks/announcements/{symbol}?'+urlencode(dict(startDate='2016-01-01',endDate=self.as_of))
        body,meta=self.get(url,f'sarmaaya/{symbol}/announcements')
        anns=[]
        for row in (body or {}).get('response',[]):
            if isinstance(row,dict):anns.append(dict(**row,source_url=url,retrieved_at=meta['retrieved_at']))
        self.add('sarmaaya_announcements',anns)
        # Fundamentals page embeds quote + ratios + public announcement records together.
        html,meta=self.get(f'{INV}/company/{symbol}/fundamentals',f'investify/{symbol}/fundamentals',html=True)
        props=extract_props(html) if html else {}
        if props:
            with gzip.open(self.out/'raw'/f'investify/{symbol}/parsed.json.gz','wt',encoding='utf-8') as f:json.dump(props,f)
            quote=props.get('stock') or {}
            self.add('investify_quote_snapshots',[dict(symbol=symbol,**{k:v for k,v in quote.items() if k!='symbol'},retrieved_at=meta['retrieved_at'],source_url=meta['url'],training_eligible=False)])
            self.add('investify_financial_snapshots',[dict(symbol=symbol,**row,retrieved_at=meta['retrieved_at'],source_url=meta['url'],training_eligible=False) for row in flatten_ratios(props.get('initialFundamental'))])
            announcements=props.get('announcements') or []
            if isinstance(announcements,dict):announcements=announcements.get('items',[])
            for row in announcements:
                if not isinstance(row,dict):continue
                self.add('investify_announcements',[dict(**row,retrieved_at=meta['retrieved_at'],page_url=meta['url'],training_eligible=False)])
                details=row.get('details') or {}
                action=details.get('corporateAction')
                financial=details.get('financial') or {}
                if action:
                    self.add('corporate_action_candidates',[dict(symbol=symbol,announcement_id=row.get('externalId'),announced_at=row.get('announcedAt'),
                        title=row.get('title'),pdf_url=row.get('pdfUrl'),**action,source='investify',
                        verification='provider extraction; NOT verified ex-date or adjustment factor',training_eligible=False)])
                self.add('filing_document_links',[dict(symbol=symbol,announcement_id=row.get('externalId'),title=row.get('title'),
                    announced_at=row.get('announcedAt'),pdf_url=row.get('pdfUrl'),image_url=row.get('imageUrl'),
                    source='investify',classification=row.get('classification'),financial=financial,
                    original_document_downloaded=False,publication_timestamp_verified=False)])
        print(f'{symbol}: {len(prices)} price rows, {nfund} financial values, {len(anns)} Sarmaaya announcements, Investify={bool(props)}',flush=True)
        return dict(symbol=symbol,prices=len(prices),financial_values=nfund,investify_parsed=bool(props))

    def finish(self,coverage):
        summary={'as_of':self.as_of,'symbols':len(coverage),'coverage':coverage,'tables':{},
                 'requests':len(self.requests),'successful_requests':sum(x.get('status')==200 for x in self.requests),
                 'failed_requests':[x for x in self.requests if x.get('status')!=200],
                 'limitations':['Sarmaaya price history may supply only close, volume and market cap; no OHLC imputation.',
                    'Historical Investify chart endpoint denied public access; no authentication bypass attempted.',
                    'Sarmaaya dividend and fundamental endpoints require authentication; financial collection stops on access denial.',
                    'Financial snapshots and provider timestamps are not verified historical accounting vintages.',
                    'Repeated possible placeholders and unknown units are quarantined from training.',
                    'Investify action summaries may use AI extraction; payment/effective dates are not assumed ex-dates.',
                    'Current KSE100 roster is not historical membership. Original filing links are collected, not all source PDFs.',
                    'Current-day observations are retained raw but excluded from completed-session price candidates.']}
        for name,rows in self.rows.items():
            frame=pd.DataFrame(rows)
            for col in frame:
                if frame[col].map(lambda x:isinstance(x,(dict,list))).any():
                    frame[col]=frame[col].map(lambda x:json.dumps(x,ensure_ascii=False) if isinstance(x,(dict,list)) else x)
            frame.to_csv(self.out/f'{name}.csv.gz',index=False)
            summary['tables'][name]=len(frame)
        prices=pd.DataFrame(self.rows.get('stock_price_history',[]))
        if not prices.empty:
            prices['trading_date']=pd.to_datetime(prices.date,utc=True,errors='coerce').dt.tz_convert('Asia/Karachi').dt.tz_localize(None).dt.normalize()
            prices['invalid_close']=pd.to_numeric(prices.close,errors='coerce').le(0)|pd.to_numeric(prices.close,errors='coerce').isna()
            prices['weekend']=prices.trading_date.dt.weekday.ge(5)
            prices['incomplete_or_future_day']=prices.trading_date.ge(pd.Timestamp(self.as_of))
            prices['duplicate_key']=prices.duplicated(['symbol','trading_date'],keep=False)
            index=pd.DataFrame(self.rows.get('kse100_history',[]))
            cal=pd.to_datetime(index['date'],utc=True,errors='coerce').dt.tz_localize(None).dt.normalize() if 'date' in index else pd.Series([],dtype='datetime64[ns]')
            prices['not_in_index_calendar']=~prices.trading_date.isin(cal)
            flags=['invalid_close','weekend','incomplete_or_future_day','duplicate_key','not_in_index_calendar']
            prices['eligible_close_volume_candidate']=~prices[flags].any(axis=1)
            prices.to_csv(self.out/'price_quality_ledger.csv.gz',index=False)
            valid=prices[prices.eligible_close_volume_candidate]
            valid.to_csv(self.out/'completed_close_volume_candidates.csv.gz',index=False)
            summary['price_quality']={c:int(prices[c].sum()) for c in flags}
            summary['price_quality'].update(candidate_rows=len(valid),new_candidate_rows_since_v2=int(valid.trading_date.gt('2026-10-13').sum()),
                first_date=str(valid.trading_date.min()),last_date=str(valid.trading_date.max()),
                full_ohlc_rows=int(valid[['open','high','low','close']].notna().all(axis=1).sum()))
            valid.groupby('symbol').agg(rows=('close','size'),first_date=('trading_date','min'),last_date=('trading_date','max')).to_csv(self.out/'price_coverage_by_ticker.csv')
        financial=pd.DataFrame(self.rows.get('financial_metrics',[]))
        if not financial.empty:
            summary['suspected_placeholder_financial_values']=int(financial.suspected_placeholder.sum())
            financial.groupby(['symbol','statement','periodicity']).agg(rows=('metric','size'),suspected_placeholders=('suspected_placeholder','sum')).to_csv(self.out/'financial_coverage.csv')
        (self.out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        lines=['# Public data collection', '',f"Run date: {self.as_of}. Stocks: {len(coverage)}. All outputs are staged; no database or existing artifacts were modified.",'','| Table | Rows |','|---|---:|']
        lines += [f'| {k} | {v:,} |' for k,v in summary['tables'].items()]
        lines += ['','## Price quality','',json.dumps(summary.get('price_quality',{}),indent=2),'','## Remaining gaps','']
        lines += ['- '+x for x in summary['limitations']]
        lines += ['','## Reproduce','',f'`python -m m1.collect_public --as-of {self.as_of}` creates a new timestamped staging run. Raw HTTP bodies, retrieval timestamps, source URLs and SHA-256 checksums are saved. No data is automatically admitted to training.']
        (self.out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in summary.items() if k not in ('coverage','failed_requests')},indent=2),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of',required=True)
    parser.add_argument('--limit',type=int)
    parser.add_argument('--resume',help='Existing collection directory name, under data/collected only')
    args=parser.parse_args()
    pd.Timestamp(args.as_of)
    out=ROOT/'data'/'collected'/('public_'+args.as_of.replace('-','')+'_'+datetime.now(timezone.utc).strftime('%H%M%S'))
    if args.resume:
        if not re.fullmatch(r'public_[0-9]{8}_[0-9]{6}',args.resume):raise ValueError('Invalid run name')
        out=ROOT/'data'/'collected'/args.resume
        if not out.is_dir():raise ValueError('Run does not exist')
    else:out.mkdir(parents=True,exist_ok=False)
    c=Collector(out,args.as_of)
    print('OUTPUT',out,flush=True)
    roster,meta=c.get(API+'/stocks/ticker?index=KSE100','sarmaaya/roster')
    if not roster or not isinstance(roster.get('response'),list):raise RuntimeError('Public roster unavailable')
    c.add('current_kse100_roster',roster['response'])
    symbols=sorted({x['symbol'] for x in roster['response'] if re.fullmatch('[A-Z0-9-]{1,20}',x.get('symbol',''))})
    if args.limit:symbols=symbols[:args.limit]
    index,meta=c.get(API+'/indices/price-history/KSE100?days=15000','sarmaaya/kse100_history')
    c.add('kse100_history',[(dict(**x,source_url=meta['url'],retrieved_at=meta['retrieved_at'])) for x in (index or {}).get('response',[])])
    # Record access restrictions once, rather than repeat a denied request for every stock.
    c.get(API+'/stocks/dividends/OGDC','access_checks/sarmaaya_dividends')
    c.get(INV+'/api/v1/charts/daily/stock/OGDC?range=5Y','access_checks/investify_chart')
    coverage=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(c.symbol,s):s for s in symbols}
        for future in as_completed(futures):
            try:coverage.append(future.result())
            except Exception as exc:
                coverage.append(dict(symbol=futures[future],error=type(exc).__name__,detail=str(exc)))
                print('ERROR',futures[future],type(exc).__name__,str(exc),flush=True)
    c.finish(sorted(coverage,key=lambda x:x['symbol']))


if __name__=='__main__':main()
