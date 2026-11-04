"""Prepare local public supply context without inventing operational targets.

Writes a versioned offline bundle. Public administrative, district-weather and
station-flow tables retain their own identities; no source-to-village join is
assumed. Use the manifest to distinguish prepared inputs from missing targets.
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean, pstdev
from uuid import uuid4

from services.worker.supply_features import IST

ROOT = Path('data/raw/supply')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def numeric(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError('Expected a finite number or explicit null')
    return value


def stream_rows(path):
    with path.open(encoding='utf-8-sig') as stream:
        for line, text in enumerate(stream, 1):
            if not text.strip():
                continue
            try:
                yield json.loads(text)
            except ValueError as error:
                raise ValueError(f'{path.name}: invalid JSON on line {line}') from error


def write_rows(path, rows):
    count = 0
    with path.open('w', encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=True, allow_nan=False)+'\n')
            count += 1
    return {'path': str(path), 'rows': count, 'sha256': sha256(path)}


def prepare_profiles(rows):
    seen = set()
    for row in rows:
        identity = 'jjm:'+row['jjm_village_id']
        if identity in seen:
            raise ValueError('Duplicate JJM village profile')
        seen.add(identity)
        households = numeric(row['reported_households'])
        taps = numeric(row['reported_tap_connections'])
        if households is None or taps is None or not 0 <= taps <= households:
            raise ValueError('Invalid household/tap profile')
        yield {'village_id': identity, 'village_name': row['village_name'], 'district': row['district'],
            'jjm_district_code': row['jjm_district_code'],
            'census_code_as_reported': row['census_code_as_reported'],
            'features': {'reported_households': households, 'reported_tap_connections': taps,
                'reported_tap_coverage_fraction': taps/households if households else None},
            'observed_on': row['observed_on'], 'available_at': row['retrieved_at'],
            'basis': row['basis'], 'source_url': row['source_url'], 'source_sha256': row['raw_sha256'],
            'label_7d': None, 'label_15d': None, 'supervised_eligible': False,
            'missing_for_training': ['dated_daily_delivery', 'usable_storage', 'sector_demand',
                                     'reviewed_future_outcomes', 'verified_service_area'],
            'use': 'administrative_context_snapshot_only'}


def preceding_features(days, issued, fields):
    """Exact calendar lags. Missing dates remain missing; today's value is excluded."""
    features = {}
    for name in fields:
        for lag in (1, 7, 15):
            features[name+f'_lag_{lag}d'] = days.get(issued-timedelta(days=lag), {}).get(name)
        for length in (7, 15):
            previous = [days.get(issued-timedelta(days=lag), {}).get(name) for lag in range(1, length+1)]
            values = [value for value in previous if value is not None]
            prefix = name+f'_previous_{length}d'
            features[prefix+'_count'] = len(values)
            features[prefix+'_mean'] = mean(values) if len(values) == length else None
            features[prefix+'_std'] = pstdev(values) if len(values) == length else None
    return features


def prepare_weather(rows, today):
    groups = {}
    fields = {'rain': 'rain_mm', 'temp_avg': 'temperature_c', 'rh_avg': 'humidity_percent'}
    for row in rows:
        day = date.fromisoformat(row['for_date'])
        if not date(2021, 1, 1) <= day < today:
            raise ValueError('Weather day outside completed 2021+ range')
        key = row['district_code_as_reported']
        if day in groups.setdefault(key, {}):
            raise ValueError('Duplicate district/day weather')
        values = {target: numeric(row.get(source)) for source, target in fields.items()}
        if values['rain_mm'] is not None and values['rain_mm'] < 0:
            raise ValueError('Negative rainfall')
        if values['humidity_percent'] is not None and not 0 <= values['humidity_percent'] <= 100:
            raise ValueError('Humidity outside physical range')
        groups[key][day] = {**values, 'raw': row}
    for district, days in sorted(groups.items()):
        for day, values in sorted(days.items()):
            row = values['raw']
            yield {'district_id': 'pocra:'+str(district), 'district': row['district'], 'date': day.isoformat(),
                'observations': {key: values[key] for key in fields.values()},
                'features': preceding_features(days, day, fields.values()),
                'source_url': row['source_url'], 'retrieved_at': row['retrieved_at'],
                'historical_publication_time': None, 'historical_feature_availability_verified': False,
                'basis': row['basis'], 'spatial_scope': 'district', 'village_connection_verified': False,
                'supervised_supply_target': False,
                'excluded_fields': ['wind: units unverified'],
                'use': 'district_context_candidate_not_joined_to_villages'}


def prepare_flow(rows, today):
    groups = {}
    for row in rows:
        day = date.fromisoformat(row['date'])
        if not date(2021, 1, 1) <= day < today:
            raise ValueError('Flow day outside completed 2021+ range')
        if row['units'] != 'm3/sec':
            raise ValueError('Unreviewed flow unit; conversion not guessed')
        key = (row['resource_id'], row['station_series_id'])
        if day in groups.setdefault(key, {}):
            raise ValueError('Duplicate resource/station/day flow')
        value = numeric(row['observed_sample_mean'])
        if value is not None and value < 0:
            raise ValueError('Negative flow requires instrument/reverse-flow review')
        groups[key][day] = {'flow_m3_s': value, 'raw': row}
    for (resource, station), days in sorted(groups.items()):
        for day, item in sorted(days.items()):
            row = item['raw']
            yield {'resource_id': resource, 'station_series_id': station, 'station': row['station'],
                'agency': row['agency'], 'district_as_reported': row['district'], 'date': day.isoformat(),
                'observed_sample_mean_m3_s': item['flow_m3_s'], 'sample_count': row['sample_count'],
                'features': preceding_features(days, day, ('flow_m3_s',)),
                'source_url': row['source_url'], 'source_sha256': row['raw_sha256'],
                'retrieved_at': row['retrieved_at'], 'historical_publication_time': row['publication_available_at'],
                'historical_feature_availability_verified': False, 'village_connection_verified': False,
                'supervised_supply_target': False, 'basis': row['value_basis'],
                'use': 'station_context_candidate_not_integrated_to_daily_volume'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('artifacts/supply-data'))
    args = parser.parse_args(argv)
    now = datetime.now(IST)
    folder = args.output/(now.strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:6])
    folder.mkdir(parents=True, exist_ok=False)
    sources = {
        'village_profiles': ROOT/'public-completion/jjm/village-households.jsonl',
        'district_weather': ROOT/'public-completion/pocra/weather-district-context.jsonl',
        'station_flow': ROOT/'surface-flow-daily.jsonl',
    }
    transforms = {'village_profiles': prepare_profiles,
                  'district_weather': lambda rows: prepare_weather(rows, now.date()),
                  'station_flow': lambda rows: prepare_flow(rows, now.date())}
    tables = {}; inputs = []
    for name, path in sources.items():
        before = sha256(path)
        print('Preparing '+name+'...', flush=True)
        tables[name] = write_rows(folder/(name+'.jsonl'), transforms[name](stream_rows(path)))
        if before != sha256(path):
            raise ValueError('Source changed while preparing: '+str(path))
        inputs.append({'path': str(path), 'sha256': before})
    report = {'created_at': now.isoformat(), 'offline': True, 'network_calls': 0, 'database_access': False,
        'status': 'context_prepared_operational_targets_missing', 'tables': tables, 'inputs': inputs,
        'ready_for_measured_supply_training': False, 'eligible_supervised_rows_created': 0,
        'synthetic_targets_created': 0, 'model_trained': False,
        'missing': ['verified village source/service-area joins', 'daily usable storage and delivery history',
                    'dated independent sector demand', 'reviewed 7/15-day shortage/urgency outcomes'],
        'rules': ['No village-level join from district names, proximity or unreviewed Census codes.',
                  'No missing value is zero-filled; calendar lags exclude issue-day/future observations.',
                  'Historical publication times are unknown; lagged observations are candidate features, not verified historical availability.',
                  'No default population, tanker capacity, flow/runtime, leakage or urgency label.',
                  'Inputs remain separate by spatial and measurement scope.']}
    target = folder/'dataset-manifest.json'
    target.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    pointer = args.output/'latest.json'
    pointer.write_text(json.dumps({'directory': str(folder.resolve()), 'manifest': str(target.resolve())}, indent=2), encoding='utf-8')
    print(json.dumps({'directory': str(folder), 'tables': {key: value['rows'] for key, value in tables.items()},
                      'ready_for_measured_supply_training': False, 'manifest': str(target)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
