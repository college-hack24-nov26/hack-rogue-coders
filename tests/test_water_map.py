import csv
import json
from datetime import datetime, timedelta, timezone

from services.api.config import settings
from services.api.db import Record, Village
from scripts.sync_water_data import parse_resource, read_date


def feature(identity, district='Test', coordinates=(74.4, 18.2), kind='groundwater'):
    return {'type': 'Feature', 'id': identity, 'geometry': {'type': 'Point', 'coordinates': list(coordinates)},
            'properties': {'id': identity, 'name': identity, 'kind': kind, 'district': district,
                           'relationship': 'monitoring_site', 'measurements': [], 'village_ids': [],
                           'observed_at': datetime.now(timezone.utc).isoformat()}}


def install_snapshot(monkeypatch, tmp_path, features, network=None):
    monkeypatch.setattr(settings, 'water_data_root', str(tmp_path))
    for name, data in [('stations.geojson', {'features': features}), ('network.geojson', {'features': network or []}),
                       ('catalogue.json', {'resources': [], 'census_used': False})]:
        (tmp_path / name).write_text(json.dumps(data), encoding='utf-8')


def test_public_collection_summary_excludes_raw_register_details(setup, monkeypatch, tmp_path):
    client, _, headers = setup
    install_snapshot(monkeypatch, tmp_path, [])
    (tmp_path/'public-supply-completion.json').write_text(json.dumps({'checked_at':'2026-11-04T00:00:00Z',
        'sources': {'pmc': {'status':'collected', 'downloaded_files':648,
                           'private_contacts':'MUST NOT BE EXPOSED', 'path':'PRIVATE FILE PATH'}}}))
    (tmp_path/'public-supply-file-audit.json').write_text(json.dumps({'checked_at':'2026-11-04T00:00:00Z',
        'eligible_daily_village_supply_records_added':0,'reviewed_urgency_labels_added':0}))
    response = client.get('/api/v1/water-data/catalogue', headers=headers['a'])
    assert response.status_code == 200
    result = response.json()['public_supply_collection']
    assert result['sources']['pmc']['downloaded_files'] == 648
    assert result['verified_village_supply_records_added'] == 0
    assert 'MUST NOT' not in response.text and 'PRIVATE FILE' not in response.text


def test_village_map_does_not_invent_location_or_supply_from_station_name(setup, monkeypatch, tmp_path):
    client, factory, headers = setup
    points = [feature('TEST FIXTURE ONLY'), feature('OTHER-DISTRICT', district='Elsewhere', coordinates=(79, 21))]
    install_snapshot(monkeypatch, tmp_path, points)
    path = '/api/v1/villages/TEST-A/water-map'
    assert client.get(path).status_code == 401
    result = client.get(path, headers=headers['f']).json()
    assert result['village']['centre'] is None
    assert result['linked_count'] == 0 and result['context_count'] == 1
    assert result['features'][0]['properties']['relationship'] == 'district_context'
    assert result['pipelines_available'] is False
    assert client.get('/api/v1/villages/MISSING/water-map', headers=headers['a']).status_code == 404


def test_reviewed_source_crosswalk_preserves_remote_supply_connection(setup, monkeypatch, tmp_path):
    client, factory, headers = setup
    install_snapshot(monkeypatch, tmp_path, [feature('REMOTE-SUPPLY', district='Elsewhere')])
    with factory() as db:
        db.add(Record(kind='geography', key='TEST-A', payload={'crosswalks': {'water_asset_ids': ['REMOTE-SUPPLY']}, 'source': 'TEST official evidence'}))
        db.commit()
    result = client.get('/api/v1/villages/TEST-A/water-map', headers=headers['a']).json()
    assert result['linked_count'] == 1
    assert result['features'][0]['properties']['relationship'] == 'reviewed_connection'


def test_viewport_filter_and_bad_bounds(setup, monkeypatch, tmp_path):
    client, _, headers = setup
    install_snapshot(monkeypatch, tmp_path, [feature('IN'), feature('OUT', coordinates=(79, 21))])
    result = client.get('/api/v1/water-data/map?bbox=74,18,75,19', headers=headers['f']).json()
    assert [f['properties']['id'] for f in result['features']] == ['IN']
    for bbox in ['nan,18,75,19', '75,19,74,18', 'hello']:
        assert client.get('/api/v1/water-data/map?bbox=' + bbox, headers=headers['f']).status_code == 422


def test_pipeline_only_district_view_retains_geographic_context(setup, monkeypatch, tmp_path):
    client, _, headers = setup
    pipe = feature('INDUSTRIAL-PIPE', district='', kind='industrial_pipeline')
    install_snapshot(monkeypatch, tmp_path, [feature('DISTRICT-WELL')], [pipe])
    result = client.get('/api/v1/water-data/map?district=Test&kinds=industrial_pipeline', headers=headers['f']).json()
    assert [f['properties']['id'] for f in result['features']] == ['INDUSTRIAL-PIPE']
    assert result['features'][0]['properties']['relationship'] != 'reviewed_connection'


def test_curated_pipeline_requires_connection_evidence(setup, monkeypatch, tmp_path):
    client, _, headers = setup
    install_snapshot(monkeypatch, tmp_path, [])
    pipe = feature('PIPE', district='Elsewhere', kind='pipeline')
    pipe['properties'].update(relationship='reviewed_connection', village_ids=['TEST-A'])
    path = tmp_path / 'reviewed-network.geojson'
    path.write_text(json.dumps({'features': [pipe]}))
    assert client.get('/api/v1/villages/TEST-A/water-map', headers=headers['a']).json()['linked_count'] == 0
    pipe['properties']['connection_evidence'] = 'TEST reviewed scheme map and supply relationship'
    path.write_text(json.dumps({'features': [pipe]}))
    result = client.get('/api/v1/villages/TEST-A/water-map', headers=headers['a']).json()
    assert result['pipelines_available'] is True and result['linked_count'] == 1


def test_csv_uses_chronology_preserves_units_and_rejects_2011(tmp_path):
    path = tmp_path / 'observations.csv'
    fields = ['Station', 'Agency', 'State', 'District', 'Latitude', 'Longitude', 'Data Acquisition Time', 'Flow (cusec)']
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for date, value in [('30-09-2026 10:00', '4'), ('01-10-2026 10:00', '9'), ('02-10-2026 10:00', ''), ('01-01-2011 10:00', '999')]:
            writer.writerow(dict(zip(fields, ['TEST', 'TEST agency', 'Maharashtra', 'Test', '18.2', '74.4', date, value])))
    features, stats = parse_resource({'id': 'TEST', 'agency': 'TEST', 'kind': 'canal', 'catalogue_url': 'https://fixture.test', 'url': 'https://fixture.test/data'}, path)
    props = next(iter(features.values()))['properties']
    assert props['measurements'][0]['value'] == 9
    assert props['measurements'][0]['units'] == 'cusec'
    assert props['observed_at'].startswith('2026-10-01')
    assert stats['rejected_rows'] == 1


def test_manual_well_mapping_keeps_below_ground_units_and_does_not_join_village_name(tmp_path):
    path = tmp_path / 'manual.csv'
    path.write_text('Well ID,Agency,State Name ,District Name ,Village ,Latitude ,Longitude ,Date of Monitoring,"Water Level, m bgl"\nTEST,TEST,Maharashtra,Test,TEST VILLAGE,18.2,74.4,01-01-2011,999\nTEST,TEST,Maharashtra,Test,TEST VILLAGE,18.2,74.4,01-01-2025,5\n')
    features, stats = parse_resource({'id': 'TEST', 'agency': 'TEST', 'kind': 'groundwater', 'catalogue_url': 'https://fixture.test', 'url': 'https://fixture.test/data'}, path)
    item = next(iter(features.values()))['properties']
    assert item['measurements'][0]['units'] == 'm bgl' and item['measurements'][0]['value'] == 5
    assert item['village_ids'] == [] and item['source_village_text'] == 'TEST VILLAGE'
    assert stats['rejected_rows'] == 1


def test_official_refresh_is_operator_only_and_prevents_duplicates(setup, monkeypatch, tmp_path):
    from services.api import water_map
    client, _, headers = setup
    install_snapshot(monkeypatch, tmp_path, [])
    monkeypatch.setattr(water_map, '_refresh_process', None)
    class Process:
        def poll(self):
            return None
    calls = []
    def launch(command, **kwargs):
        calls.append(command)
        assert command[1:] == ['-m', 'scripts.sync_water_data']
        return Process()
    monkeypatch.setattr(water_map.subprocess, 'Popen', launch)
    path = '/api/v1/admin/water-data/refresh'
    assert client.post(path, headers=headers['f']).status_code == 403
    assert client.post(path, headers=headers['a']).status_code == 403
    assert client.post(path, headers=headers['s']).status_code == 202
    assert client.post(path, headers=headers['s']).status_code == 409
    assert len(calls) == 1
    assert client.get('/api/v1/water-data/refresh-status', headers=headers['a']).json()['running'] is True


def test_training_export_excludes_2011_and_current_year(monkeypatch, tmp_path):
    from scripts import export_water_training
    import sys
    monkeypatch.chdir(tmp_path)
    root = tmp_path / 'data/water'
    root.mkdir(parents=True)
    (root / 'catalogue.json').write_text(json.dumps({'resources': [{'id': 'TEST', 'url': 'https://fixture.test'}]}))
    raw = tmp_path / 'raw.csv'
    raw.write_text('State,Data Acquisition Time,Value\nMaharashtra,01-01-2011 00:00,999\nMaharashtra,01-01-2021 00:00,5\nMaharashtra,01-01-2026 00:00,7\n')
    monkeypatch.setattr(export_water_training, 'download', lambda resource: (raw, {'sha256': 'TEST-SOURCE'}))
    output = tmp_path / 'filtered.csv'
    monkeypatch.setattr(sys, 'argv', ['export', 'TEST', '--before', '2026-01-01', '--output', str(output)])
    export_water_training.main()
    rows = list(csv.DictReader(output.open()))
    assert len(rows) == 1 and rows[0]['Value'] == '5'
    receipt = json.loads(output.with_suffix('.metadata.json').read_text())
    assert receipt['exported_rows'] == 1 and receipt['excluded_rows'] == 2


def review_payload(asset='TEST-SOURCE'):
    today = datetime.now(timezone.utc).date()
    return {'asset_id': asset, 'source_name': 'TEST authority source', 'kind': 'groundwater',
            'scheme_id': 'TEST-SCHEME', 'connection_status': 'documented', 'evidence_method': 'official_scheme_record',
            'evidence_url': 'https://fixture.test/authority-plan', 'evidence_note': 'TEST scheme identifies this source and the village service area.',
            'evidence_date': today.isoformat(), 'valid_until': (today + timedelta(days=30)).isoformat()}


def test_source_review_permissions_versioning_and_no_delivery_inference(setup, monkeypatch, tmp_path):
    client, factory, headers = setup
    install_snapshot(monkeypatch, tmp_path, [feature('TEST-SOURCE', district='Elsewhere')])
    path = '/api/v1/admin/villages/TEST-A/water-connections'
    body = review_payload()
    assert client.post(path, headers=headers['f'], json=body).status_code == 403
    assert client.post(path, headers=headers['o2'], json=body).status_code == 403
    assert client.post(path, headers=headers['o'], json=body).status_code == 200
    assert client.post(path, headers=headers['a'], json=body).status_code == 409
    result = client.get('/api/v1/villages/TEST-A/water-map', headers=headers['f']).json()
    assert result['linked_count'] == 1
    assert result['verification']['recent_delivery_readings'] == 0
    assert result['connection_reviews'][0]['effective_delivery_status'] == 'unknown'
    assert result['verification']['supply_prediction_ready'] is False
    body.update(expected_version=1, connection_status='not_connected')
    assert client.post(path, headers=headers['a'], json=body).status_code == 200
    result = client.get('/api/v1/villages/TEST-A/water-map', headers=headers['a']).json()
    assert result['linked_count'] == 0
    assert result['features'][0]['properties']['relationship'] == 'not_connected'
    with factory() as db:
        from sqlalchemy import select
        assert len(list(db.scalars(select(Record).where(Record.kind == 'water_connection')))) == 2


def test_early_review_keys_remain_visible_and_update_without_duplicate_connections(setup, monkeypatch, tmp_path):
    import hashlib
    client, factory, headers = setup
    install_snapshot(monkeypatch, tmp_path, [])
    body = review_payload()
    with factory() as db:
        db.add(Record(kind='water_connection', key=hashlib.sha256(b'TEST-A|TEST-SOURCE').hexdigest(),
            payload={**body, 'village_id': 'TEST-A', 'delivery_status': 'unknown'}))
        db.commit()
    path = '/api/v1/villages/TEST-A/water-map'
    assert client.get(path, headers=headers['a']).json()['linked_count'] == 1
    assert client.post('/api/v1/admin/villages/TEST-A/water-connections', headers=headers['a'],
        json={**body, 'expected_version': 1}).status_code == 200
    result = client.get(path, headers=headers['a']).json()
    assert result['linked_count'] == 1 and len(result['connection_reviews']) == 1
    assert result['connection_reviews'][0]['version'] == 2


def test_delivery_requires_measured_evidence_and_old_reading_is_unknown(setup, monkeypatch, tmp_path):
    client, _, headers = setup
    install_snapshot(monkeypatch, tmp_path, [])
    path = '/api/v1/admin/villages/TEST-A/water-connections'
    body = {**review_payload(), 'delivery_status': 'measured'}
    assert client.post(path, headers=headers['a'], json=body).status_code == 422
    body.update(delivered_litres_per_day=0, delivery_observed_at=(datetime.now(timezone.utc)-timedelta(days=3)).isoformat(),
                delivery_evidence_url='https://fixture.test/delivery-meter', delivery_method='TEST dated inlet meter daily total')
    assert client.post(path, headers=headers['a'], json=body).status_code == 200
    result = client.get('/api/v1/villages/TEST-A/water-map', headers=headers['a']).json()
    assert result['features'][0]['geometry'] is None  # Never place an unlocated source at the village pin.
    assert result['connection_reviews'][0]['delivered_litres_per_day'] == 0
    assert result['connection_reviews'][0]['effective_delivery_status'] == 'unknown'
    body.update(expected_version=1, delivery_observed_at=datetime.now(timezone.utc).isoformat())
    assert client.post(path, headers=headers['a'], json=body).status_code == 200
    result = client.get('/api/v1/villages/TEST-A/water-map', headers=headers['a']).json()
    assert result['verification']['recent_delivery_readings'] == 1
    assert result['connection_reviews'][0]['effective_delivery_status'] == 'measured'
    assert result['village']['centre'] is None


def test_expired_review_overrides_legacy_crosswalk_and_rejects_old_or_partial_evidence(setup, monkeypatch, tmp_path):
    client, factory, headers = setup
    install_snapshot(monkeypatch, tmp_path, [feature('TEST-SOURCE')])
    path = '/api/v1/admin/villages/TEST-A/water-connections'
    body = review_payload()
    for changes in [{'evidence_date': '2011-01-01'}, {'latitude': 18.2}, {'delivery_status': 'reported_stopped'}, {'evidence_url': 'javascript:alert(1)'}]:
        assert client.post(path, headers=headers['s'], json={**body, **changes}).status_code == 422
    from services.api.water_evidence import review_key
    with factory() as db:
        db.add(Record(kind='geography', key='TEST-A', payload={'crosswalks': {'water_asset_ids': ['TEST-SOURCE']}}))
        db.add(Record(kind='water_connection', key=review_key('TEST-A','TEST-SOURCE'), payload={**body, 'village_id': 'TEST-A',
            'delivery_status': 'unknown', 'valid_until': '2021-01-01'}))
        db.commit()
    result = client.get('/api/v1/villages/TEST-A/water-map', headers=headers['a']).json()
    assert result['linked_count'] == 0
    assert result['features'][0]['properties']['relationship'] == 'unverified_connection'


def test_additional_reservoirs_keep_missing_values_unknown_and_unlocated_records_off_map():
    from scripts.sync_additional_water import parse_dams
    row = {'dam_id': 'TEST', 'dam_name_en': 'TEST', 'date': '2026-11-02', 'lat': '18.2', 'lng': '74.4',
           'live_storage_mcum': '0', 'level_rl': None, 'rainfall_mm': None}
    features, report = parse_dams({'data': [row, {**row, 'lat': None}], 'total': 2})
    assert report['mapped'] == 1 and report['unlocated'] == 1
    assert features[0]['properties']['measurements'][0]['value'] == 0
    assert len(features[0]['properties']['measurements']) == 1
    assert features[0]['properties']['prediction_use'] is False
