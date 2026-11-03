from datetime import date,timedelta
import pytest
from services.api.planning import farm_plan

def test_reviewed_plan_units_and_horizons():
    issue=date(2026,10,30)
    farm={'area_ha':1,'sowing_date':'2026-10-01','irrigation_method':'drip'}
    weather={'units':{'et0_fao_evapotranspiration':'mm','precipitation_sum':'mm'},'daily':{'time':[(issue+timedelta(days=h)).isoformat() for h in range(1,16)],'et0_fao_evapotranspiration':[5]*15,'precipitation_sum':[2]*15}}
    agronomy={'reviewed':True,'efficiencies':{'drip':.8},'effective_rain_factor':.5,'stages':[{'start_day':0,'end_day':200,'name':'TEST FIXTURE stage','kc':1}]}
    assert farm_plan(farm,weather,agronomy,7,issue)['total_litres']==350000
    assert farm_plan(farm,weather,agronomy,15,issue)['total_litres']==750000
    agronomy['reviewed']=False
    with pytest.raises(ValueError):farm_plan(farm,weather,agronomy,7,issue)
