"""Disposable synthetic registry throughput, not production inference or real observations."""
import json
import tempfile
import time
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from services.api.db import Base,Village
from services.worker.main import daily_inference

def main():
    results=[]
    for count in [1000,50000]:
        with tempfile.TemporaryDirectory() as folder:
            engine=create_engine('sqlite:///'+str(Path(folder)/'benchmark.db'))
            Base.metadata.create_all(engine)
            with Session(engine) as db:
                for i in range(count):db.add(Village(id='TEST-BENCH-'+str(i),name='SYNTHETIC FIXTURE',district='TEST',taluka='TEST',jurisdiction='TEST',provenance={'fixture':True}))
                db.commit();started=time.perf_counter();result=daily_inference(db,{'date':'TEST-RUN'});write=time.perf_counter();db.commit();end=time.perf_counter()
            engine.dispose()
            results.append({'records':count,'workload':'synthetic unavailable-snapshot publication','download_seconds':None,'feature_seconds':None,'model_inference_seconds':None,'process_and_flush_seconds':write-started,'commit_seconds':end-write,'total_seconds':end-started,'result':result})
    Path('docs/BENCHMARK.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(results,indent=2))
if __name__=='__main__':main()
