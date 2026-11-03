import json
from pathlib import Path

import httpx
import pytest

from scripts import collect_water_history as history


def test_ranges_reject_truncation_changed_entity_and_ignored_range():
    for headers, body, status in [
        ({'content-range': 'bytes 0-3/10', 'etag': '"stable"'}, b'ab', 206),
        ({'content-range': 'bytes 0-3/10', 'etag': '"changed"'}, b'abcd', 206),
        ({'etag': '"stable"'}, b'abcd', 200),
        ({'content-range': 'bytes 1-4/10', 'etag': '"stable"'}, b'abcd', 206),
    ]:
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status, headers=headers, content=body))) as client:
            with pytest.raises(ValueError):
                history.range_bytes(client, 'https://fixture.test/archive.csv', 0, 3, '"stable"', 10)
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(206, headers={'content-range': 'bytes 0-3/10', 'etag': '"stable"'}, content=b'abcd'))) as client:
        data, size, etag = history.range_bytes(client, 'https://fixture.test/archive.csv', 0, 3, '"stable"', 10)
    assert data == b'abcd' and size == 10 and etag == '"stable"'


def test_history_exports_only_2021_onward_before_holdout_without_imputation(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    raw = tmp_path / 'history.csv'
    raw.write_text('State,Data Acquisition Time,Flow (cusec)\nMaharashtra,01-01-2011 10:00,999\nMaharashtra,02-01-2021 10:00,0\nMaharashtra,03-01-2021 10:00,\nMaharashtra,01-01-2026 10:00,7\nGujarat,01-01-2022 10:00,5\nMaharashtra,bad,4\n')
    monkeypatch.setattr(history, 'download_chunks', lambda entry: (raw, {'sha256': 'TEST', 'bytes': raw.stat().st_size}))
    result = history.collect({'id': 'TEST', 'name': 'TEST', 'url': 'https://fixture.test/history'})
    assert result['status'] == 'profiled' and result['exported_rows'] == 2
    assert result['outside_state_rows'] == 1 and result['invalid_dates'] == 1
    output = Path(result['export_path']).read_text()
    assert '2011' not in output and '2026' not in output
    assert '02-01-2021 10:00,0' in output and '03-01-2021 10:00,\n' in output
    assert result['quality_status'] == 'candidate_only'


def test_reviewed_legacy_encoding_and_manual_date_column_preserve_text_and_filter_old_years(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    raw = tmp_path / 'legacy.csv'
    raw.write_bytes(b'State Name ,Date of Monitoring,Village ,Water Level\nMaharashtra,01-01-2011,TEST\xae,99\nMaharashtra,01-01-2022,TEST\xae,0\n')
    monkeypatch.setattr(history, 'ENCODINGS', {'TEST': 'cp1252'})
    monkeypatch.setattr(history, 'download_chunks', lambda entry: (raw, {'sha256': 'TEST', 'bytes': raw.stat().st_size}))
    result = history.collect({'id': 'TEST', 'name': 'TEST', 'url': 'https://fixture.test/history'})
    assert result['exported_rows'] == 1 and result['source_encoding'] == 'cp1252'
    output = Path(result['export_path']).read_text(encoding='utf-8')
    assert 'TEST\u00ae,0' in output and '2011' not in output
