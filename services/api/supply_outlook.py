"""Village supply sufficiency is a water balance, never groundwater depth."""
import json
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from .auth import current, require, scoped
from .config import settings
from .db import Record, User, Village, session
from services.worker.village_supply_predictions import LEVELS, SCENARIO_METADATA, SNAPSHOT

router = APIRouter(prefix='/api/v1')
SECTORS = {'household', 'agriculture', 'livestock', 'other'}
STAFF = {'admin', 'system_admin', 'official'}


@lru_cache(maxsize=2)
def read_snapshot(path, revision):
    payload = json.loads(path.read_text(encoding='utf-8'))
    if (payload.get('schema') != 1 or not isinstance(payload.get('villages'), dict)
            or not isinstance(payload.get('generated_at'), str) or not isinstance(payload.get('model_run'), str)):
        raise ValueError('Invalid scenario snapshot')
    return payload


def scenario_snapshot():
    path = Path(settings.model_artifact_root) / SNAPSHOT
    try:
        stat = path.stat()
        return read_snapshot(path, (stat.st_mtime_ns, stat.st_size))
    except (OSError, ValueError, AttributeError):
        return {'generated_at': None, 'model_run': None, 'villages': {}}


def scenario_for(snapshot, key):
    return snapshot['villages'].get(key, {'scenarios': {}, 'missing_inputs': ['Scenario estimate unavailable for this village']})


@router.get('/supply-predictions')
def supply_predictions(
    days: int = 7,
    scenario: Literal['tight_supply', 'lower_supply'] = 'tight_supply',
    view: Literal['all', 'reviewed_shortage', 'scenario_shortage', 'insufficient_data'] = 'all',
    district: str = Query('', max_length=200),
    q: str = Query('', max_length=200),
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    u: User = Depends(current),
    db: Session = Depends(session),
):
    from .main import baseline_data

    require(u, STAFF)
    if days not in (7, 15):
        raise HTTPException(422, 'Choose a 7-day or 15-day horizon')
    issue = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    snapshot = scenario_snapshot()
    statement = select(Village.id, Village.name, Village.district, Village.taluka)
    if u.role != 'system_admin':
        statement = statement.where(Village.jurisdiction.in_(u.jurisdictions))
    registry = list(db.execute(statement))
    districts = sorted({row.district for row in registry})
    query = q.strip().casefold()
    villages = [row for row in registry if (not district or row.district == district) and (
        not query or any(query in str(value).casefold() for value in row))]
    keys = {row.id for row in villages}

    # Use the same versioned balances as the village details, without queries per village.
    records = {}
    for record in db.scalars(select(Record).where(Record.kind.in_(['supply', 'baseline', 'supply_source']))
                             .order_by(Record.version.desc())):
        if record.kind == 'supply_source' or record.key.rsplit(':', 1)[0] in keys:
            records.setdefault((record.kind, record.key), record)

    counts = dict(villages=len(villages), scenario_scored=0, scenario_shortage=0,
                  reviewed_shortage=0, reviewed_enough=0, missing_reviewed_inputs=0, missing_scenario_inputs=0)
    results = []
    for village in villages:
        estimate = scenario_for(snapshot, village.id)
        level = estimate['scenarios'].get(scenario, {}).get(str(days))
        counts['scenario_scored' if level is not None else 'missing_scenario_inputs'] += 1
        if level is not None and level >= 2:
            counts['scenario_shortage'] += 1
        reviewed = {'verdict': 'insufficient_data', 'shortage_litres': None}
        if all((kind, f'{village.id}:{sector}') in records for kind in ('baseline', 'supply') for sector in SECTORS):
            balance = summarize(baseline_data(db, village.id, days, records=records, issue=issue), issue)
            reviewed = {key: balance[key] for key in ('verdict', 'shortage_litres', 'first_shortage_date')}
        bucket = {'not_enough': 'reviewed_shortage', 'enough': 'reviewed_enough', 'insufficient_data': 'missing_reviewed_inputs'}
        counts[bucket[reviewed['verdict']]] += 1
        if (view == 'reviewed_shortage' and reviewed['verdict'] != 'not_enough'
                or view == 'scenario_shortage' and (level is None or level < 2)
                or view == 'insufficient_data' and reviewed['verdict'] != 'insufficient_data'):
            continue
        results.append({**village._asdict(), 'reviewed': reviewed, 'scenario_level': level,
                        'scenario_label': LEVELS.get(level), 'reference_date': estimate.get('reference_date'),
                        'household_basis': estimate.get('household_basis'), 'missing_scenario_inputs': estimate.get('missing_inputs', [])})
    results.sort(key=lambda row: (row['reviewed']['verdict'] != 'not_enough',
                -(row['reviewed']['shortage_litres'] or 0),
                -(row['scenario_level'] if row['scenario_level'] is not None else -1), row['name'].casefold(), row['id']))
    return {'days': days, 'scenario': scenario, 'scenarios': SCENARIO_METADATA, 'issued_on': issue.isoformat(),
            'scenario_generated_at': snapshot['generated_at'], 'scenario_model_run': snapshot['model_run'],
            'counts': counts, 'districts': districts, 'total': len(results), 'rows': results[offset:offset+limit]}


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
    prototype = None
    if u.role in STAFF and scoped(u, v.jurisdiction):
        snapshot = scenario_snapshot()
        prototype = {**scenario_for(snapshot, key), 'assumptions': SCENARIO_METADATA,
                     'generated_at': snapshot['generated_at'], 'model_run': snapshot['model_run']}
    return {'village_id':key,'village_name':v.name,'issued_on':issue.isoformat(),
            'target':'water_supply_sufficiency','units':'litres','scope':'whole_village_all_four_sectors',
            'method':'daily_water_balance_of_reviewed_inputs','model_trained':False,
            'prototype':prototype,
            'outlooks':[summarize(baseline_data(db,key,n),issue) for n in (7,15)],
            'assumptions':['Daily demand and net supply remain constant at reviewed rates through each horizon.',
                'Opening usable storage is assumed available at the start of the first projected day.',
                'Allocated water must be suitable for its assigned use; historical quality samples do not certify current drinking-water safety.',
                'Storage is allocated once between sectors; spare allocations are not automatically transferred between sectors.',
                'Daily inflow serves that day’s demand subject to delivery limits; remaining water is stored up to capacity and excess is overflow.',
                'Daily totals do not resolve hourly outages, pressure or delivery timing.',
                'This is a conditional supply scenario, not a validated machine-learning shortage forecast.',
                'Groundwater depth, river proximity and pipe geometry are not converted into deliverable litres.']}
