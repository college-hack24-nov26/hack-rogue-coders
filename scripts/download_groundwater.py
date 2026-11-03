"""Bounded, atomic download of the official historic NWIC telemetry resource."""
import hashlib,json,time
from pathlib import Path
import httpx

def main():
    catalogue='https://nwdp.nwic.gov.in/api/3/action/package_show?id=ground-water-level-telemetry-daily-maharashtra-gw'
    target=Path('data/raw/nwic-maharashtra-2021-2025.csv');target.parent.mkdir(parents=True,exist_ok=True)
    metadata=target.with_suffix('.metadata.json')
    if target.exists() and metadata.exists():
        saved=json.loads(metadata.read_text());digest=hashlib.sha256(target.read_bytes()).hexdigest()
        if digest==saved['sha256']:print(json.dumps({'status':'cached',**saved}));return
        raise ValueError('Existing historic source hash mismatch; preserve for review')
    started=time.perf_counter()
    with httpx.Client(timeout=60) as client:
        result=client.get(catalogue);result.raise_for_status()
        resources=result.json()['result']['resources']
        matches=[r for r in resources if '2021_2025.csv' in r['url']]
        if len(matches)!=1:raise ValueError('Historic resource identity requires review')
        resource=matches[0];url=resource['url']
        if not url.startswith('https://nwdp.nwic.gov.in/dataset/'):raise ValueError('Unexpected source host')
        count=0;digest=hashlib.sha256();partial=target.with_suffix('.csv.part');next_progress=32*1024*1024
        with client.stream('GET',url) as response:
            response.raise_for_status()
            with partial.open('wb') as stream:
                for chunk in response.iter_bytes(1024*1024):
                    count+=len(chunk)
                    if count>600*1024*1024:raise ValueError('Source exceeds reviewed download limit')
                    digest.update(chunk);stream.write(chunk)
                    if count>=next_progress:print(json.dumps({'downloaded_bytes':count}),flush=True);next_progress+=32*1024*1024
        partial.replace(target)
    report=dict(source=url,catalogue=catalogue,resource_name=resource['name'],bytes=count,sha256=digest.hexdigest(),download_seconds=time.perf_counter()-started)
    metadata.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
