"""Bounded official-source adapters. Preserve raw units/dates; empty feeds stay empty."""
import hashlib,json,re
from datetime import datetime,timezone
from html.parser import HTMLParser
import httpx
from sqlalchemy import select
from services.api.db import Record,Village,now,uid
from services.api.config import settings

class TextParser(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ['script','style']:self.hidden+=1
    def handle_endtag(self,tag):
        if tag in ['script','style']:self.hidden=max(0,self.hidden-1)
    def handle_data(self,data):
        if not self.hidden and data.strip():self.parts.append(data.strip())
class TableParser(HTMLParser):
    def __init__(self):super().__init__();self.rows=[];self.row=[];self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='tr':self.row=[]
        if tag in ['td','th']:self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ['td','th'] and self.cell is not None:self.row.append(' '.join(' '.join(self.cell).split()));self.cell=None
        if tag=='tr' and self.row:self.rows.append(self.row)
def persist(db,kind,key,payload):
    old=db.scalar(select(Record).where(Record.kind==kind,Record.key==key).order_by(Record.version.desc()).limit(1))
    if old and old.payload==payload:return old
    r=Record(kind=kind,key=key,version=old.version+1 if old else 1,payload=payload);db.add(r);return r
def snapshot(db,source,response,status,records=0):
    db.add(Record(kind='source_fetch',key=uid(),payload={'source':source,'retrieved_at':now(),'http_status':response.status_code,'status':status,'records':records,'sha256':hashlib.sha256(response.content).hexdigest(),'bytes':len(response.content),'raw_sample':response.text[:6000]}))

def schemes(db,payload):
    count=0;results=[]
    with httpx.Client(timeout=30,follow_redirects=False) as client:
        for url in ['https://mahadbt.maharashtra.gov.in/Farmer/AgriLogin/AgriLogin','https://gsda.maharashtra.gov.in/en-important-government-resolutions/']:
            try:r=client.get(url)
            except httpx.HTTPError as error:
                result={'source':url,'status':'failed','retrieved_at':now(),'error_class':type(error).__name__}
                db.add(Record(kind='source_fetch',key=uid(),payload=result));results.append(result);continue
            if r.status_code!=200:snapshot(db,url,r,'unavailable');results.append({'source':url,'status':'unavailable'});continue
            if len(r.content)>4000000:snapshot(db,url,r,'exceeds_ingestion_limit');results.append({'source':url,'status':'exceeds_ingestion_limit'});continue
            parser=TextParser();parser.feed(r.text);text=' '.join(parser.parts)
            if len(text)<100:snapshot(db,url,r,'no_extractable_evidence');results.append({'source':url,'status':'no_extractable_evidence'});continue
            persist(db,'document',hashlib.sha256(url.encode()).hexdigest(),{'source':url,'source_date':now(),'publication_date':None,'passage':text[:20000],'content_sha256':hashlib.sha256(text.encode()).hexdigest(),'retrieval_method':'official_html_text','applicability_reviewed':False,'eligibility_verified':False});count+=1;snapshot(db,url,r,'retrieved',1);results.append({'source':url,'status':'retrieved'})
    return {'status':'completed' if count==2 else 'partial' if count else 'unavailable','documents':count,'eligibility_verified':False,'sources':results}

def agmarknet(db,payload):
    if not settings.agmarknet_api_key:return {'status':'blocked','reason':'AGMARKNET API key unavailable'}
    url='https://api.data.gov.in/resource/'+settings.agmarknet_resource_id
    with httpx.Client(timeout=30) as client:r=client.get(url,params={'api-key':settings.agmarknet_api_key,'format':'json','filters[state]':'Maharashtra','limit':1000})
    r.raise_for_status();data=r.json();count=0
    for row in data.get('records',[]):
        required={'market','commodity','variety','arrival_date','min_price','max_price','modal_price'}
        if not required.issubset(row):continue
        day=datetime.strptime(row['arrival_date'],'%d/%m/%Y').date().isoformat()
        quote={'source':'https://www.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi','source_date':day,'market':row['market'],'commodity':row['commodity'],'variety':row['variety'],'units':'INR/quintal','price':float(row['modal_price']),'min_price':float(row['min_price']),'max_price':float(row['max_price']),'original':row}
        key=hashlib.sha256(json.dumps([quote[k] for k in ['market','commodity','variety','source_date']]).encode()).hexdigest();persist(db,'market',key,quote);count+=1
    # Never retain provider request URLs containing an API key.
    snapshot(db,'AGMARKNET official data.gov.in resource',r,'retrieved',count);return {'status':'completed','quotes':count}

def msamb(db,payload):
    code=payload.get('commodity_code')
    if not code:return {'status':'blocked','reason':'Select an official commodity code; broad unbounded scraping is disabled'}
    if not re.fullmatch(r'\d{5}',code):raise ValueError('Invalid commodity code')
    url='https://www.msamb.com/ApmcDetail/GetArrivalPriceInfoByCommodityWise'
    with httpx.Client(timeout=30) as client:r=client.get(url,params={'commodityCode':code,'apmcCode':''},headers={'Accept-Language':'en-IN','X-Requested-With':'XMLHttpRequest','Referer':'https://www.msamb.com/ApmcDetail/APMCPriceInformation'})
    r.raise_for_status();parser=TableParser();parser.feed(r.text)
    # Parse only explicit, recognized labels. Unknown layouts require review rather than guessing units.
    header=next((row for row in parser.rows if any('market' in x.lower() or 'बाजार' in x for x in row) and any('unit' in x.lower() or 'एकक' in x or 'परिमाण' in x for x in row)),None);count=0
    if header:
        labels=[s.lower() for s in header]
        def column(*names):return next((i for i,s in enumerate(labels) if any(n in s for n in names)),None)
        positions={k:column(*names) for k,names in {'market':['market','बाजार समिती'],'variety':['variety','जात'],'date':['date','दिनांक'],'units':['unit','एकक','परिमाण'],'price':['modal','average','सर्वसाधारण','सरासरी']}.items()}
        if all(v is not None for v in positions.values()):
            for row in parser.rows:
                if len(row)<=max(positions.values()) or row==header:continue
                try:
                    original={k:row[i] for k,i in positions.items()};price=float(original['price'].replace(',',''));day=datetime.strptime(original['date'],'%d/%m/%Y').date().isoformat()
                except ValueError:continue
                quote={'source':'https://www.msamb.com/ApmcDetail/APMCPriceInformation','source_date':day,'market':original['market'],'commodity':code,'variety':original['variety'],'units':original['units'],'price':price,'original':original}
                persist(db,'market',hashlib.sha256(json.dumps(original,sort_keys=True).encode()).hexdigest(),quote);count+=1
    snapshot(db,'MSAMB commodity '+code,r,'retrieved' if count else 'empty_or_layout_unverified',count)
    return {'status':'completed','quotes':count,'availability':'available' if count else 'unavailable','reason':None if count else 'No dated quote with verified units could be parsed'}

def villages(db,payload):
    from .directory import ENDPOINT,SOURCE,validate_rows
    code=str(payload.get('district_code') or '')
    if not re.fullmatch(r'\d{3}',code):raise ValueError('Select an explicit official district code')
    with httpx.Client(timeout=30) as client:r=client.post(ENDPOINT,data={'distcode':code})
    r.raise_for_status();records=r.json();count=0
    # An empty district remains an explicit no-record result; statewide operator
    # imports additionally reconcile each district with the source catalogue.
    if records==[]:snapshot(db,ENDPOINT,r,'empty_source_response');return {'status':'completed','villages':0,'district_code':code,'availability':'no_source_records'}
    for key,row in validate_rows(records,code).items():
        name=row['tlgdnameenglish'];district=row['tlgddistrict'];taluka=row['tlgdTaluka']
        existing=db.get(Village,key)
        if existing:
            if existing.jurisdiction!='district:'+str(district):raise ValueError('Existing village jurisdiction conflict requires review')
            continue
        db.add(Village(id=key,name=name,district=row.get('distname',str(district)),taluka=row.get('talukaname',str(taluka)),jurisdiction='district:'+str(district),provenance={'source':SOURCE,'endpoint':ENDPOINT,'retrieved_at':now(),'raw':row,'census_2011_code':row.get('vc2011_code'),'lgd_taluka_code':taluka}));count+=1
    snapshot(db,ENDPOINT,r,'retrieved',count);return {'status':'completed','villages':count,'district_code':code,'source_records':len(records)}
