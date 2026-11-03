"""Read official NWIC resources; publish dated Maharashtra map/data snapshots.

No credentials, application database writes, Census baselines or model training.
Historical resources remain explicit downloads; current observations are parsed
chronologically, never ordered lexically by day-first timestamp strings.
"""
import argparse
import concurrent.futures
import csv
import hashlib
import io
import json
import math
import os
import re
import time
import zipfile
from contextlib import contextmanager
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from functools import lru_cache

import httpx

API = 'https://nwdp.nwic.gov.in/api/3/action/'
RAW = Path('data/raw/water')
OUT = Path(os.environ.get('WATER_DATA_ROOT', 'data/water'))
CURRENT_YEAR = datetime.now(timezone.utc).year
SOURCE_TZ = timezone(timedelta(hours=5, minutes=30))


def stamp():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def sync_lock():
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / '.sync.lock').open('a+b') as lock:
        lock.seek(0, 2)
        if not lock.tell():
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == 'nt':
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    temporary.replace(path)


@lru_cache(maxsize=200000)
def read_date(value):
    value = str(value or '').strip()
    for fmt in ('%d-%m-%Y %H:%M:%S', '%d-%m-%Y %H:%M', '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)
    except ValueError:
        return None


def kind_for(title):
    value = title.lower().replace('_', ' ')
    if 'quality' in value:
        return 'water_quality'
    if 'ground' in value or 'well water' in value:
        return 'groundwater'
    if 'canal' in value:
        return 'canal'
    if 'reservoir' in value or 'reservior' in value:
        return 'reservoir'
    if 'river' in value or 'scada' in value:
        return 'river'
    if 'quality' in value:
        return 'water_quality'
    return 'weather'


def official_url(url):
    return url.startswith('https://nwdp.nwic.gov.in/dataset/')


def preferred_kind(kinds):
    # A specific published source category takes precedence over an overlapping
    # generic dataset. Never infer the asset type from a station's name.
    return next((k for k in ('groundwater', 'water_quality', 'reservoir', 'canal', 'river', 'weather') if k in kinds), 'weather')


def download(resource):
    if not official_url(resource['url']):
        raise ValueError('Resource is outside the reviewed official download host')
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / (resource['id'] + ('.zip' if resource['format'].upper() == 'SHP' else '.csv'))
    receipt_path = path.with_suffix('.receipt.json')
    revision = resource.get('last_modified') or resource.get('metadata_modified')
    if path.exists() and receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        if receipt.get('revision') == revision and receipt.get('bytes') == path.stat().st_size:
            if hashlib.sha256(path.read_bytes()).hexdigest() == receipt['sha256']:
                return path, receipt
    digest = hashlib.sha256()
    size = 0
    temporary = path.with_suffix('.part')
    with httpx.Client(timeout=90, follow_redirects=False) as client:
        with client.stream('GET', resource['url']) as response:
            response.raise_for_status()
            with temporary.open('wb') as stream:
                for block in response.iter_bytes(1024 * 1024):
                    size += len(block)
                    if size > 800_000_000:
                        raise ValueError('Resource exceeds the bounded download limit')
                    digest.update(block)
                    stream.write(block)
    temporary.replace(path)
    receipt = dict(url=resource['url'], retrieved_at=stamp(), revision=revision, bytes=size, sha256=digest.hexdigest())
    atomic(receipt_path, receipt)
    return path, receipt


def is_maharashtra(resource):
    # Resource geography, not merely the producer's name, must match.
    name = resource.get('name', '').replace('Maharashtra_SW', '').replace('Maharashtra_GW', '')
    basin_resource = bool(re.search(r'River Water Level Maharashtra_SW (Godavari|Krishna|Tapi|West flowing|\-)', resource.get('name', '')))
    return 'maharashtra' in name.lower() or '_mh_' in resource.get('url', '').lower() or basin_resource


def discover():
    packages = {}
    with httpx.Client(timeout=40) as client:
        for query in ('Maharashtra', 'organization:maharashtra-sw', 'organization:maharashtra-gw'):
            offset = 0
            while True:
                response = client.get(API + 'package_search', params={'q': query, 'rows': 100, 'start': offset})
                response.raise_for_status()
                batch = response.json()['result']
                for package in batch['results']:
                    packages[package['id']] = package
                offset += len(batch['results'])
                if offset >= batch['count'] or not batch['results']:
                    break
        for slug in ('river-line', 'canal', 'reservoir'):
            response = client.get(API + 'package_show', params={'id': slug})
            response.raise_for_status()
            package = response.json()['result']
            packages[package['id']] = package
    return list(packages.values())


def inventory(packages):
    entries = []
    for package in packages:
        for resource in package['resources']:
            if resource.get('format', '').upper() != 'CSV' or not is_maharashtra(resource):
                continue
            years = [int(y) for y in re.findall(r'(?<!\d)(?:19|20)\d{2}(?!\d)', resource.get('name', ''))]
            if not years or max(years) < 2021:
                continue
            entry = {k: resource.get(k) for k in ('id', 'name', 'url', 'format', 'size', 'last_modified', 'datastore_active')}
            entry.update(package_id=package['id'], package_name=package['name'], title=package['title'],
                         kind=kind_for(package['name']), agency=package.get('organization', {}).get('title', ''),
                         catalogue_url='https://nwdp.nwic.gov.in/dataset/' + package['name'],
                         api_url=API + 'datastore_search?resource_id=' + resource['id'],
                         period_start=min(years), period_end=max(years),
                         role='current' if min(years) <= CURRENT_YEAR <= max(years) else 'history',
                         training_filter='Observation dates from 2021 onward only; retain original units and issue times',
                         access_status='unverified')
            entries.append(entry)
    return entries


def probe(entry):
    try:
        response = httpx.get(API + 'datastore_search', params={'resource_id': entry['id'], 'limit': 1}, timeout=30)
        response.raise_for_status()
        data = response.json()
        if not data.get('success'):
            raise ValueError('Record API rejected query')
        result = data['result']
        return {**entry, 'access_status': 'api_verified', 'record_count': result.get('total'),
                'fields': [f['id'] for f in result.get('fields', [])], 'checked_at': stamp()}
    except Exception as error:
        return {**entry, 'access_status': 'failed', 'error_class': type(error).__name__, 'checked_at': stamp()}


def parse_resource(entry, path, encoding='utf-8-sig'):
    latest = {}
    rows = rejected = outside = 0
    newest = None
    with path.open(encoding=encoding, newline='') as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        keys = {k.lower().strip(): k for k in fields}
        date_key = next((k for k in fields if 'acquisition time' in k.lower() or k.lower().strip() == 'date of monitoring'), None)
        lat_key, lon_key = keys.get('latitude'), keys.get('longitude')
        if not date_key or not lat_key or not lon_key:
            return {}, dict(rows=0, rejection='No supported observation time / coordinate columns')
        measurement_keys = [k for k in fields if '(' in k and ')' in k and k not in (date_key,)]
        for row in reader:
            rows += 1
            observed = read_date(row.get(date_key))
            try:
                lat, lon = float(row[lat_key]), float(row[lon_key])
            except (TypeError, ValueError):
                rejected += 1
                continue
            if not observed or observed.year < 2021 or observed > datetime.now(SOURCE_TZ).replace(tzinfo=None) or not math.isfinite(lat + lon):
                rejected += 1
                continue
            if not (15.5 <= lat <= 22.2 and 72.5 <= lon <= 81.1):
                outside += 1
                continue
            state_key = keys.get('state', keys.get('state name'))
            if state_key and row[state_key].strip().lower() != 'maharashtra':
                outside += 1
                continue
            name = row.get(keys.get('station', keys.get('station name', keys.get('well id', ''))), '').strip()
            if not name:
                rejected += 1
                continue
            agency = row.get(keys.get('agency', keys.get('agency name', '')), entry['agency'])
            identity = '|'.join([agency.lower(), name.lower(), f'{lat:.5f}', f'{lon:.5f}'])
            asset_id = 'nwic-' + hashlib.sha256(identity.encode()).hexdigest()[:20]
            previous = latest.get(asset_id)
            values = []
            for label in measurement_keys:
                try:
                    value = float(row.get(label, ''))
                except (TypeError, ValueError):
                    continue
                if math.isfinite(value):
                    values.append(dict(label=label, value=value, units=label[label.rfind('(') + 1:label.rfind(')')],
                                       observed_at=observed.replace(tzinfo=SOURCE_TZ).isoformat(), resource_id=entry['id'], source_url=entry['url']))
            if keys.get('data value') and keys.get('unit'):
                try:
                    value = float(row[keys['data value']])
                    unit = row[keys['unit']]
                    label = row.get(keys.get('description', ''), 'Measured value') + ' (' + unit + ')'
                    if math.isfinite(value):
                        values.append(dict(label=label, value=value, units=unit,
                            observed_at=observed.replace(tzinfo=SOURCE_TZ).isoformat(), resource_id=entry['id'], source_url=entry['url']))
                except (ValueError, TypeError):
                    pass
            if keys.get('water level, m bgl'):
                try:
                    value = float(row[keys['water level, m bgl']])
                    if math.isfinite(value):
                        values.append(dict(label='Water level below ground', value=value, units='m bgl',
                            observed_at=observed.replace(tzinfo=SOURCE_TZ).isoformat(), resource_id=entry['id'], source_url=entry['url']))
                except (ValueError, TypeError):
                    pass
            # A newer row with no measurement must not erase the last real reading.
            if not values:
                continue
            newest = max(newest, observed) if newest else observed
            if not previous:
                previous = dict(type='Feature', id=asset_id, geometry=dict(type='Point', coordinates=[lon, lat]),
                    properties=dict(id=asset_id, name=name, kind=entry['kind'], kinds=[entry['kind']], agency=agency,
                        district=row.get(keys.get('district', keys.get('district name', '')), ''), district_code=row.get(keys.get('district lgd code', ''), ''),
                        taluka=row.get(keys.get('tehsil', keys.get('block name', '')), ''), source_url=entry['catalogue_url'],
                        source_village_text=row.get(keys.get('village', ''), ''), village_ids=[],
                        relationship='monitoring_site', measurements=[], resource_ids=[],
                        geometry_date=None, geometry_role='station_coordinate'))
                latest[asset_id] = previous
            props = previous['properties']
            measurements = {v['label']: v for v in props['measurements']}
            for value in values:
                if value['label'] not in measurements or value['observed_at'] > measurements[value['label']]['observed_at']:
                    measurements[value['label']] = value
            props['measurements'] = list(measurements.values())
            props['observed_at'] = max(v['observed_at'] for v in props['measurements'])
            props['resource_ids'] = [entry['id']]
    return latest, dict(rows=rows, rejected_rows=rejected, outside_rows=outside,
                       station_count=len(latest), latest_observation=newest.replace(tzinfo=SOURCE_TZ).isoformat() if newest else None)


def sync_entry(entry):
    try:
        path, receipt = download(entry)
        cached = path.with_suffix('.latest.json')
        if cached.exists():
            previous = json.loads(cached.read_text(encoding='utf-8'))
            if previous.get('parser_version') == 3 and previous.get('sha256') == receipt['sha256']:
                return previous['features'], {**entry, **previous['stats'], 'download_status': 'verified', 'receipt': receipt}
        features, stats = parse_resource(entry, path)
        atomic(cached, dict(parser_version=3, sha256=receipt['sha256'], features=features, stats=stats))
        print(json.dumps({'resource': entry['name'], **stats}), flush=True)
        return features, {**entry, **stats, 'download_status': 'verified', 'receipt': receipt}
    except Exception as error:
        print(json.dumps({'resource': entry['name'], 'error': type(error).__name__}), flush=True)
        return {}, {**entry, 'download_status': 'failed', 'error_class': type(error).__name__}


def merge_features(target, incoming):
    for key, feature in incoming.items():
        if key not in target:
            target[key] = feature
            continue
        props, new = target[key]['properties'], feature['properties']
        props['kinds'] = sorted(set(props.get('kinds', [props['kind']]) + new.get('kinds', [new['kind']])))
        props['kind'] = preferred_kind(props['kinds'])
        measurements = {(m['label'], m['resource_id']): m for m in props['measurements']}
        for value in new['measurements']:
            identity = (value['label'], value['resource_id'])
            if identity not in measurements or value['observed_at'] > measurements[identity]['observed_at']:
                measurements[identity] = value
        props['measurements'] = list(measurements.values())
        props['observed_at'] = max(m['observed_at'] for m in props['measurements'])
        props['resource_ids'] = sorted(set(props['resource_ids'] + new['resource_ids']))


def geometry_snapshot(package):
    import shapefile
    from pyproj import CRS, Transformer
    from shapely.geometry import shape, mapping
    resource = next(r for r in package['resources'] if r.get('format', '').upper() == 'SHP')
    path, receipt = download(resource)
    # Read only in memory; never extract paths from an external ZIP archive.
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        shp = next(n for n in names if n.lower().endswith('.shp'))
        base = shp[:-4]
        members = {n.lower(): n for n in names}
        prj_name = members.get((base + '.prj').lower())
        projection = archive.read(prj_name).decode(errors='replace') if prj_name else ''
        crs = CRS.from_wkt(projection)
        to_lonlat = Transformer.from_crs(crs, 'EPSG:4326', always_xy=True)
        to_source = Transformer.from_crs('EPSG:4326', crs, always_xy=True)
        reader = shapefile.Reader(shp=io.BytesIO(archive.read(shp)),
            dbf=io.BytesIO(archive.read(members[(base + '.dbf').lower()])),
            shx=io.BytesIO(archive.read(members[(base + '.shx').lower()])))
        fields = [f[0] for f in reader.fields[1:]]
        features = []
        boundary = (72.5, 15.5, 81.1, 22.2)
        source_boundary = to_source.transform_bounds(*boundary, densify_pts=21)
        for index, record in enumerate(reader.iterShapeRecords(bbox=source_boundary)):
            attrs = dict(zip(fields, record.record))
            state = next((str(v) for k, v in attrs.items() if k.lower() in ('state', 'state_name', 'st_name', 'state_al')), None)
            if state and 'maharashtra' not in state.lower():
                continue
            geometry = record.shape.__geo_interface__
            def transform(values):
                if len(values) >= 2 and all(isinstance(v, (int, float)) for v in values[:2]):
                    x, y = to_lonlat.transform(values[0], values[1])
                    if not math.isfinite(x + y):
                        raise ValueError('Invalid transformed coordinate')
                    return [x, y]
                return [transform(v) for v in values]
            geometry['coordinates'] = transform(geometry['coordinates'])
            display_shape = shape(geometry).simplify(.0002, preserve_topology=True)
            geometry = mapping(display_shape)
            # Source layers with no state field remain explicitly regional context.
            name = next((str(attrs[k]) for k in ('can_name', 'rivname', 'res_name', 'name', 'reservoir') if attrs.get(k)),
                        next((str(v) for k, v in attrs.items() if v and 'name' in k.lower()), package['title']))
            kind = {'river-line': 'river', 'canal': 'canal', 'reservoir': 'reservoir'}[package['name']]
            identity = 'geometry-' + package['name'] + '-' + str(index)
            features.append(dict(type='Feature', id=identity, geometry=geometry, bbox=list(display_shape.bounds),
                properties=dict(id=identity, name=name, kind=kind, agency='CWC / NWIC', district='', village_ids=[],
                    source_url='https://nwdp.nwic.gov.in/dataset/' + package['name'], resource_ids=[resource['id']],
                    geometry_date=None, catalogue_updated_at=package.get('metadata_modified'),
                    relationship='geographic_context', measurements=[], observed_at=None,
                    geometry_role='reference_only', geography_filter='Maharashtra asset; full geometry may cross state borders' if state else 'Maharashtra bounding region',
                    display_simplification_degrees=.0002,
                    note='Latest published reference file; survey date unspecified. Geometry generalized for display; original archive retained. Excluded from prediction inputs.')))
    # Round display coordinates, preserving every vertex and original cached archive.
    def rounded(value):
        if isinstance(value, (tuple, list)):
            return [rounded(v) for v in value]
        return round(value, 5) if isinstance(value, float) else value
    for feature in features:
        feature['geometry']['coordinates'] = rounded(feature['geometry']['coordinates'])
    return features, dict(name=package['name'], features=len(features), fields=fields, receipt=receipt, source_crs=crs.to_string(), display_crs='EPSG:4326',
                          geometry_date=None, prediction_use=False, geography='state attribute when available; otherwise bounding region')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--geometry', action='store_true', help='Download official river/canal/reservoir map archives')
    parser.add_argument('--history', action='store_true', help='Also download historical files (can be several GB); map parser still uses current resources')
    parser.add_argument('--catalogue-only', action='store_true')
    parser.add_argument('--workers', type=int, default=4, choices=range(1, 7))
    args = parser.parse_args()
    packages = discover()
    entries = inventory(packages)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        entries = list(pool.map(probe, entries))
    report = dict(updated_at=stamp(), source='National Water Data Portal / NWIC',
                  scope='Maharashtra resources across available publishing agencies; coverage is measured, not assumed',
                  history_min_year=2021, census_used=False, resources=entries,
                  blocked=[dict(name='IMD district rainfall forecast', status='api_key_required',
                      url='https://api.imd.gov.in/api/v1/state_district_rainfall_forecast', checked_status=401),
                      dict(name='Village pipeline / DMA operational feeds', status='no_verified_public_feed',
                           note='No pipeline or supply connection is inferred from proximity')])
    if args.catalogue_only or not (OUT / 'catalogue.json').exists():
        atomic(OUT / 'catalogue.json', report)
    if args.catalogue_only:
        print(json.dumps({'resources': len(entries), 'catalogue': str(OUT / 'catalogue.json')}))
        return
    assets = {}
    current = [e for e in entries if e['role'] == 'current']
    checked = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for features, entry in pool.map(sync_entry, current):
            merge_features(assets, features)
            checked.append(entry)
    indexed = {e['id']: e for e in checked}
    if not assets:
        raise RuntimeError('No valid observation assets; the previous published snapshot was preserved')
    report['resources'] = [indexed.get(e['id'], e) for e in entries]
    geometries = []
    if args.geometry:
        for slug in ('river-line', 'canal', 'reservoir'):
            try:
                features, receipt = geometry_snapshot(next(p for p in packages if p['name'] == slug))
                geometries.extend(features)
                report.setdefault('geometry', []).append(receipt)
                print(json.dumps({'geometry': slug, 'features': len(features)}), flush=True)
            except Exception as error:
                report.setdefault('geometry', []).append({'name': slug, 'status': 'failed', 'error_class': type(error).__name__})
    elif (OUT / 'network.geojson').exists():
        geometries = json.loads((OUT / 'network.geojson').read_text(encoding='utf-8')).get('features', [])
        if (OUT / 'catalogue.json').exists():
            report['geometry'] = json.loads((OUT / 'catalogue.json').read_text(encoding='utf-8')).get('geometry', [])
    report['updated_at'] = stamp()
    report['station_count'] = len(assets)
    report['districts'] = sorted({f['properties']['district'] for f in assets.values() if f['properties']['district']})
    report['station_kinds'] = dict(Counter(f['properties']['kind'] for f in assets.values()))
    atomic(OUT / 'stations.geojson', dict(type='FeatureCollection', updated_at=stamp(), features=list(assets.values())))
    atomic(OUT / 'network.geojson', dict(type='FeatureCollection', updated_at=stamp(), features=geometries))
    atomic(OUT / 'catalogue.json', report)
    try:
        from scripts.sync_public_utilities import main as sync_utilities
        sync_utilities()
    except Exception as error:
        print(json.dumps({'utility_refresh': 'failed_previous_snapshot_retained', 'error_class': type(error).__name__}), flush=True)
    try:
        from scripts.publish_historical_quality import main as publish_quality
        publish_quality()
        if (RAW / 'bb185a88-c7c3-483f-b06e-784ce5322ff8.csv').exists():
            from scripts.publish_historical_wells import main as publish_wells
            publish_wells()
    except Exception as error:
        print(json.dumps({'quality_refresh': 'failed_previous_snapshot_retained', 'error_class': type(error).__name__}), flush=True)
    from scripts.sync_additional_water import main as sync_additional
    sync_additional()
    if args.history:
        for entry in entries:
            if entry['role'] == 'history':
                try:
                    _, receipt = download(entry)
                    entry['history_download'] = receipt
                except Exception as error:
                    entry['history_download'] = {'error_class': type(error).__name__}
        atomic(OUT / 'catalogue.json', report)
    print(json.dumps({'stations': len(assets), 'districts': len(report['districts']), 'resources': len(entries),
                      'geometry_features': len(geometries), 'path': str(OUT)}), flush=True)


if __name__ == '__main__':
    with sync_lock():
        main()
