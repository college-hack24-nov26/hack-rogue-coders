"""Fetch public supply evidence and build dated surface-flow context features.

No database writes, private API access or village delivery inference. Cached
2021+ archives stay separate from current-year holdout/context observations.
"""
import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

from scripts.sync_water_data import atomic, read_date

ROOT = Path('data/raw/supply')
OUT = Path('data/water/supply-evidence.json')
IOT = 'https://ejalshakti.gov.in/jjmreport/Iot/IoTMonitoring.aspx/BindIotVillageList'
SURVEY = 'https://jaljeevanmission.gov.in/sites/default/files/2025-12/FHTC_Maharashtra_State%20Report.pdf'
REVIEWED_SURVEY_SHA256 = 'a9bde2ade9bccaa1714684ee652d834d5c2b21bd83259ca07ae321cb7638e66a'
EXTRA_READS = [
    ('jjm-root-records', 'https://ejalshakti.gov.in/jjmreport/IoTMonitoring.aspx/BindDistrictMap',
     {'cat':'11','subcat':'11','param':'11','stcode':'11'}),
    ('neeri-sensors', 'https://hargharnal.neeri.res.in/xsensor_list', None),
    ('janori-sources', 'https://ejalshakti.gov.in/jjmreport/JJMVillage_Profile.aspx/BindSourceInfo',
     {'stcode':'381','dtcode':'6271','cat':'11','subcat':'11','param':'11','VillageId':'11113419371'}),
    ('janori-schemes', 'https://ejalshakti.gov.in/jjmreport/JJMVillage_Profile.aspx/BindSchemeInfo',
     {'stcode':'381','dtcode':'6271','cat':'11','subcat':'11','param':'11','VillageId':'11113419371'}),
    ('janori-getLPCD_WaterSuppliedDetails', 'https://ejalshakti.gov.in/jjmreport/Iot/IoTVillage_Location.aspx/getLPCD_WaterSuppliedDetails',
     {'StateId':'1291','VillageId':'11113419371'}),
    ('janori-BindDevice_data', 'https://ejalshakti.gov.in/jjmreport/Iot/IoTVillage_Location.aspx/BindDevice_data',
     {'StateId':'1291','VillageId':'11113419371'}),
]
FLOW_IDS = [
    'd39ff877-27f6-44ca-9e05-911a677b3ba3', 'ceec5178-3da1-41ec-bbbc-e4e496e08df9',
    '101987dd-7bcc-4f6d-9118-9bfed0c7e414', 'a6722e4b-6a61-49d3-afe7-50656a78f9bc',
    '9c659865-ab21-4ffa-a3f9-edbae14f5c86', '65e0ff3a-2b79-4e0b-b1ad-c2977cda9d09',
]
CFS_TO_CMS = 0.028316846592  # International foot = exactly 0.3048 m.


def stamp():
    return datetime.now(timezone.utc).isoformat()


def retrieve(client, path, url, *, payload=None, maximum=20_000_000):
    """Bounded, atomic download. A failed fetch cannot replace a valid snapshot."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.part')
    sha, size = hashlib.sha256(), 0
    try:
        with client.stream('POST' if payload is not None else 'GET', url, json=payload) as response:
            response.raise_for_status()
            with temporary.open('wb') as handle:
                for part in response.iter_bytes():
                    size += len(part)
                    if size > maximum:
                        raise ValueError('Response exceeds bounded download size')
                    sha.update(part);handle.write(part)
            receipt = {'url':url, 'request':payload, 'retrieved_at':stamp(), 'http_status':response.status_code,
                       'bytes':size, 'sha256':sha.hexdigest()}
        if url == SURVEY and not temporary.read_bytes().startswith(b'%PDF'):
            raise ValueError('Expected a PDF')
        if path.suffix == '.json':
            json.loads(temporary.read_text(encoding='utf-8-sig'))
        temporary.replace(path)
        atomic(path.with_suffix('.receipt.json'), receipt)
        return receipt
    finally:
        temporary.unlink(missing_ok=True)


def summarize_iot(path):
    data = json.loads(path.read_text(encoding='utf-8-sig'))['d']
    data = json.loads(data) if isinstance(data, str) else data
    if not isinstance(data, list) or len(data) != 2 or not all(isinstance(a, list) for a in data):
        raise ValueError('Unexpected public pilot contract')
    villages, readings = data
    mh = [r for r in villages if str(r.get('StateName', '')).lower() == 'maharashtra']
    mh_ids = {r['VillageId'] for r in mh}
    return {'returned_rows':len(villages), 'distinct_village_ids':len({r['VillageId'] for r in villages}),
            'states':dict(Counter(r.get('StateName') for r in villages)),
            'maharashtra_rows':len(mh), 'maharashtra_dated_readings':sum(r.get('VillageId') in mh_ids for r in readings),
            'dated_readings':len(readings), 'dates':dict(Counter(r.get('Date') for r in readings)),
            'prediction_use':False,
            'limitations':'Unversioned public dashboard request, not an approved API contract. Duplicate village rows, population vintage, units and sensor status require review. No zero placeholders treated as quality measurements.'}


def summarize_additional(path, name, url):
    content = path.read_bytes()
    receipt = json.loads(path.with_suffix('.receipt.json').read_text(encoding='utf-8'))
    if hashlib.sha256(content).hexdigest() != receipt['sha256']:raise ValueError('Evidence hash mismatch')
    data = json.loads(content)
    value = data.get('d', data)
    if isinstance(value, str):value = json.loads(value)
    result = {'id':name, 'url':url, 'receipt':receipt, 'prediction_use':False}
    if name == 'jjm-root-records':
        result.update(returned_rows=len(value), maharashtra_rows=[r for r in value if r.get('StateName') == 'Maharashtra'],
            limitations='Pilot inventory only, undated population/source descriptions. Janori listing and detailed source profile differ; identity/service-area reconciliation required before use.')
    elif name == 'neeri-sensors':
        result.update(saved_or_live_flag=data.get('live'), devices_returned=len(data.get('data', [])),
            device_code_prefixes=sorted({r['device_code'].split('_')[0] for r in data.get('data', [])}),
            limitations='Dashboard explicitly returned live=0 (saved mode). Device-code prefixes are not a verified state/village crosswalk. No current Maharashtra delivery series verified.')
    elif name == 'janori-sources':
        result.update(rows=value, limitations='Source locations/types only; no observation date, source yield, flow or verified modern service area. FunctionalStatus is null.')
    elif name == 'janori-schemes':
        result.update(rows=value, limitations='Administrative status is undated, not a current flow measurement. Older sanctioned assets are discovery metadata only, not 2011-based prediction inputs.')
    else:
        result.update(response=value, limitations='Checked Janori public request returned no dated delivery measurements; empty is unknown, not zero delivery.')
    return result


def resource_daily(resource, path, receipt, today):
    """Keep parameters/gates separate; never add overlapping resources together."""
    series, rejected = {}, Counter()
    sha = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024), b''):sha.update(chunk)
    if sha.hexdigest() != receipt['sha256']:
        raise ValueError('Raw resource hash mismatch: '+resource['id'])
    seen, conflicts = {}, set()
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            row = {k.strip():v for k, v in raw.items() if k}
            if str(row.get('State', '')).strip().lower() != 'maharashtra':
                rejected['outside_state'] += 1;continue
            observed = read_date(row.get('Data Acquisition Time'))
            if observed is None or not date(2021, 1, 1) <= observed.date() < today:
                rejected['invalid_old_or_incomplete_day'] += 1;continue
            station, agency = row.get('Station', '').strip(), row.get('Agency', '').strip()
            if not station or not agency:
                rejected['no_identity'] += 1;continue
            identity = [resource['id'], agency, station, row.get('District LGD Code', ''), row.get('Latitude', ''), row.get('Longitude', '')]
            station_id = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]
            for field, raw_value in row.items():
                if 'discharge' not in field.lower():continue
                unit = 'cusec' if '(cusec)' in field.lower() else 'm3/sec' if '(m3/sec)' in field.lower() else None
                if not unit:
                    rejected['unreviewed_units'] += 1;continue
                try:
                    value = float(raw_value)
                    if not math.isfinite(value) or value < 0:raise ValueError
                except (ValueError, TypeError):
                    rejected['missing_or_invalid_value'] += 1;continue
                key = (station_id, field, observed.isoformat())
                value *= CFS_TO_CMS if unit == 'cusec' else 1
                if key in seen:
                    rejected['duplicate_parameter_timestamp'] += 1
                    if seen[key][0] != value:conflicts.add(key)
                    continue
                seen[key] = (value, observed.date(), {'station':station, 'agency':agency, 'district':row.get('District'),
                    'original_unit':unit, 'parameter':field, 'resource_id':resource['id'], 'source_url':resource['url'],
                    'raw_sha256':receipt['sha256'], 'retrieved_at':receipt['retrieved_at'],
                    'publication_available_at':None, 'village_connection_verified':False})
    for key, (value, day, meta) in seen.items():
        if key in conflicts:
            rejected['conflicting_parameter_timestamp'] += 1;continue
        bucket = series.setdefault((key[0], key[1]), {'meta':meta, 'days':defaultdict(list)})
        bucket['days'][day].append(value)
    result = []
    for (station_id, parameter), data in sorted(series.items()):
        means = {day:sum(values)/len(values) for day, values in data['days'].items()}
        for day, values in sorted(data['days'].items()):
            history = [means.get(day-timedelta(days=i)) for i in range(1, 8)]
            prior = means.get(day-timedelta(days=7))
            result.append({**data['meta'], 'station_series_id':station_id+':'+parameter, 'date':day.isoformat(),
                'units':'m3/sec', 'observed_sample_mean':means[day], 'observed_sample_min':min(values),
                'observed_sample_max':max(values), 'sample_count':len(values),
                'lag_1d':means.get(day-timedelta(days=1)), 'lag_7d':prior, 'lag_15d':means.get(day-timedelta(days=15)),
                'previous_7d_count':sum(v is not None for v in history),
                'previous_7d_mean':sum(history)/7 if all(v is not None for v in history) else None,
                'change_from_7d_ago':means[day]-prior if prior is not None else None,
                'split':'historical_candidate' if day.year < 2026 else 'current_year_holdout_context',
                'prediction_use':'context_only_pending_verified_asset_join_and_issue_time_review',
                'value_basis':'publisher_observation_unvalidated', 'village_delivered_litres':None,
                'limitations':'Sample mean is not time-weighted daily mean or integrated volume. No sampling gap filling; zero readings retained as reported, not validated. Gates/resources are not summed. Historical publication availability is unknown.'})
    return result, dict(rejected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Process previously fetched evidence only')
    args = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    report = {'checked_at':stamp(), 'target':'village_water_supply_sufficiency_7_and_15_days', 'sources':[], 'failures':[]}
    if not args.offline:
        with httpx.Client(timeout=45, follow_redirects=True) as client:
            for name, payload in [('iot-receiving', {'StateId':'11','IsdataRecevived':'21','type':'0'}),
                     ('iot-all-pilots', {'StateId':'11','IsdataRecevived':'11','type':'0'}),
                     ('iot-maharashtra', {'StateId':'291','IsdataRecevived':'11','type':'0'})]:
                try:retrieve(client, ROOT/(name+'.json'), IOT, payload=payload)
                except (httpx.HTTPError, ValueError) as e:report['failures'].append({'id':name,'error':type(e).__name__})
            try:retrieve(client, ROOT/'maharashtra-functionality-2024.pdf', SURVEY)
            except (httpx.HTTPError, ValueError) as e:report['failures'].append({'id':'survey','error':type(e).__name__})
            for name, url, payload in EXTRA_READS:
                try:retrieve(client, ROOT/(name+'.json'), url, payload=payload)
                except (httpx.HTTPError, ValueError) as e:report['failures'].append({'id':name,'error':type(e).__name__})
    for name in ['iot-receiving','iot-all-pilots','iot-maharashtra']:
        path = ROOT/(name+'.json')
        if path.exists():
            report['sources'].append({'id':name, 'url':IOT, 'receipt':json.loads(path.with_suffix('.receipt.json').read_text(encoding='utf-8')),
                                      **summarize_iot(path)})
    for name, url, _ in EXTRA_READS:
        path = ROOT/(name+'.json')
        if path.exists():report['sources'].append(summarize_additional(path, name, url))
    survey = ROOT/'maharashtra-functionality-2024.pdf'
    if survey.exists():
        survey_receipt = json.loads(survey.with_suffix('.receipt.json').read_text(encoding='utf-8'))
        reviewed = survey_receipt['sha256'] == REVIEWED_SURVEY_SHA256
        report['sources'].append({'id':'maharashtra_functionality_2024', 'url':SURVEY,
            'receipt':survey_receipt, 'profile_reviewed':reviewed,
            'observation_period':'July-October 2024' if reviewed else None, 'districts':34 if reviewed else None,
            'villages_sampled':1023 if reviewed else None, 'households_sampled':12276 if reviewed else None,
            'use':'historical district survey context; no village daily litres or 7/15-day labels',
            'current_village_measurement':False, 'latest_scope':'latest Maharashtra assessment listed on the checked 2024 report page; not a claim that no newer survey exists'})
    catalogue = json.loads(Path('data/water/catalogue.json').read_text(encoding='utf-8'))
    resources = {r['id']:r for r in catalogue['resources']}
    all_rows, resources_summary = 0, []
    feature_path = ROOT/'surface-flow-daily.jsonl'
    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    with feature_path.with_suffix('.part').open('w', encoding='utf-8') as target:
        with httpx.Client(timeout=45, follow_redirects=True) as client:
            for rid in FLOW_IDS:
                resource = resources[rid]
                path = Path('data/raw/water')/(rid+'.csv')
                fresh = ROOT/'nwic'/(rid+'.csv')
                if resource['role'] == 'current':
                    if not args.offline:
                        try:retrieve(client, fresh, resource['url'])
                        except (httpx.HTTPError, ValueError) as e:report['failures'].append({'id':rid,'error':type(e).__name__})
                    if fresh.exists():path = fresh
                if not path.exists():
                    report['failures'].append({'id':rid,'error':'missing_raw_archive'});continue
                receipt = json.loads(path.with_suffix('.receipt.json').read_text(encoding='utf-8'))
                rows, rejected = resource_daily(resource, path, receipt, today)
                for row in rows:target.write(json.dumps(row, ensure_ascii=True)+'\n')
                all_rows += len(rows)
                resources_summary.append({'id':rid, 'name':resource['name'], 'url':resource['url'], 'receipt':receipt,
                    'daily_parameter_rows':len(rows), 'station_series':len({r['station_series_id'] for r in rows}),
                    'first_day':min((r['date'] for r in rows), default=None), 'last_day':max((r['date'] for r in rows), default=None),
                    'districts':sorted({r['district'] for r in rows if r['district']}), 'excluded':rejected})
    feature_path.with_suffix('.part').replace(feature_path)
    report['surface_flow'] = {'output':str(feature_path), 'daily_parameter_rows':all_rows, 'resources':resources_summary,
                              'sha256':hashlib.sha256(feature_path.read_bytes()).hexdigest()}
    report['measured_village_daily_supply_rows'] = 0
    report['measurement_count_scope'] = 'this collection of public endpoints, not an inventory of records held privately by village operators'
    report['supervised_supply_training_ready'] = False
    report['remaining'] = ['Verified source/scheme-to-village mapping and current service area population',
        'Daily inlet/outlet volumes, usable tank storage, demand and observed shortage history',
        'Actual runtime/outages, loss studies, tanker delivery volumes and source allocations',
        'Chronological model validation with villages and seasons held out; no estimated labels']
    atomic(OUT, report)
    print(json.dumps({'report':str(OUT), 'daily_context_rows':all_rows, 'measured_village_rows':0, 'failures':report['failures']}, indent=2))


if __name__ == '__main__':main()
