import json
from datetime import date, datetime, timedelta

import pytest

from services.worker.supply_features import IST
from services.worker.supply_urgency import validate_label, read_labels
from scripts.train_supply_offline import main, urgency_metrics


def label(issued=date(2024,1,1),h=7,level=5):
    return {'village_id':'TEST:ONLY','scope':'whole_village','issued_on':issued.isoformat(),
        'horizon_days':h,'level':level,'policy_version':'supply-urgency-v1','basis':'observed_outcome',
        'reviewed':True,'followup_complete':True,'tanker_need_assessed':True,
        'tanker_required_on':(issued+timedelta(days=3)).isoformat() if level==5 else None,
        'available_at':datetime.combine(issued+timedelta(days=h),datetime.min.time(),IST).isoformat(),
        'source':'TEST FIXTURE ONLY','reviewer':'TEST reviewer','rationale':'TEST reviewed outcome'}


def test_level_five_needs_verified_first_seven_days_not_dispatch_or_later_need():
    now=datetime.now(IST)
    assert validate_label(label(),now)['level']==5
    for change in [dict(tanker_required_on=None),dict(tanker_required_on='2024-01-08'),
                   dict(basis='scenario'),dict(reviewed=False),dict(followup_complete=False),
                   dict(tanker_need_assessed=False),dict(level=6),dict(level=True),dict(level=4),
                   dict(available_at='2024-01-03T00:00:00+05:30')]:
        with pytest.raises(ValueError):validate_label({**label(),**change},now)
    assert validate_label({**label(level=4,h=15),'tanker_required_on':'2024-01-10'},now)['level']==4


def test_missing_outcome_never_becomes_level_zero_and_horizons_must_agree(tmp_path):
    for key in ['level','source','reviewer','rationale']:
        with pytest.raises((ValueError,KeyError)):
            validate_label({**label(),key:''},datetime.now(IST))
    p=tmp_path/'labels.jsonl'
    p.write_text('\n'.join(json.dumps(r) for r in [label(h=7),label(h=15,level=4)]))
    with pytest.raises(ValueError,match='disagree'):read_labels([p],datetime.now(IST))
    p.write_text('\n'.join(json.dumps(r) for r in [label(h=7,level=4),label(h=15,level=2)]))
    with pytest.raises(ValueError,match='cannot be lower'):read_labels([p],datetime.now(IST))


def test_urgency_metrics_penalize_critical_underestimation_explicitly():
    r=urgency_metrics([0,5],[[1,0,0,0,0,0],[1,0,0,0,0,0]],[.5,0,0,0,0,.5])
    assert r['level_5_recall']==0 and r['missed_level_5_cases']==1
    assert r['mean_absolute_level_error']==2.5 and r['severely_underestimated_level_5_cases']==1


def test_default_urgency_training_saves_six_class_candidates_without_label_leakage(tmp_path):
    import socket
    from unittest.mock import patch
    source=tmp_path/'TEST-operations.jsonl'
    labels=tmp_path/'TEST-outcomes.jsonl'
    start=date(2024,1,1)
    with source.open('w') as data,labels.open('w') as outcomes:
        for i in range(360):
            issued=start+timedelta(days=i)
            available=datetime.combine(issued+timedelta(days=1),datetime.min.time(),IST).isoformat()
            def field(value):return {'value':value,'unit':'litres','basis':'measured','source':'TEST FIXTURE ONLY',
                'method':'TEST meter interval','available_at':available}
            r={'village_id':'TEST:ONLY','scope':'whole_village','date':issued.isoformat(),
               'complete_day':True,'coverage_verified':True,'fields':{
                   'delivered_litres':field(100+i%8),'net_inflow_litres':field(100+i%8),'closing_storage_litres':field(200)}}
            data.write(json.dumps(r)+'\n')
            for h in (7,15):outcomes.write(json.dumps(label(issued,h,i%6))+'\n')
    output=tmp_path/'models'
    with patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden')):
        assert main(['--operations',str(source),'--urgency-labels',str(labels),'--output',str(output),
                     '--trees','3','--threads','1'])==0
    latest=json.loads((output/'latest-run.json').read_text())
    from pathlib import Path
    report=json.loads(Path(latest['report']).read_text())
    assert report['target']=='water_supply_urgency_0_to_5' and report['urgency_labels']==720
    assert report['approved'] is False and report['model_trained'] is True
    assert len(report['models'])==2
    for m in report['models']:
        assert [c['level'] for c in m['classes']]==list(range(6))
        assert not any('urgency' in name or 'tanker' in name for name in m['features'])
        assert len(m['metrics']['confusion_rows_actual_columns_predicted'])==6
        assert m['artifact'].startswith('urgency-')
