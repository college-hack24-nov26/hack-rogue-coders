"""Resumable directory import: strict identity checks, retries, per-district commits."""
import argparse, asyncio, hashlib, json, re, time
from datetime import datetime, timezone
from pathlib import Path
import httpx
from sqlalchemy import insert, select
from services.api.db import Session, Village, Record, now, uid
from services.worker.sources import TableParser
from services.worker.directory import SOURCE, ENDPOINT, validate_rows


def atomic_json(path, payload):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)

def import_rows(code, rows, digest, retrieved_at, expected=None, district_name=None):
    unique=validate_rows(rows,code,expected)
    with Session() as db:
        existing=dict(db.execute(select(Village.id,Village.jurisdiction)).all());values=[]
        for key,row in unique.items():
            if key in existing:
                if existing[key]!='district:'+code:raise ValueError('Existing village belongs to a different jurisdiction; reviewed migration required')
                continue
            values.append(dict(id=key,name=row['tlgdnameenglish'].strip(),district=row.get('distname',district_name or code),taluka=row.get('talukaname',row['tlgdTaluka']),jurisdiction='district:'+code,provenance={'source':SOURCE,'endpoint':ENDPOINT if 'source_api_raw' in row else 'https://mahavillages.mahabhumi.gov.in/all_list_back.php','retrieved_at':retrieved_at,'district_snapshot_sha256':digest,'raw':row,'census_2011_code':row.get('vc2011_code'),'lgd_taluka_code':row['tlgdTaluka']}))
        if values:db.execute(insert(Village),values)
        db.commit()
    return len(values),len(unique)

async def run(args):
    root=Path(args.cache);root.mkdir(parents=True,exist_ok=True)
    report=Path(args.report);report.parent.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter();results={}
    try:previous={item['district']:item for item in json.loads(report.read_text(encoding='utf-8'))['districts']}
    except (OSError,ValueError,KeyError):previous={}
    async with httpx.AsyncClient(timeout=args.timeout) as client:
        response=await client.get(SOURCE);response.raise_for_status()
    codes=sorted(set(re.findall(r'class="talukalist" id="(\d+)"',response.text)))
    if not codes:raise ValueError('No district IDs found in official catalogue')
    table=TableParser();table.feed(response.text)
    catalogue={row[1]:{'name':row[2],'expected':int(row[7]) if row[7].isdigit() else 0} for row in table.rows if len(row)==8 and row[1] in codes}
    if set(catalogue)!=set(codes):raise ValueError('Unrecognized district count table')
    if args.district:
        if any(code not in codes for code in args.district):raise ValueError('District absent from catalogue')
        codes=args.district
    (root/'catalogue.html').write_bytes(response.content);catalogue_at=now()
    semaphore=asyncio.Semaphore(args.concurrency)
    def checkpoint():
        manifest={'source':SOURCE,'documented_api':ENDPOINT,'api_documentation':'https://mahavillages.mahabhumi.gov.in/pdf/LGD%20WebServices.pdf','retrieved_at':catalogue_at,'catalogue_sha256':hashlib.sha256(response.content).hexdigest(),'catalogue_villages':sum(catalogue[c]['expected'] for c in codes),'districts':[results[c] for c in codes if c in results],'requested_districts':len(codes),'completed_districts':len(results),'imported_new_villages':sum(r.get('imported_new',0) for r in results.values()),'total_source_rows':sum(r.get('records',0) for r in results.values()),'unique_source_villages':sum(r.get('unique_villages',0) for r in results.values()),'seconds':time.perf_counter()-started,'coverage':'all_source_districts' if len(results)==len(codes) and not args.district and all(r['status']!='unavailable' for r in results.values()) else 'partial','coordinates':'not provided by this source; never inferred from station names'}
        atomic_json(report,manifest);return manifest
    async def one(code):
        file=root/(code+'.json')
        async with semaphore:
            rows=None;attempts=[];status='cached'
            if file.exists() and not args.refresh:
                try:rows=json.loads(file.read_text(encoding='utf-8'));validate_rows(rows,code,catalogue[code]['expected'])
                except (ValueError,KeyError,TypeError):rows=None
            retrieved_at=previous.get(code,{}).get('retrieved_at') or (datetime.fromtimestamp(file.stat().st_mtime,timezone.utc).isoformat() if rows else None)
            if rows is None:
                for attempt in range(1,args.attempts+1):
                    try:
                        # Reconnect after timeout rather than stranding the queue
                        # on a shared failed connection. Only read-only queries.
                        async with httpx.AsyncClient(timeout=args.timeout) as client:
                            r=await client.post(ENDPOINT,data={'distcode':code})
                        r.raise_for_status();candidate=r.json();validate_rows(candidate,code,catalogue[code]['expected'])
                        rows=candidate;retrieved_at=now();status='downloaded';atomic_json(file,rows)
                        attempts.append({'attempt':attempt,'status':'success'});break
                    except (httpx.HTTPError,ValueError,KeyError,TypeError) as e:
                        attempts.append({'attempt':attempt,'error_class':type(e).__name__})
                        if attempt<args.attempts:await asyncio.sleep(min(2**(attempt-1),8))
            if rows is None:result={'district':code,'status':'unavailable','attempts':attempts}
            else:
                digest=hashlib.sha256(file.read_bytes()).hexdigest();imported,unique=import_rows(code,rows,digest,retrieved_at,catalogue[code]['expected'],catalogue[code]['name'])
                result={'district':code,'district_name':catalogue[code]['name'],'status':status,'records':len(rows),'unique_villages':unique,'catalogue_villages':catalogue[code]['expected'],'duplicate_rows':len(rows)-unique,'imported_new':imported,'sha256':digest,'retrieved_at':retrieved_at,'attempts':attempts}
            results[code]=result;checkpoint();print(json.dumps(result,ensure_ascii=True),flush=True)
    await asyncio.gather(*(one(code) for code in codes))
    manifest=checkpoint()
    with Session() as db:
        manifest['database_villages']=len(db.scalars(select(Village.id)).all())
        db.add(Record(kind='registry_import',key=uid(),payload=manifest));db.commit()
    atomic_json(report,manifest);print(json.dumps({k:v for k,v in manifest.items() if k!='districts'},indent=2),flush=True)
    return manifest

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cache',default='data/raw/lgd');parser.add_argument('--report',default='docs/LIVE_DIRECTORY_IMPORT.json')
    parser.add_argument('--district',nargs='+');parser.add_argument('--timeout',type=float,default=25)
    parser.add_argument('--attempts',type=int,default=3);parser.add_argument('--concurrency',type=int,default=2);parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args()
    if not (1<=args.concurrency<=3 and 1<=args.attempts<=5 and 1<=args.timeout<=60):parser.error('Use concurrency 1-3, attempts 1-5, timeout 1-60s')
    asyncio.run(run(args))
if __name__=='__main__':main()
