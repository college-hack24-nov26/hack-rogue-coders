"""Dated official observations and reviewed village connections for the map."""
import json
import math
import os
import subprocess
import sys
import threading
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import current, require
from .config import settings
from .db import Record, User, Village, session
from .water_evidence import reviews_for

router = APIRouter(prefix='/api/v1')
_refresh_lock = threading.Lock()
_refresh_process = None


@router.get('/water-data/refresh-status')
def refresh_status(u: User = Depends(current)):
    process = _refresh_process
    code = process.poll() if process else None
    return {'running': bool(process and code is None), 'last_refresh_succeeded': code == 0 if process else None,
            'updated_at': snapshot('catalogue.json').get('updated_at')}


@router.post('/admin/water-data/refresh', status_code=202)
def refresh_sources(u: User = Depends(current)):
    global _refresh_process
    require(u, ['system_admin'])
    with _refresh_lock:
        if _refresh_process and _refresh_process.poll() is None:
            raise HTTPException(409, 'An official-data refresh is already running')
        root = Path(__file__).resolve().parents[2]
        output = Path(settings.water_data_root).resolve()
        output.mkdir(parents=True, exist_ok=True)
        environment = {**os.environ, 'WATER_DATA_ROOT': str(output)}
        with (output / 'refresh.log').open('w', encoding='utf-8') as log:
            _refresh_process = subprocess.Popen([sys.executable, '-m', 'scripts.sync_water_data'], cwd=root,
                env=environment, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    return {'status': 'refreshing', 'message': 'Refreshing official observations. The existing snapshot remains available.'}


@lru_cache(maxsize=12)
def _read_file(path, modified):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def snapshot(name):
    path = Path(settings.water_data_root) / name
    if not path.exists():
        return {'features': [], 'resources': [], 'updated_at': None}
    return _read_file(str(path.resolve()), path.stat().st_mtime_ns)


def monitoring_features():
    features = snapshot('stations.geojson').get('features', []) + snapshot('reservoirs.geojson').get('features', [])
    current_ids = {f['properties'].get('id') for f in features}
    # Never let an older quality snapshot overwrite a current monitoring identity.
    historical = snapshot('historical-quality.geojson').get('features', []) + snapshot('historical-wells.geojson').get('features', [])
    return features + [f for f in historical if f['properties'].get('id') not in current_ids]


def network_features():
    return snapshot('network.geojson').get('features', []) + snapshot('utility-network.geojson').get('features', [])


def freshness(value):
    if not value:
        return 'undated'
    try:
        observed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if observed.tzinfo is None:
            from datetime import timedelta
            observed = observed.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
        age = (datetime.now(timezone.utc) - observed).total_seconds()
        return 'recent' if 0 <= age <= 48 * 3600 else 'older'
    except (ValueError, TypeError):
        return 'undated'


def bounds(geometry):
    points = []
    def visit(value):
        if not isinstance(value, (list, tuple)):
            return
        if len(value) >= 2 and all(isinstance(n, (int, float)) and math.isfinite(n) for n in value[:2]):
            points.append(value[:2])
        else:
            for child in value:
                visit(child)
    if geometry:
        visit(geometry.get('coordinates'))
    if not points:
        return None
    return min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)


def intersects(a, b):
    return bool(a and b and a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1])


def feature_bounds(feature):
    return feature.get('bbox') or bounds(feature.get('geometry'))


def parse_bbox(value):
    if value is None:
        return None
    try:
        result = tuple(float(n) for n in value.split(','))
        if len(result) != 4 or not all(math.isfinite(n) for n in result):
            raise ValueError
        if not (-180 <= result[0] < result[2] <= 180 and -90 <= result[1] < result[3] <= 90):
            raise ValueError
        return result
    except (ValueError, TypeError):
        raise HTTPException(422, 'Map bounds must be west,south,east,north')


def clean_feature(feature, relationship=None):
    props = {**feature['properties']}
    props['freshness'] = freshness(props.get('observed_at'))
    if relationship:
        props['relationship'] = relationship
    return {**feature, 'properties': props}


@router.get('/water-data/catalogue')
def catalogue(u: User = Depends(current)):
    data = snapshot('catalogue.json')
    return {**data, 'census_used': False, 'history_min_year': 2021,
            'public_supply_collection': public_supply_collection(),
            'additional_sources': snapshot('additional-sources.json'),
            'history_collection': snapshot('history-collection.json'),
            'historical_quality_sites': len(snapshot('historical-quality.geojson').get('features', [])),
            'historical_well_sites': len(snapshot('historical-wells.geojson').get('features', [])),
            'utility_features': len(snapshot('utility-network.geojson').get('features', [])),
            'districts': data.get('districts', []),
            'map_geometry': snapshot('network.geojson').get('updated_at'),
            'limitations': ['Latest published observations are not a real-time supply guarantee.',
                           'Monitoring stations and nearby rivers do not establish village supply connections.',
                           'Reference geometry with unknown survey date is excluded from prediction inputs.',
                           'No 2011 population, demand or infrastructure baseline is used.']}


def public_supply_collection():
    """Expose source coverage only; raw tanker files include contact details."""
    report = snapshot('public-supply-completion.json')
    sources = report.get('sources', {})
    audit = snapshot('public-supply-file-audit.json')
    fields = {
        'jjm': ('status', 'village_records', 'districts_completed'),
        'pmc': ('status', 'downloaded_files', 'failed_files', 'index_complete'),
        'wssd': ('status', 'downloaded_files', 'listed_files'),
        'pocra': ('status', 'weather_date_range', 'weather', 'village_attributes'),
    }
    summary = {key: {field: sources.get(key, {}).get(field) for field in selected}
               for key, selected in fields.items()}
    # No local paths, receipts, raw records or application field names are needed.
    summary['pocra']['weather_rows'] = (summary['pocra'].pop('weather') or {}).get('rows')
    return {'checked_at': report.get('checked_at'), 'sources': summary,
            'files_profiled': bool(audit.get('checked_at')),
            'verified_village_supply_records_added': audit.get('eligible_daily_village_supply_records_added'),
            'reviewed_urgency_labels_added': audit.get('reviewed_urgency_labels_added')}


@router.get('/water-data/map')
def state_map(bbox: str | None = None, district: str = '', kinds: str = '', limit: int = Query(4000, ge=1, le=12000),
              u: User = Depends(current)):
    viewport = parse_bbox(bbox)
    selected_kinds = set(kinds.split(',')) if kinds else None
    stations = snapshot('stations.geojson')
    station_features = monitoring_features()
    features = [clean_feature(f) for f in station_features
                if (not district or str(f['properties'].get('district', '')).casefold() == district.casefold())
                and (not selected_kinds or f['properties'].get('kind') in selected_kinds)
                and (not viewport or intersects(feature_bounds(f), viewport))]
    # National reference geometries have no reliable district join. Fetch them
    # by viewport, retaining their explicit geographic-context relationship.
    network = network_features()
    if district:
        # Layer filters must not erase the district extent when only pipes are selected.
        district_assets = [f for f in station_features if str(f['properties'].get('district', '')).casefold() == district.casefold()]
        boxes = [feature_bounds(f) for f in district_assets if feature_bounds(f)]
        viewport = (min(b[0] for b in boxes) - .05, min(b[1] for b in boxes) - .05,
                    max(b[2] for b in boxes) + .05, max(b[3] for b in boxes) + .05) if boxes else None
    features += [clean_feature(f) for f in network
                 if (not selected_kinds or f['properties'].get('kind') in selected_kinds)
                 and (not viewport or intersects(feature_bounds(f), viewport)) and (not district or viewport)]
    return {'type': 'FeatureCollection', 'features': features[:limit], 'total': len(features),
            'truncated': len(features) > limit, 'updated_at': stations.get('updated_at'),
            'counts': dict(Counter(f['properties']['kind'] for f in features)),
            'scope': 'published_monitoring_and_reference_geometry'}


def district_matches(props, village):
    code = village.jurisdiction.removeprefix('district:')
    return bool(props.get('district_code') and str(props['district_code']) == code or
                str(props.get('district', '')).casefold() == village.district.casefold())


@router.get('/villages/{key}/water-map')
def village_map(key: str, u: User = Depends(current), db: Session = Depends(session)):
    village = db.get(Village, key)
    if not village:
        raise HTTPException(404, 'Village not found')
    geo = db.scalar(select(Record).where(Record.kind == 'geography', Record.key == key)
                    .order_by(Record.version.desc()).limit(1))
    payload = geo.payload if geo else {}
    crosswalks = payload.get('crosswalks', {})
    reviewed_ids = crosswalks.get('water_asset_ids', []) if isinstance(crosswalks, dict) else []
    reviewed_ids = {v for v in reviewed_ids if isinstance(v, str)} if isinstance(reviewed_ids, list) else set()
    features = []
    stations = snapshot('stations.geojson')
    network = network_features()
    reviewed = snapshot('reviewed-network.geojson').get('features', [])
    station_features = monitoring_features()
    connection_reviews = reviews_for(db, key)
    reviews_by_id = {r['asset_id']: r for r in connection_reviews}
    known_ids = {f['properties'].get('id') for f in station_features + network + reviewed}
    manual = [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [r['longitude'], r['latitude']]} if r.get('latitude') is not None else None,
               'properties': {'id': r['asset_id'], 'name': r['source_name'], 'kind': r['kind'],
                              'source_url': r['evidence_url'], 'measurements': [], 'agency': 'Local authority review'}}
              for r in connection_reviews if r['asset_id'] not in known_ids]
    centre = [village.longitude, village.latitude] if village.latitude is not None and village.longitude is not None else None
    boundary = payload.get('boundary')
    viewport = bounds(boundary) if boundary else None
    if not viewport and centre:
        viewport = (centre[0] - .12, centre[1] - .12, centre[0] + .12, centre[1] + .12)
    if not viewport:
        district_points = [f['geometry']['coordinates'] for f in station_features
                           if f.get('geometry', {}).get('type') == 'Point' and district_matches(f['properties'], village)]
        if district_points:
            # This is the extent of observed district stations, never a village location.
            viewport = (min(p[0] for p in district_points) - .05, min(p[1] for p in district_points) - .05,
                        max(p[0] for p in district_points) + .05, max(p[1] for p in district_points) + .05)
    for feature in station_features + network + reviewed + manual:
        props = feature.get('properties', {})
        # A name match or distance is never a supply connection.
        linked = props.get('id') in reviewed_ids or (
            feature in reviewed and props.get('relationship') == 'reviewed_connection'
            and key in props.get('village_ids', []) and bool(props.get('connection_evidence')))
        review = reviews_by_id.get(props.get('id'))
        if review:
            linked = review['current'] and review['connection_status'] == 'documented'
            feature = {**feature, 'properties': {**props, 'connection_review': review}}
        if linked:
            features.append(clean_feature(feature, 'reviewed_connection'))
        elif review:
            features.append(clean_feature(feature, 'not_connected' if review['current'] and review['connection_status'] == 'not_connected' else 'unverified_connection'))
        elif district_matches(props, village):
            features.append(clean_feature(feature, 'district_context'))
        elif viewport and intersects(feature_bounds(feature), viewport):
            features.append(clean_feature(feature, 'geographic_context'))
    linked_features = [f for f in features if f['properties']['relationship'] == 'reviewed_connection']
    unmapped = []
    allocations = list(db.scalars(select(Record).where(Record.kind == 'supply').order_by(Record.version.desc())))
    seen = set()
    for allocation in allocations:
        if allocation.key in seen or allocation.payload.get('village_id') != key:
            continue
        seen.add(allocation.key)
        supply = allocation.payload
        source = db.scalar(select(Record).where(Record.kind == 'supply_source', Record.key == supply['source_id'])
                           .order_by(Record.version.desc()).limit(1))
        unmapped.append({'name': supply['source_id'], 'kind': 'reviewed_supply', 'sector': supply.get('sector'),
                        'litres_per_day': supply.get('litres_per_day'), 'valid_until': supply.get('valid_until'),
                        'source_url': source.payload.get('source_url') if source else None,
                        'geometry': None, 'note': 'Recorded allocation; source coordinates have not been supplied.'})
    from .water_requirements import village_requirements, APPROXIMATIONS
    return {'type': 'FeatureCollection', 'village': {'id': village.id, 'name': village.name,
                'district': village.district, 'taluka': village.taluka, 'centre': centre,
                'boundary': boundary, 'location_status': 'reviewed' if centre or boundary else 'unavailable'},
            'features': features, 'updated_at': stations.get('updated_at'), 'unmapped_sources': unmapped,
            'connection_reviews': connection_reviews,
            'can_review': u.role in ['system_admin', 'admin', 'official'] and (u.role == 'system_admin' or village.jurisdiction in u.jurisdictions),
            'verification': village_requirements(centre, boundary, linked_features, connection_reviews),
            'approximations': APPROXIMATIONS,
            'linked_count': len(linked_features), 'context_count': len(features) - len(linked_features),
            'coverage': 'partial_verified_connections' if linked_features else 'no_verified_connections',
            'message': 'Showing recorded village connections and available monitoring context.' if linked_features else
                       'No verified supplying-source connections recorded for this village. Available district monitoring sites are shown as context.',
            'pipelines_available': any(f['properties'].get('kind') in ('pipeline', 'industrial_pipeline') for f in linked_features),
            'census_used': False}
