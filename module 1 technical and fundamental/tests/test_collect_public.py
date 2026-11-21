import json
from m1.collect_public import extract_props,statement_records,flatten_ratios

def test_public_props_without_executing_scripts():
 p={'stock':{'sym':'AAA'},'initialFundamental':{'earn':{'aeps':{'period':'2026 FY','value':4}}},'announcements':[]}
 html='<script>self.__next_f.push('+json.dumps([1,'1:'+json.dumps(p)+'\n'])+')</script>'
 result=extract_props(html)
 assert result['stock']['sym']=='AAA'
 assert flatten_ratios(result['initialFundamental'])==[{'metric':'earn.aeps','period':'2026 FY','value':4}]

def test_placeholder_and_vintage_quarantine():
 body={'response':{'Revenue':{'metric':'SALES','data':[{'value':'12.230','date':'2025-06-30','epsReportDate':'2025-09-23'},{'value':449190.752,'date':'2026-06-30'}]}}}
 rows=statement_records(body,'OGDC','income-statement','ANN','https://example.test','2026-11-17')
 assert rows[0]['suspected_placeholder']
 assert rows[0]['provider_report_date']=='2025-09-23'
 assert not rows[1]['suspected_placeholder']
 assert all(not x['training_eligible'] for x in rows)

def test_no_missing_page_data_invented():
 assert extract_props('<html>Sign in</html>')=={}
 assert statement_records(None,'AAA','income','ANN','url','now')==[]


def test_auth_denial_stops_fundamentals_without_network(tmp_path):
    from m1.collect_public import Collector
    c=Collector(tmp_path,'2026-11-17')
    c.fundamentals_blocked=True
    body,meta=c.get('https://beta-restapi.sarmaaya.pk/api/stocks/fundamentals/cashflow?isin=TEST','test')
    assert body is None and 'authentication' in meta['skipped']
    assert not hasattr(c.local,'session')


def test_filing_selection_rejects_untrusted_urls():
    import pandas as pd
    from m1.collect_filings import select_documents
    rows=pd.DataFrame([dict(symbol='AAA',pdf_url='https://evil.test/fake.pdf',title='Financial results',announced_at='2026-11-01'),
                       dict(symbol='AAA',pdf_url='https://dps.psx.com.pk/download/document/123.pdf',title='Financial results',announced_at='2026-11-01')])
    selected=select_documents(rows)
    assert len(selected)==1
    assert selected.iloc[0].pdf_url.startswith('https://dps.psx.com.pk/')
