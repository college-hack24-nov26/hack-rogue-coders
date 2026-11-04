from datetime import date, datetime, timedelta

import pytest

from services.worker.supply_features import IST, build_examples, derive_fields, sensitivity
from scripts.collect_supply_evidence import CFS_TO_CMS, resource_daily, summarize_iot


def field(value, unit='litres', basis='measured', available='2025-01-02T00:00:00+05:30', **kwargs):
    return {'value':value, 'unit':unit, 'basis':basis, 'source':'TEST evidence',
            'method':'TEST complete calibrated meter interval', 'available_at':available, **kwargs}


def test_formula_lineage_no_default_loss_or_dead_storage_or_silent_override():
    values = {'population':field(1000, 'people', observed_on='2025-01-01'),
        'household_lpcd':field(55, 'litres/person/day', basis='assumed'),
        'flow_lps':field(5, 'litres/second'), 'runtime_hours':field(4, 'hours/day'),
        'tank_capacity_m3':field(100, 'm3'), 'tank_fill_fraction':field(.5, 'fraction')}
    r = derive_fields(values)
    assert r['household_demand_litres']['value'] == 55000
    assert r['household_demand_litres']['inputs']['household_lpcd']['basis'] == 'assumed'
    assert r['gross_inflow_litres']['value'] == 72000
    assert 'net_inflow_litres' not in r and 'storage_litres' not in r
    values.update(loss_fraction=field(.2, 'fraction', basis='assumed'), dead_storage_m3=field(5, 'm3'))
    r = derive_fields(values)
    assert r['net_inflow_litres']['value'] == 57600 and r['storage_litres']['value'] == 45000
    values['net_inflow_litres'] = field(123)
    assert derive_fields(values)['net_inflow_litres']['value'] == 123
    assert 'demand_litres' not in r  # No silently omitted sectors.


def test_irrigation_and_capture_require_parameters_and_do_not_become_supply_or_truth():
    data = {k:field(v, u) for k,v,u in [('area_ha',2,'ha'),('et0_mm',5,'mm/day'),('kc',1.2,'coefficient'),
        ('effective_rain_mm',1,'mm/day'),('soil_contribution_mm',0,'mm/day'),('irrigation_efficiency',.5,'fraction'),
        ('rain_mm',10,'mm/day'),('roof_area_m2',100,'m2'),('runoff_coefficient',.8,'fraction'),('capture_efficiency',.75,'fraction')]}
    r = derive_fields(data)
    assert r['agriculture_demand_litres']['value'] == 200000
    assert r['rain_capture_litres']['value'] == 600
    assert 'net_inflow_litres' not in r and 'unmet_litres' not in r
    with pytest.raises(ValueError):derive_fields({'loss_fraction':field(1.1, 'fraction')})
    with pytest.raises(ValueError):derive_fields({'population':field(1000, 'people', observed_on='2011-01-01')})
    with pytest.raises(ValueError):derive_fields({'dead_storage_m3':field(100, 'm3'),
        'tank_capacity_m3':field(10, 'm3'), 'tank_fill_fraction':field(.1, 'fraction')})


def test_preknown_norm_estimates_can_be_features_but_full_daily_measurements_cannot_arrive_early():
    from services.worker.supply_features import validate_record
    values=derive_fields({'population':field(1000,'people',observed_on='2025-01-01'),
        'household_lpcd':field(55,'litres/person/day',basis='assumed')})
    validate_record({'village_id':'TEST:1','scope':'household','date':'2025-02-01','fields':values})
    with pytest.raises(ValueError):
        validate_record({'village_id':'TEST:1','scope':'household','date':'2025-02-01',
                         'fields':{'delivered_litres':field(100)}})


def record(day, shortage=0, basis='measured', late=False):
    available = datetime.combine(day+timedelta(days=1), datetime.min.time(), IST).isoformat()
    return {'village_id':'TEST:001', 'scope':'whole_village', 'date':day.isoformat(), 'complete_day':True, 'coverage_verified':True,
            'fields':{'delivered_litres':field(100, available=available), 'demand_litres':field(100, available=available),
                'net_inflow_litres':field(90, available=available), 'closing_storage_litres':field(200, available=available),
                'unmet_litres':field(shortage, basis=basis, available='2026-12-01T00:00:00+05:30' if late else available)}}


def test_seven_fifteen_labels_and_feature_cutoff_future_values_never_enter_features():
    issue = date(2025, 2, 1)
    records = [record(issue+timedelta(days=i), shortage=10 if i == 10 else 0) for i in range(-15,15)]
    records[-1]['fields']['delivered_litres']['value'] = 99999999
    seven,fifteen = build_examples(records, issue)
    assert seven['label_enough'] is True and fifteen['label_enough'] is False
    assert fifteen['label_shortage_litres'] == 10
    assert seven['features']['delivered_litres_previous_15d_mean'] == 100
    assert seven['supervised_eligible'] and seven['split'] == 'train'


def test_missing_estimated_or_not_yet_available_targets_remain_unknown_and_split_is_purged():
    issue = date(2025, 12, 25)
    records = [record(issue+timedelta(days=i)) for i in range(-15,15)]
    seven,fifteen = build_examples(records, issue)
    assert seven['split'] == 'train' and fifteen['split'] == 'purged_at_split'
    assert not fifteen['supervised_eligible']
    records[-1]['fields']['unmet_litres']['basis'] = 'derived'
    assert build_examples(records, issue)[1]['label_enough'] is None
    records[-1] = record(issue+timedelta(days=14), late=True)
    assert build_examples(records, issue, as_of=datetime(2026,2,1,tzinfo=IST))[1]['label_enough'] is None
    records[0]['fields']['delivered_litres']['available_at'] = '2026-12-01T00:00:00+05:30'
    r = build_examples(records, issue)[0]
    assert r['features']['delivered_litres_previous_15d_count'] == 14
    assert r['features']['delivered_litres_previous_15d_mean'] is None
    with pytest.raises(ValueError):build_examples(records+[records[0]], issue)


def test_bounds_show_assumption_sensitivity_without_fake_probability():
    r = sensitivity([100,120], [90,110], [100,200], 500, 120)
    assert r['outlooks'][0]['status'] == 'sensitive_to_assumptions'
    assert r['outlooks'][0]['shortage_range_litres'] == [0,110]
    assert sensitivity([100,100],[150,150],[0,0],0,100)['outlooks'][1]['status'] == 'enough_in_tested_bounds'
    assert sensitivity([100,100],[0,0],[0,0],0,100)['outlooks'][1]['status'] == 'short_in_tested_bounds'


def test_shortage_formula_can_label_actual_balance_but_norm_estimates_never_become_truth():
    issue=date(2025,2,1)
    records=[record(issue+timedelta(days=i)) for i in range(-15,15)]
    for r in records:
        del r['fields']['unmet_litres']
        r['fields']['demand_litres']['value']=120
        r['fields']=derive_fields(r['fields'])
        r['demand_independent_of_supply_verified']=True
    assert build_examples(records,issue)[1]['label_shortage_litres']==300
    records[-1]['demand_independent_of_supply_verified']=False
    assert build_examples(records,issue)[1]['label_enough'] is None
    records[-1]['demand_independent_of_supply_verified']=True
    records[-1]['fields']['unmet_litres']['inputs']['demand_litres']['basis']='assumed'
    assert build_examples(records,issue)[1]['label_enough'] is None


def test_official_flow_units_duplicate_conflicts_no_interpolation_or_village_litres(tmp_path):
    import hashlib
    p=tmp_path/'flow.csv'
    p.write_text('Station,Agency,State,District,Latitude,Longitude,Data Acquisition Time,Gate-1 Discharge (cusec)\n'
        'A,SW,Maharashtra,TEST,18,75,01-01-2025 00:00,1\n'
        'A,SW,Maharashtra,TEST,18,75,01-01-2025 00:00,1\n'
        'A,SW,Maharashtra,TEST,18,75,01-01-2025 01:00,3\n'
        'A,SW,Maharashtra,TEST,18,75,01-01-2025 01:00,5\n'
        'A,SW,Maharashtra,TEST,18,75,01-01-2011 00:00,999\n'
        'A,SW,Maharashtra,TEST,18,75,03-01-2025 00:00,0\n')
    rows,rejected=resource_daily({'id':'TEST','url':'https://fixture.test/flow'},p,
        {'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'retrieved_at':'2026-11-04T00:00:00+05:30'},date(2026,11,4))
    assert len(rows)==2 and rows[0]['observed_sample_mean']==CFS_TO_CMS
    assert rows[0]['sample_count']==1 and rejected['conflicting_parameter_timestamp']==1
    assert rows[1]['lag_1d'] is None and rows[1]['observed_sample_mean']==0
    assert all(r['village_delivered_litres'] is None and r['publication_available_at'] is None for r in rows)


def test_public_pilot_missing_maharashtra_not_interpreted_as_zero_delivery(tmp_path):
    import json
    p=tmp_path/'iot.json'
    p.write_text(json.dumps({'d':json.dumps([[{'StateName':'Gujarat','VillageId':'1'}],[{'VillageId':'1','Date':'TEST','Value':1}]])}))
    r=summarize_iot(p)
    assert r['maharashtra_rows']==0 and r['maharashtra_dated_readings']==0 and r['prediction_use'] is False
