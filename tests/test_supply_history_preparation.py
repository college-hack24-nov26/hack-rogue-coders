from datetime import date, timedelta

from scripts.aggregate_supply_history import district_key, metric_family
from scripts.prepare_history_simulation import archived_features, climate_drivers, historical_partition


def test_archived_features_exclude_future_and_assumed_publication_gap():
    issue = date(2024, 6, 10)
    values = {issue-timedelta(days=2):{'daily_rain_mm':0},
              issue-timedelta(days=3):{'daily_rain_mm':4},
              issue-timedelta(days=1):{'daily_rain_mm':1000},
              issue:{'daily_rain_mm':2000}}
    features = archived_features(values, issue)
    assert features['archive_daily_rain_mm_lag2'] == 0
    assert features['archive_daily_rain_mm_prior7_mean'] == 2
    assert features['archive_daily_rain_mm_prior7_days'] == 2
    assert 'archive_air_temperature_c_lag2' not in features


def test_historical_rain_missingness_and_known_zero_remain_distinct():
    issue=date(2024,6,10)
    rows={issue-timedelta(days=2):{'daily_rain_mm':0},
          issue-timedelta(days=1):{'daily_rain_mm':100},
          issue:{'daily_rain_mm':10}}
    fallback=[{'rain':2,'temp_avg':29,'district_code_as_reported':527}]
    drivers,counts=climate_drivers(rows,issue,fallback)
    assert drivers[28]['rain']==0 and drivers[28]['rain_basis']=='archive_daily_rain'
    assert drivers[29]['rain']==2 and drivers[29]['rain_basis']=='illustrative_pocra_template'
    assert drivers[30]['rain']==10  # Follow-up forcing, never a predictor.
    assert counts['actual_rain_days']==2 and counts['fallback_rain_days']==43


def test_history_split_purges_training_horizons_and_keeps_context_types_separate():
    assert historical_partition(date(2024,12,2))=='train'
    assert historical_partition(date(2024,12,3)) is None
    assert historical_partition(date(2025,1,1))=='validation'
    assert district_key('Osmanabad')==district_key('Dharashiv')
    assert district_key('Ahmadnagar')==district_key('Ahilyanagar')
    assert metric_family('Telemetry Hourly Rainfall (mm)','weather')=='rain_sample_mm'
    assert metric_family('Manual Daily Rainfall (mm)','weather')=='daily_rain_mm'
    assert metric_family('Water Level, m bgl','groundwater')=='groundwater_level_change_m'
