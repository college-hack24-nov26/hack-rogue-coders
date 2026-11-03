from datetime import date,timedelta
from .calculations import irrigation

def weather_grid(latitude,longitude):
    if latitude is None or longitude is None:return None
    # Explicit shared request cells; source response retains the actual provider grid position.
    return f'{round(latitude,1):.1f}:{round(longitude,1):.1f}'

def farm_plan(farm,weather,agronomy,days,issue_date):
    if agronomy.get('reviewed') is not True:raise ValueError('Agronomy coefficients require review')
    if weather.get('units',{}).get('et0_fao_evapotranspiration')!='mm' or weather.get('units',{}).get('precipitation_sum')!='mm':raise ValueError('Incompatible weather units')
    daily=weather['daily'];indices={d:i for i,d in enumerate(daily['time'])}
    efficiency=agronomy['efficiencies'][farm['irrigation_method']]
    rain_factor=agronomy['effective_rain_factor']
    if not 0<=rain_factor<=1:raise ValueError('Invalid reviewed rainfall assumption')
    sowing=date.fromisoformat(farm['sowing_date']);result=[]
    for horizon in range(1,days+1):
        day=issue_date+timedelta(days=horizon);key=day.isoformat()
        if key not in indices:raise ValueError('Weather does not cover the requested horizon')
        stage=next((s for s in agronomy['stages'] if s['start_day']<=(day-sowing).days<=s['end_day']),None)
        if not stage:raise ValueError('Crop stage unsupported by reviewed coefficients')
        index=indices[key];et0=daily['et0_fao_evapotranspiration'][index];rain=daily['precipitation_sum'][index]
        if et0 is None or rain is None:raise ValueError('Missing weather value')
        values=irrigation(farm['area_ha'],et0,stage['kc'],rain*rain_factor,efficiency)
        result.append({'date':key,'crop_stage':stage['name'],'kc':stage['kc'],'et0_mm':et0,'effective_rain_mm':rain*rain_factor,**values})
    return {'status':'estimated_requirement','days':days,'daily':result,'total_litres':sum(r['requirement_litres'] for r in result),'units':'litres','soil_assumption':'Unmeasured soil contribution omitted (0 mm)','rain_assumption':f'Effective rain = forecast rain × reviewed factor {rain_factor}','efficiency':efficiency,'supply_litres':None,'allocation_litres':None,'limitations':'Crop demand is not proof of available or permitted water. Weather is grid-level forecast evidence.'}
