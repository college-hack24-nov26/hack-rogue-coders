import csv
import json
import socket
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from scripts.train_supply_offline import from_csv, main, read_operations, split_examples
from services.worker.supply_features import IST


def report_at(output):
    latest=json.loads((output/'latest-run.json').read_text(encoding='utf-8'))
    return Path(latest['run_directory']),json.loads(Path(latest['report']).read_text(encoding='utf-8'))


def test_empty_local_folder_reports_missing_targets_and_never_calls_network(tmp_path,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('Offline trainer tried to access network')
    monkeypatch.setattr(socket.socket,'connect',forbidden)
    operations=tmp_path/'operations';operations.mkdir()
    output=tmp_path/'models'
    assert main(['--operations',str(operations),'--output',str(output)])==2
    folder,r=report_at(output)
    assert r['model_trained'] is False and r['operation_records']==0
    assert r['network_calls']==0 and r['database_access'] is False
    assert r['drought_intensity']['included_in_training'] is False
    assert r['status']=='blocked_missing_measured_supply_training_data'
    assert not list(folder.glob('supply-*d.json'))


def test_csv_zero_is_real_missing_stays_missing_and_basis_is_not_guessed(tmp_path):
    path=tmp_path/'daily.csv'
    headers=['village_id','date','scope','available_at','basis','evidence_source','measurement_method',
             'complete_day','coverage_verified','net_inflow_litres','unmet_litres']
    with path.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(headers);w.writerow(['TEST:ONLY','2025-01-01','whole_village',
            '2025-01-02T00:00:00+05:30','measured','TEST meter log','TEST calibrated daily meter','true','true','0',''])
    rows,receipts=read_operations([path],datetime.now(IST))
    assert rows[0]['fields']['net_inflow_litres']['value']==0
    assert 'unmet_litres' not in rows[0]['fields'] and receipts[0]['records']==1
    row=dict(zip(headers,['TEST:ONLY','2025-01-01','whole_village','2025-01-02T00:00:00+05:30',
                         '','TEST','TEST','true','true','5','']))
    with pytest.raises(ValueError):
        from services.worker.supply_features import validate_record
        validate_record(from_csv(row))
    with pytest.raises(ValueError):from_csv({'village_id':'TEST:ONLY',None:['extra']})


def test_nwic_csv_is_rejected_and_does_not_overwrite_old_run(tmp_path):
    source=tmp_path/'river.csv';source.write_text('Station,Data Acquisition Time,Flow\nTEST,01-01-2025,999\n')
    output=tmp_path/'models';old=output/'previous';old.mkdir(parents=True)
    (old/'model.json').write_text('TEST KEEP')
    assert main(['--operations',str(source),'--output',str(output)])==2
    _,r=report_at(output)
    assert r['status']=='blocked_invalid_inputs_or_missing_dependency'
    assert (old/'model.json').read_text()=='TEST KEEP'


def test_temporal_partition_purges_overlaps_and_late_training_labels():
    rows=[]
    start=date(2025,1,1)
    for offset in range(120):
        for horizon in (7,15):
            issued=start+timedelta(days=offset)
            rows.append({'horizon_days':horizon,'issued_on':issued.isoformat(),'label_enough':offset%2==0,
                'latest_label_available_at':datetime.combine(issued+timedelta(days=horizon),datetime.min.time(),IST).isoformat()})
    rows[0]['latest_label_available_at']='2026-01-01T00:00:00+05:30'
    cutoff=date(2025,4,1)
    _,parts,_=split_examples(rows,cutoff,min_train=20,min_validation=10,min_class=2)
    for h,p in parts.items():
        assert all(date.fromisoformat(r['issued_on'])+timedelta(days=h-1)<cutoff-timedelta(days=15) for r in p['train'])
        assert all(date.fromisoformat(r['issued_on'])>=cutoff for r in p['validation'])
    assert rows[0] not in parts[7]['train']


def fixture_operations(path,days=300,estimated_targets=False):
    start=date(2024,1,1)
    with path.open('w',encoding='utf-8') as f:
        for i in range(days):
            day=start+timedelta(days=i)
            available=datetime.combine(day+timedelta(days=1),datetime.min.time(),IST).isoformat()
            deficit=10 if i%60>=45 else 0
            def item(value,basis='measured'):
                return {'value':value,'unit':'litres','basis':basis,'source':'TEST FIXTURE ONLY',
                        'method':'TEST calibrated complete daily boundary','available_at':available}
            r={'village_id':'TEST:ONLY','date':day.isoformat(),'scope':'whole_village',
               'complete_day':True,'coverage_verified':True,'fields':{
                'net_inflow_litres':item(100-deficit),'delivered_litres':item(100-deficit),
                'closing_storage_litres':item(200),'demand_litres':item(100),
                'unmet_litres':item(deficit,'assumed' if estimated_targets else 'measured')}}
            f.write(json.dumps(r)+'\n')


def test_real_training_code_saves_two_loadable_models_using_isolated_test_fixture(tmp_path,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('Network is forbidden in offline training')
    monkeypatch.setattr(socket.socket,'connect',forbidden)
    source=tmp_path/'TEST-ONLY.jsonl';fixture_operations(source)
    output=tmp_path/'models'
    assert main(['--operations',str(source),'--output',str(output),'--trees','5','--threads','1','--target','sufficiency'])==0
    folder,r=report_at(output)
    assert r['model_trained'] is True and r['approved'] is False
    assert r['drought_intensity']['status']=='not_implemented'
    assert r['app_forecasts_published'] is False
    assert len(r['models'])==2 and r['data']['selected_records']==300
    for model in r['models']:
        assert (folder/model['artifact']).exists() and len(model['sha256'])==64
        assert model['split']['training_rows']>=100 and model['split']['validation_rows']>=30
        assert model['positive_class']=='shortage_on_any_day_in_horizon'
        assert model['metrics']['samples']==model['split']['validation_rows']


def test_estimated_shortages_are_not_accepted_as_ground_truth(tmp_path):
    source=tmp_path/'TEST-ONLY.jsonl';fixture_operations(source,estimated_targets=True)
    output=tmp_path/'models'
    assert main(['--operations',str(source),'--output',str(output),'--check-only','--target','sufficiency'])==2
    _,r=report_at(output)
    assert r['model_trained'] is False and r['data']['eligible_examples']==0
