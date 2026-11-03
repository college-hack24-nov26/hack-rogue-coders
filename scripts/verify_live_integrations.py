import asyncio,json
from pathlib import Path
from services.api.db import Session,Record,uid,now
from services.api.config import settings
from services.api.readiness import configuration_status
from services.api.integrations import fetch_weather
from services.worker.sources import schemes,msamb,persist
async def main():
    configuration=configuration_status(settings)
    results={'verified_at':now(),**{name:value['status'] for name,value in configuration['providers'].items()},'missing_configuration':{name:value['missing_env'] for name,value in configuration['providers'].items() if value['missing_env']},'external_messages_sent':0}
    with Session() as db:
        try:
            weather=await fetch_weather(20.4,76.8);persist(db,'weather','20.4:76.8',weather);db.add(Record(kind='source_fetch',key=uid(),payload={'source':'Open-Meteo','status':'verified_live_fetch','retrieved_at':now(),'units':weather['units'],'source_grid':[weather['latitude'],weather['longitude']],'source_dates':weather['daily']['time']}));results['weather']={'status':'live_fetch_verified','grid':[weather['latitude'],weather['longitude']],'days':len(weather['daily']['time']),'village_assignment':None};db.commit()
        except Exception as e:db.rollback();results['weather']={'status':'failed','error_class':type(e).__name__}
        for name,fn,payload in [('schemes',schemes,{}),('msamb',msamb,{'commodity_code':'08035'})]:
            try:results[name]=fn(db,payload);db.commit()
            except Exception as e:
                db.rollback();results[name]={'status':'failed','error_class':type(e).__name__};db.add(Record(kind='source_fetch',key=uid(),payload={'source':name,'status':'failed','retrieved_at':now(),'error_class':type(e).__name__}));db.commit()
        results['groundwater_models']=[]
        for file,folder in [('REAL_MODEL_EVALUATION.json','nwic-research'),('RESIDUAL_MODEL_EVALUATION.json','nwic-residual'),('MULTIYEAR_MODEL_EVALUATION.json','nwic-multiyear'),('SEASONAL_MODEL_EVALUATION.json','nwic-seasonal')]:
            report_file=Path('docs')/file
            if not report_file.exists():continue
            report=json.loads(report_file.read_text(encoding='utf-8'));report['artifact']=folder+'/model.json';report['approved']=False
            persist(db,'model',folder+'-'+report['sha256'][:12],report);db.commit()
            result={'status':'trained_and_evaluated_withheld','gates':report['gates'],'report':file}
            results['groundwater_models'].append(result);results['groundwater_model']=result
    Path('docs/LIVE_INTEGRATIONS.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print(json.dumps(results,indent=2))
if __name__=='__main__':asyncio.run(main())
