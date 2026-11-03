import pytest
from services.api.calculations import irrigation,budget,tank_outflow
from services.worker.model import release_gate,evaluate

def test_irrigation_units_and_cap():
    r=irrigation(2,5,1.2,1,.5,0,100000)
    assert r['requirement_litres']==200000
    assert r['unmet_litres']==100000
    assert irrigation(1,3,1,10,.8)['requirement_litres']==0
    with pytest.raises(ValueError):irrigation(1,5,1,0,0)
def test_balance_and_overlapping_windows():
    assert tank_outflow(100,80,70,10)==100
    assert budget([100]*7)['demand_litres']==700
    assert budget([100]*15)['demand_litres']==1500
    assert budget([100])['unmet_litres'] is None
    r=budget([100,100],[0,200]);assert r['unmet_litres']==100
    assert r['days'][1]['closing_litres']==100
def test_release_fail_closed():
    with pytest.raises(ValueError):release_gate({'approved':False})
    with pytest.raises(ValueError):evaluate([[1]*7],[[1]*7],[[1]*7])
    metrics=evaluate([[2]*15],[[2]*15],[[3]*15]);assert metrics['15']['mae']==0
def test_marathi_fallback_numerical_consistency(setup):
    c,f,h=setup
    r=c.post('/api/v1/assistant/messages',headers=h['f'],json={'village_id':'TEST-A','question':'पाणी उपलब्ध आहे का?','language':'mr','days':15,'consent':False})
    assert r.status_code==200;r=r.json();assert r['mode']=='evidence_only';assert 'उपलब्ध' in r['text'];assert r['evidence']['budget']['shortage_litres'] is None;assert r['evidence']['outlook']['status']=='unavailable'
def test_baseline_versions_and_scope(setup):
    c,f,h=setup
    payload={'sector':'household','litres_per_day':100,'method':'TEST normative','source':'TEST FIXTURE source','reference_start':'2026-01-01','reference_end':'2026-02-01','valid_from':'2026-01-01','valid_to':'2030-01-01','uses_covered':'domestic','assumptions':'TEST FIXTURE assumption','uncertainty':'unknown'}
    for i in [1,2]:
        r=c.post('/api/v1/admin/villages/TEST-A/baselines',headers=h['a'],json=payload);assert r.status_code==200,r.text;assert r.json()['version']==i
    r=c.get('/api/v1/villages/TEST-A/water-budget?days=15',headers=h['f']).json();assert r['components'][0]['demand_litres']==1500
    assert c.post('/api/v1/admin/villages/TEST-B/baselines',headers=h['a'],json=payload).status_code==403
