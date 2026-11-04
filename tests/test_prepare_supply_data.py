from datetime import date

import pytest

from scripts.prepare_supply_data import preceding_features, prepare_profiles, prepare_weather


def test_calendar_lags_exclude_issue_day_and_do_not_interpolate_missing_dates():
    days = {date(2026, 10, d): {'rain_mm': float(d)} for d in range(1, 10)}
    result = preceding_features(days, date(2026, 10, 9), ('rain_mm',))
    assert result['rain_mm_lag_1d'] == 8
    assert result['rain_mm_previous_7d_count'] == 7
    assert result['rain_mm_previous_7d_mean'] == 5
    del days[date(2026, 10, 5)]
    result = preceding_features(days, date(2026, 10, 9), ('rain_mm',))
    assert result['rain_mm_previous_7d_count'] == 6
    assert result['rain_mm_previous_7d_mean'] is None
    assert result['rain_mm_previous_15d_mean'] is None


def test_profile_zero_and_missing_targets_stay_distinct_and_duplicates_fail():
    row = {'jjm_village_id': '123', 'reported_households': 0, 'reported_tap_connections': 0,
           'village_name': 'TEST ONLY', 'district': 'TEST', 'jjm_district_code': '1',
           'census_code_as_reported': '0', 'observed_on': None, 'retrieved_at': '2026-11-04T00:00:00Z',
           'basis': 'administrative_snapshot_measurement_vintage_unknown', 'source_url': 'https://fixture.test',
           'raw_sha256': 'test-only'}
    result = list(prepare_profiles([row]))[0]
    assert result['features']['reported_households'] == 0
    assert result['features']['reported_tap_coverage_fraction'] is None
    assert result['label_7d'] is None and not result['supervised_eligible']
    assert result['observed_on'] is None
    with pytest.raises(ValueError, match='Duplicate'):
        list(prepare_profiles([row, row]))


def test_weather_retains_spatial_scope_availability_and_zero_without_guessing_wind():
    row = {'for_date': '2026-11-02', 'district_code_as_reported': 527, 'district': 'TEST',
           'rain': 0, 'temp_avg': 24, 'rh_avg': None, 'wind_avg': 100,
           'source_url': 'https://fixture.test', 'retrieved_at': '2026-11-04T00:00:00Z',
           'basis': 'publisher_district_weather'}
    result = list(prepare_weather([row], date(2026, 11, 4)))[0]
    assert result['observations'] == {'rain_mm': 0, 'temperature_c': 24, 'humidity_percent': None}
    assert not result['historical_feature_availability_verified']
    assert result['historical_publication_time'] is None
    assert result['spatial_scope'] == 'district' and not result['village_connection_verified']
    with pytest.raises(ValueError, match='Duplicate'):
        list(prepare_weather([row, row], date(2026, 11, 4)))
