import hashlib
import json
from datetime import date

import httpx
import pytest

from scripts import collect_remaining_public_supply as collector
from scripts.extract_public_supply import count_value, dates_in, summarize_sheet


def test_dates_do_not_promote_upload_years_or_future_and_old_dates():
    today = date(2026, 11, 4)
    assert dates_in('दिनांक: २५-१०-२०२६', today) == {'2026-10-25'}
    assert not dates_in('25-10-26 31-02-2026 01-01-2011 25-11-2026', today)
    assert dates_in('2026-10-25', today) == set()  # Not the source DMY convention.


def test_trip_totals_preserve_missing_zero_and_exclude_summary_rows_and_pii():
    rows = [
        (None, 'दिनांक: २५-१०-२०२६'),
        ('अ. क्र.', 'Name', 'शेड्यूलनुसार खेपा', 'आवश्यकतेनुसार खेपा'),
        (1, 'PRIVATE RECIPIENT MUST NOT LEAVE INPUT', 0, None),
        (2, 'PRIVATE PHONE MUST NOT LEAVE INPUT', '२', '३'),
        ('एकूण', None, 999, 999),
    ]
    result = summarize_sheet(rows, today=date(2026, 11, 4))
    assert result['content_date'] == '2026-10-25' and result['date_usable']
    assert result['recipient_rows'] == 2
    assert result['reported_scheduled_trips_sum'] == 2
    assert result['reported_required_trips_sum'] == 3
    assert result['scheduled_cells_present'] == 2 and result['required_cells_present'] == 1
    assert 'PRIVATE' not in json.dumps(result)
    assert result['delivered_litres'] is None and result['urgency_label'] is None
    assert not result['completed_dispatches_verified'] and not result['prediction_use']


def test_date_conflict_and_bad_counts_remain_visible():
    rows = [('Date: 25-10-2026',), ('अ.क्र.', 'शेड्यूलनुसार खेपा', 'आवश्यकतेनुसार खेपा'),
            (1, -1, '=SUM(A1)'), (1, None, None)]
    result = summarize_sheet(rows, title='26-10-2026', today=date(2026, 11, 4))
    assert result['date_conflict'] and not result['date_usable']
    assert result['duplicate_serial_rows'] == 1 and result['invalid_trip_cells'] == 2
    assert result['reported_scheduled_trips_sum'] is None
    assert result['reported_required_trips_sum'] is None


@pytest.mark.parametrize('value', [-1, 1.5, True, 'unknown', '=A1', 'one'])
def test_invalid_trip_count_is_not_imputed(value):
    with pytest.raises(ValueError):
        count_value(value)


def test_cache_checks_request_and_content_and_does_not_accept_html_as_json(tmp_path, monkeypatch):
    path = tmp_path/'source.json'
    calls = []
    client_class = httpx.Client
    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={'value': request.url.params['day']})
    monkeypatch.setattr(collector.httpx, 'Client', lambda **kwargs: client_class(
        **kwargs, transport=httpx.MockTransport(respond)))
    collector.fetch(path, 'https://fixture.test/source', params={'day': 1})
    collector.fetch(path, 'https://fixture.test/source', params={'day': 1})
    assert len(calls) == 1
    collector.fetch(path, 'https://fixture.test/source', params={'day': 2})
    assert len(calls) == 2 and json.loads(path.read_bytes())['value'] == '2'
    path.write_text('{"tampered":true}')
    _, receipt = collector.fetch(path, 'https://fixture.test/source', params={'day': 2})
    assert len(calls) == 3 and hashlib.sha256(path.read_bytes()).hexdigest() == receipt['sha256']
    monkeypatch.setattr(collector.httpx, 'Client', lambda **kwargs: client_class(
        **kwargs, transport=httpx.MockTransport(lambda request: httpx.Response(200, text='<html>login</html>'))))
    with pytest.raises(ValueError):
        collector.fetch(path, 'https://fixture.test/source', params={'day': 3})
    assert not path.with_suffix('.json.part').exists()
    assert json.loads(path.read_bytes())['value'] == '2'
