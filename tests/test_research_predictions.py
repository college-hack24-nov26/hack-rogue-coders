from services.api.db import Record
from datetime import datetime
from zoneinfo import ZoneInfo


def test_station_replay_is_scoped_and_does_not_publish_outlook(setup):
    client, factory, headers = setup
    with factory() as db:
        db.add(Record(kind='research_predictions', key='scope-a', payload={
            'status': 'historical_research', 'operational': False, 'approved': False,
            'samples': [{'station_fingerprint': 'fixture-station',
                         'horizons': [{'day': day, 'predicted': float(day)} for day in range(1, 16)]}]}))
        db.commit()
    path = '/api/v1/admin/villages/TEST-A/research-predictions'
    result = client.get(path+'?days=7', headers=headers['a'])
    assert result.status_code == 200
    assert result.json()['operational'] is False
    assert result.json()['approved'] is False
    assert len(result.json()['samples'][0]['horizons']) == 7
    assert len(client.get(path+'?days=15', headers=headers['a']).json()['samples'][0]['horizons']) == 15
    assert client.get(path, headers=headers['f']).status_code == 403
    assert client.get(path.replace('TEST-A', 'TEST-B'), headers=headers['a']).status_code == 403
    assert client.get('/api/v1/villages/TEST-A/outlook', headers=headers['f']).json()['status'] == 'unavailable'


def test_missing_station_data_is_not_replaced_with_another_district(setup):
    client, _, headers = setup
    result = client.get('/api/v1/admin/villages/TEST-B/research-predictions', headers=headers['s'])
    assert result.status_code == 200
    assert result.json()['status'] == 'unavailable'
    assert result.json()['samples'] == []
    assert client.get('/api/v1/admin/villages/TEST-A/research-predictions?days=3', headers=headers['a']).status_code == 422


def test_experimental_preview_keeps_dates_and_hides_old_runs(setup):
    client, factory, headers = setup
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat()
    with factory() as db:
        db.add(Record(kind='research_predictions', key='scope-a', payload={'samples': []}))
        row = Record(kind='experimental_forecasts', key='scope-a', payload={
            'operational': False, 'forecast_date': today,
            'samples': [{'horizons': [{'day': d, 'actual': None} for d in range(1, 16)]}]})
        db.add(row)
        db.commit()
        record_id = row.id
    path = '/api/v1/admin/villages/TEST-A/research-predictions?days=7'
    response = client.get(path, headers=headers['a'])
    assert response.status_code == 200
    preview = response.json()['experimental_current']
    assert preview['forecast_date'] == today and preview['operational'] is False
    assert len(preview['samples'][0]['horizons']) == 7
    assert preview['samples'][0]['horizons'][0]['actual'] is None
    with factory() as db:
        row = db.get(Record, record_id)
        row.payload = {**row.payload, 'forecast_date': '2000-01-01'}
        db.commit()
    assert client.get(path, headers=headers['a']).json()['experimental_current'] is None
