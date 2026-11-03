"""Research throughput on real source feature rows, not claims of 50,000-village coverage."""
import argparse,hashlib,json,time,tempfile
from pathlib import Path
import numpy as np
from xgboost import XGBRegressor
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from services.api.db import Base,Record
from services.worker.model import predict_levels
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model-root',type=Path,default=Path('artifacts/nwic-research'));parser.add_argument('--features',type=Path);parser.add_argument('--report',type=Path,default=Path('docs/REAL_INFERENCE_BENCHMARK.json'));args=parser.parse_args()
    root=args.model_root;manifest=json.loads((root/'evaluation.json').read_text(encoding='utf-8'))
    if hashlib.sha256((root/'model.json').read_bytes()).hexdigest()!=manifest['sha256']:raise ValueError('Artifact hash mismatch')
    start=time.perf_counter();features=np.load(args.features or root/'benchmark_features.npz',allow_pickle=False)['X'];feature_load=time.perf_counter()-start
    start=time.perf_counter();model=XGBRegressor();model.load_model(root/'model.json');load=time.perf_counter()-start;results=[]
    for n in [1000,50000]:
        if len(features)<n:raise ValueError('Insufficient real feature rows; never pad or invent observations')
        started=time.perf_counter();batches=[]
        for i in range(0,n,500):batches.append(predict_levels(model,features[i:min(n,i+500)],manifest))
        predicted=np.concatenate(batches);inference=time.perf_counter()-started
        with tempfile.TemporaryDirectory() as folder:
            engine=create_engine('sqlite:///'+str(Path(folder)/'research.db'));Base.metadata.create_all(engine);write=time.perf_counter()
            with Session(engine) as db:
                db.bulk_save_objects([Record(kind='research_benchmark',key=str(i),payload={'source_feature_row':i,'horizons':row.tolist(),'operational':False}) for i,row in enumerate(predicted)]);db.commit()
            write_seconds=time.perf_counter()-write;engine.dispose()
        results.append({'model_sha256':manifest['sha256'],'real_feature_rows':n,'geography':'historical station/date feature rows, NOT distinct villages','download_seconds':None,'feature_cache_load_seconds':feature_load,'model_load_seconds':load,'inference_seconds':inference,'write_seconds':write_seconds,'total_seconds':feature_load+load+inference+write_seconds,'published_operational_forecasts':0,'note':'Research candidate remains unapproved; outputs written only to a temporary research database'})
    args.report.write_text(json.dumps(results,indent=2),encoding='utf-8');print(json.dumps(results,indent=2))
if __name__=='__main__':main()
