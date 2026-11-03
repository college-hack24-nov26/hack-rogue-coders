"""Village supply sufficiency is a water balance, never groundwater depth."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .auth import current
from .db import User, session

router = APIRouter(prefix='/api/v1')
SECTORS = {'household', 'agriculture', 'livestock', 'other'}


def summarize(data, issue):
    components = data['components']
    missing = sorted(SECTORS - set(data['sectors_covered']))
    gaps = []
    if missing:gaps.append('Missing current demand for: ' + ', '.join(missing) + '. Record reviewed zero demand explicitly when a sector does not apply.')
    if any(c['unmet_litres'] is None for c in components):gaps.append('Current source-backed supply, storage and delivery limits are missing for one or more sectors.')
    if components and not all(c.get('storage_partition_verified') is True for c in components):gaps.append('Confirm sector storage allocations do not count the same stored water more than once.')
    if components and not all(c.get('net_supply_after_losses') is True for c in components):gaps.append('Confirm planned inflows are usable supply after treatment and conveyance losses.')
    ready = not gaps and bool(components)
    daily = []
    if components and all(c['unmet_litres'] is not None for c in components):
        for i in range(data['days']):
            row = {'date': (issue + timedelta(days=i+1)).isoformat()}
            for name in ['demand_litres','inflow_litres','delivered_litres','unmet_litres','closing_litres','overflow_litres']:
                row[name] = sum(c['days'][i].get(name,0) for c in components)
            daily.append(row)
    first = next((d['date'] for d in daily if d['unmet_litres'] > 0),None)
    shortage = sum(d['unmet_litres'] for d in daily) if ready else None
    return {'days':data['days'],'status':'reviewed_scenario' if ready else 'insufficient_data',
            'verdict':('not_enough' if shortage > 0 else 'enough') if ready else 'insufficient_data',
            'enough':shortage == 0 if ready else None,'shortage_litres':shortage,
            'first_shortage_date':first if ready else None,
            'demand_litres':sum(c['demand_litres'] for c in components) if not missing else None,
            'opening_storage_litres':sum(c['opening_storage_litres'] or 0 for c in components) if ready else None,
            'planned_net_inflow_litres':sum(d['inflow_litres'] for d in daily) if ready else None,
            'closing_storage_litres':daily[-1]['closing_litres'] if ready and daily else None,
            'sectors_covered':data['sectors_covered'],'missing_inputs':gaps,
            'daily':daily if ready else [],'evidence':components}


@router.get('/villages/{key}/supply-outlook')
def supply_outlook(key:str,u:User=Depends(current),db:Session=Depends(session)):
    from .main import village,baseline_data
    v = village(db,key)
    issue = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    return {'village_id':key,'village_name':v.name,'issued_on':issue.isoformat(),
            'target':'water_supply_sufficiency','units':'litres','scope':'whole_village_all_four_sectors',
            'method':'daily_water_balance_of_reviewed_inputs','model_trained':False,
            'outlooks':[summarize(baseline_data(db,key,n),issue) for n in (7,15)],
            'assumptions':['Daily demand and net supply remain constant at reviewed rates through each horizon.',
                'Opening usable storage is assumed available at the start of the first projected day.',
                'Allocated water must be suitable for its assigned use; historical quality samples do not certify current drinking-water safety.',
                'Storage is allocated once between sectors; spare allocations are not automatically transferred between sectors.',
                'Daily inflow serves that day’s demand subject to delivery limits; remaining water is stored up to capacity and excess is overflow.',
                'Daily totals do not resolve hourly outages, pressure or delivery timing.',
                'This is a conditional supply scenario, not a validated machine-learning shortage forecast.',
                'Groundwater depth, river proximity and pipe geometry are not converted into deliverable litres.']}
