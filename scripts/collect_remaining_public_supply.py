"""Collect publicly accessible remaining supply context; no fabricated operations.

JJM household/tap snapshots, official PMC tanker-register files, statewide
tanker PDFs and public PoCRA attributes retain independent source lineage.
No application database writes or authority-access bypasses.
"""
import argparse
import concurrent.futures
import hashlib
import json
import re
import time
import uuid
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote,urljoin,urlparse

import httpx

ROOT=Path('data/raw/supply/public-completion')
REPORT=Path('data/water/public-supply-completion.json')
JJM='https://ejalshakti.gov.in/jjmreport/JJMVillage_Profile.aspx/'
PMC='https://webadmin.pmc.gov.in'
TANKERS='https://water.maharashtra.gov.in/en/document-category/tanker-report/'


def stamp():return datetime.now(timezone.utc).isoformat()


def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    part=path.with_suffix(path.suffix+'.'+uuid.uuid4().hex+'.tmp')
    try:
        part.write_text(json.dumps(value,ensure_ascii=True,indent=2),encoding='utf-8');part.replace(path)
    finally:part.unlink(missing_ok=True)


def enc(value):return quote(''.join(chr(ord(c)+1) for c in str(value)),safe='@*_+-./')+'1'


def fetch(path,url,*,body=None,params=None,limit=25_000_000,refresh=False):
    receipt_path=path.with_suffix(path.suffix+'.receipt.json')
    requested_url=str(httpx.URL(url,params=params)) if params else str(httpx.URL(url))
    if path.exists() and receipt_path.exists() and not refresh:
        receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
        same_request=receipt.get('requested_url',receipt['url'])==requested_url and receipt.get('request')==body
        if same_request and hashlib.sha256(path.read_bytes()).hexdigest()==receipt['sha256']:return path,receipt
    path.parent.mkdir(parents=True,exist_ok=True)
    part=path.with_suffix(path.suffix+'.part')
    try:
        for attempt in range(3):
            try:
                with httpx.Client(timeout=httpx.Timeout(40,connect=12),follow_redirects=True) as client:
                    with client.stream('POST' if body is not None else 'GET',url,json=body,params=params) as response:
                        response.raise_for_status();sha=hashlib.sha256();size=0
                        with part.open('wb') as f:
                            for chunk in response.iter_bytes():
                                size+=len(chunk)
                                if size>limit:raise ValueError('Public file exceeds download limit')
                                sha.update(chunk);f.write(chunk)
                        receipt={'url':str(response.url),'requested_url':requested_url,'request':body,'retrieved_at':stamp(),'bytes':size,
                                 'sha256':sha.hexdigest(),'http_status':response.status_code}
                break
            except httpx.HTTPError:
                if attempt==2:raise
                time.sleep(attempt+1)
        if path.suffix=='.json':json.loads(part.read_bytes())
        if path.suffix=='.pdf' and not part.read_bytes().startswith(b'%PDF'):raise ValueError('Not a PDF')
        part.replace(path);atomic(receipt_path,receipt);return path,receipt
    finally:part.unlink(missing_ok=True)


def collect_jjm(refresh=False):
    url='https://ejalshakti.gov.in/JJMReport/content/JsIot/JJM_Iot_Village_Legend.js?v=20220216165452'
    p,receipt=fetch(ROOT/'jjm'/'legend.js',url,refresh=refresh)
    text=p.read_text(encoding='utf-8-sig')
    marker=re.search(r'var\s+DtPoint\s*=\s*',text)
    if not marker:raise ValueError('JJM district definition changed')
    districts,_=json.JSONDecoder().raw_decode(text[marker.end():])
    districts=[r for r in districts if str(r.get('StKeyValue'))=='27']
    if len(districts)!=34 or len({r['KeyValue'] for r in districts})!=34:raise ValueError('Review changed rural JJM district coverage')
    atomic(ROOT/'jjm'/'districts.json',districts)
    def one(district):
        code=str(district['KeyValue'])
        payload={k:enc(v) for k,v in {'cat':'0','subcat':'0','param':'0','stcode':'27','dtcode':code}.items()}
        try:
            path,r=fetch(ROOT/'jjm'/('villages-'+code+'.json'),JJM+'BindVillageData',body=payload,refresh=refresh)
            rows=json.loads(path.read_bytes())['d']
            if not isinstance(rows,list) or len({v['KeyId'] for v in rows})!=len(rows):raise ValueError('Unexpected/duplicate JJM village IDs')
            normalized=[]
            for row in rows:
                total,taps=float(row['Total']),float(row['Value'])
                if min(total,taps)<0 or taps>total:raise ValueError('Inconsistent household/tap counts')
                normalized.append({'jjm_village_id':row['KeyId'],'census_code_as_reported':row.get('KeyValue','').strip(),
                    'village_name':row['Name'],'jjm_district_code':code,'district':district['Name'],
                    'reported_households':total,'reported_tap_connections':taps,'retrieved_at':r['retrieved_at'],
                    'observed_on':None,'source_url':r['url'],'raw_sha256':r['sha256'],
                    'basis':'administrative_snapshot_measurement_vintage_unknown','measured_daily_supply_litres':None})
            return {'district':district['Name'],'code':code,'status':'downloaded','rows':len(rows),
                    'households':sum(v['reported_households'] for v in normalized),
                    'tap_connections':sum(v['reported_tap_connections'] for v in normalized),'receipt':r,'records':normalized}
        except (httpx.HTTPError,ValueError,KeyError,TypeError) as e:return {'district':district['Name'],'code':code,'status':'failed','error':type(e).__name__,'detail':str(e)[:180]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(one,districts))
    records=[v for d in results for v in d.pop('records',[])]
    ids={r['jjm_village_id'] for r in records}
    if len(ids)!=len(records):raise ValueError('JJM village appears in multiple district snapshots')
    output=ROOT/'jjm'/'village-households.jsonl'
    with output.open('w',encoding='utf-8') as f:
        for row in records:f.write(json.dumps(row,ensure_ascii=True)+'\n')
    return {'status':'collected' if all(d['status']=='downloaded' for d in results) else 'partial',
            'source':'JJM public village profile','districts_requested':len(districts),'districts_completed':sum(d['status']=='downloaded' for d in results),
            'village_records':len(records),'reported_households':sum(v['reported_households'] for v in records),
            'reported_tap_connections':sum(v['reported_tap_connections'] for v in records),
            'output':str(output),'districts':results,'limitations':'Counts are administrative snapshots, with unknown observation vintage. Rural dashboard coverage is not all 44,929 directory villages. Census IDs are identity metadata, not 2011 demographic inputs. No deliveries, tank levels, current measured demand or emergency labels are inferred.'}


def collect_pmc(refresh=False):
    url=PMC+'/en/jsonapi/node/water_tanker'
    params={'include':'field_file_upload','page[limit]':50,'sort':'-field_file_upload_date'}
    records,files,seen=[],{},set();page=0;pagination_error=None
    while url:
        if page>=100 or url in seen:raise ValueError('PMC pagination limit/cycle')
        seen.add(url)
        try:path,receipt=fetch(ROOT/'pmc'/f'index-{page:03}.json',url,params=params,refresh=refresh)
        except httpx.HTTPError as error:
            pagination_error={'url':url,'error':type(error).__name__,'detail':str(error)[:150]};break
        data=json.loads(path.read_bytes());included={r['id']:r for r in data.get('included',[]) if r.get('type')=='file--file'}
        for node in data.get('data',[]):
            a=node['attributes'];rel=node.get('relationships',{}).get('field_file_upload',{}).get('data')
            if not rel:continue
            if isinstance(rel,list):rels=rel
            else:rels=[rel]
            for relation in rels:
                file=included.get(relation['id'])
                if not file:continue
                fa=file['attributes'];file_url=urljoin(PMC,fa['uri']['url']).replace('http://webadmin.pmc.gov.in','https://webadmin.pmc.gov.in')
                if urlparse(file_url).hostname!='webadmin.pmc.gov.in':raise ValueError('Unreviewed file host')
                entry={'node_id':node['id'],'file_id':file['id'],'title':a.get('title'),'upload_date':a.get('field_file_upload_date'),
                    'created':a.get('created'),'changed':a.get('changed'),'file_url':file_url,'filename':fa.get('filename'),
                    'bytes_reported':fa.get('filesize'),'index_receipt_sha256':receipt['sha256'],'retrieved_at':receipt['retrieved_at']}
                records.append(entry);files[file['id']]=entry
        link=data.get('links',{}).get('next',{});url=link.get('href') if isinstance(link,dict) else None
        if url:
            url=url.replace('http://webadmin.pmc.gov.in','https://webadmin.pmc.gov.in')
            if urlparse(url).hostname!='webadmin.pmc.gov.in':raise ValueError('Unreviewed pagination host')
        page+=1;params=None
    atomic(ROOT/'pmc'/'register-index.json',records)
    def one(entry):
        suffix=Path(urlparse(entry['file_url']).path).suffix.lower()
        if suffix not in ('.xlsx','.xls','.pdf','.csv'):return {**entry,'status':'unsupported_format'}
        try:
            p,r=fetch(ROOT/'pmc'/'files'/(entry['file_id']+suffix),entry['file_url'],refresh=refresh)
            return {**entry,'status':'downloaded','path':str(p),'receipt':r}
        except (httpx.HTTPError,ValueError) as e:return {**entry,'status':'failed','error':type(e).__name__}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:downloads=list(pool.map(one,files.values()))
    atomic(ROOT/'pmc'/'downloads.json',downloads)
    return {'status':'partial' if pagination_error or any(r['status']=='failed' for r in downloads) else 'collected',
        'source':PMC+'/en/jsonapi/node/water_tanker','index_complete':pagination_error is None,'pagination_error':pagination_error,
        'index_pages':page,'register_entries':len(records),'distinct_files':len(files),
        'downloaded_files':sum(r['status']=='downloaded' for r in downloads),'failed_files':sum(r['status']=='failed' for r in downloads),
        'index':str(ROOT/'pmc'/'register-index.json'),'manifest':str(ROOT/'pmc'/'downloads.json'),
        'limitations':'Official urban PMC dispatch registers; not statewide rural coverage or assessed need. Upload dates are not dispatch dates. Litres require explicit source capacity/volume, not a default tanker size. No village urgency labels inferred.'}


class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            d=dict(attrs)
            if d.get('href'):self.links.append(d['href'])


def collect_tankers(refresh=False):
    urls=set();pages=[]
    for number in range(1,8):
        url=TANKERS if number==1 else TANKERS+f'page/{number}'
        try:
            p,r=fetch(ROOT/'wssd'/f'listing-{number}.html',url,refresh=refresh)
            parser=Links();parser.feed(p.read_text(encoding='utf-8'))
            found={urljoin(url,v) for v in parser.links if '.pdf' in v.lower() and 'cdnbbsr.s3waas.gov.in' in v}
            urls.update(found);pages.append({'url':url,'pdf_links':len(found),'receipt':r})
        except (httpx.HTTPError,ValueError) as e:pages.append({'url':url,'error':type(e).__name__})
    def one(url):
        try:
            p,r=fetch(ROOT/'wssd'/'pdfs'/(hashlib.sha256(url.encode()).hexdigest()[:20]+'.pdf'),url,refresh=refresh)
            return {'url':url,'path':str(p),'status':'downloaded','receipt':r}
        except (httpx.HTTPError,ValueError) as e:return {'url':url,'status':'failed','error':type(e).__name__}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:files=list(pool.map(one,sorted(urls)))
    atomic(ROOT/'wssd'/'downloads.json',files)
    complete=len(pages)==7 and all('receipt' in p for p in pages) and all(f['status']=='downloaded' for f in files)
    return {'status':'collected' if complete and files else 'partial' if files else 'failed',
            'source':TANKERS,'pages':pages,'listed_files':len(urls),'downloaded_files':sum(f['status']=='downloaded' for f in files),
            'manifest':str(ROOT/'wssd'/'downloads.json'),'limitations':'Published state district-level reports. Observation/report dates and geographic resolution require content checks; downloads do not establish village deliveries or tanker need.'}


def collect_pocra(refresh=False):
    """Collect public attributes and dated district weather, without old geometry."""
    base='https://gis.mahapocra.gov.in/webservices/'
    wfs='https://gis.mahapocra.gov.in/geoserver/PoCRA_Dashboard_V2/ows'
    requested=datetime.now(ZoneInfo('Asia/Kolkata')).date()
    from datetime import timedelta
    requested=(requested-timedelta(days=1)).isoformat()
    p,receipt=fetch(ROOT/'pocra'/'districts.json',base+'get_districts',refresh=refresh)
    districts=json.loads(p.read_bytes())['data']
    attributes=[];seen=set();total=None;offset=0
    while total is None or offset<total:
        if offset>=100000:raise ValueError('PoCRA village pagination exceeds reviewed bounds')
        params={'service':'WFS','version':'2.0.0','request':'GetFeature','typeNames':'PoCRA_Dashboard_V2:mh_villages',
            'outputFormat':'application/json','count':5000,'startIndex':offset,'sortBy':'id A',
            'propertyName':'id,vincode,vlname,dtname,thname,is_pocra,phase'}
        p,r=fetch(ROOT/'pocra'/f'village-attributes-{offset:05}.json',wfs,params=params,refresh=refresh)
        data=json.loads(p.read_bytes());matched=int(data['numberMatched'])
        if total is not None and total!=matched:raise ValueError('PoCRA village inventory changed during download')
        total=matched;features=data.get('features',[])
        if not features and offset<total:raise ValueError('Truncated PoCRA village page')
        for f in features:
            row=f['properties']
            if row['id'] in seen:raise ValueError('Duplicate paginated PoCRA village identity')
            seen.add(row['id']);attributes.append({**row,'retrieved_at':r['retrieved_at'],
                'source_url':r['url'],'observation_date':None,'geometry':None,'prediction_use':False})
        offset+=len(features)
    p=ROOT/'pocra'/'village-attributes.jsonl'
    with p.open('w',encoding='utf-8') as f:
        for row in attributes:f.write(json.dumps(row,ensure_ascii=True)+'\n')
    def one(district):
        code=int(district['dtncode']);out={'district':district['dtname'],'code':code,'weather':[],'dryspell':[],'errors':[]}
        for kind,endpoint in [('weather','fetch_district_weather_data_fifteen_days'),('dryspell','fetch_mh_dry_spell_selected_date')]:
            try:
                p,r=fetch(ROOT/'pocra'/f'{kind}-{code}-{requested}.json',base+endpoint,
                          params={'dtncode':code,'for_date':requested},refresh=refresh)
                data=json.loads(p.read_bytes());rows=data.get('weather_data' if kind=='weather' else 'data',[])
                if not isinstance(rows,list):raise ValueError('Unexpected district data response')
                for row in rows:
                    if kind=='weather' and not ('2021-01-01'<=row['for_date']<=requested):raise ValueError('Invalid weather observation date')
                out[kind]=[{**row,'district':district['dtname'],'district_code_as_reported':code,'requested_for_date':requested,
                    'source_url':r['url'],'retrieved_at':r['retrieved_at'],'basis':'publisher_district_weather' if kind=='weather' else 'publisher_dryspell_aggregation',
                    'observation_date_verified':kind=='weather','village_delivered_litres':None} for row in rows]
            except (httpx.HTTPError,ValueError,KeyError) as e:out['errors'].append({'kind':kind,'error':type(e).__name__,'detail':str(e)[:120]})
        return out
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(one,districts))
    summaries={};dates=[]
    for kind in ('weather','dryspell'):
        p=ROOT/'pocra'/(kind+'-district-context.jsonl');rows=[r for d in results for r in d[kind]]
        with p.open('w',encoding='utf-8') as f:
            for row in rows:f.write(json.dumps(row,ensure_ascii=True)+'\n')
        summaries[kind]={'rows':len(rows),'output':str(p)}
        if kind=='weather':dates=[r['for_date'] for r in rows]
    return {'source':'https://gis.mahapocra.gov.in/','status':'partial' if any(r['errors'] for r in results) else 'collected',
            'requested_for_date':requested,'districts':len(districts),'village_attributes':len(attributes),'village_attribute_total_matched':total,
            'weather':summaries['weather'],'dryspell':summaries['dryspell'],
            'weather_date_range':[min(dates,default=None),max(dates,default=None)],
            'errors':[{'district':r['district'],**e} for r in results for e in r['errors']],
            'limitations':'Weather is district context, not village supply. Dry-spell response lacks a valid-period field; request date alone does not establish freshness. Wind units and aggregation method unverified. Attribute codes/geometry vintage unverified; geometry excluded. No demographic, delivery or urgency labels inferred.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sources',nargs='+',choices=['jjm','pmc','wssd','pocra'],default=['jjm','pmc','wssd','pocra'])
    p.add_argument('--refresh',action='store_true');args=p.parse_args()
    ROOT.mkdir(parents=True,exist_ok=True)
    report=json.loads(REPORT.read_text(encoding='utf-8')) if REPORT.exists() else {'sources':{}}
    report.update(checked_at=stamp(),scope='Public source completion; operational training gaps remain explicit')
    for source in args.sources:
        print('Collecting '+source+' public records...',flush=True)
        try:result={'status':'collected',**{'jjm':collect_jjm,'pmc':collect_pmc,'wssd':collect_tankers,'pocra':collect_pocra}[source](args.refresh)}
        except (httpx.HTTPError,ValueError,KeyError,TypeError) as e:result={'status':'failed','error':type(e).__name__,'detail':str(e)[:200]}
        # Re-read after long downloads so an independently completed source is retained.
        report=json.loads(REPORT.read_text(encoding='utf-8')) if REPORT.exists() else report
        report['sources'][source]=result;report['checked_at']=stamp();atomic(REPORT,report)
        print(json.dumps({k:v for k,v in result.items() if k not in ['pages','districts','limitations']},ensure_ascii=True),flush=True)
    report['finished_at']=stamp();atomic(REPORT,report)


if __name__=='__main__':main()
