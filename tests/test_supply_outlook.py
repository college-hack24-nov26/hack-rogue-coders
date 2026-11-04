from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from services.api.db import Record
from services.api.calculations import budget


def supply_fixture(setup,valid_days=30,confirmed=True,sectors=('household','agriculture','livestock','other')):
    client,factory,headers=setup
    today=datetime.now(ZoneInfo('Asia/Kolkata')).date()
    with factory() as db:
        source=Record(kind='supply_source',key='TEST-SOURCE',payload={'valid_until':(today+timedelta(days=valid_days)).isoformat()})
        db.add(source);db.flush()
        for sector in sectors:
            db.add(Record(kind='baseline',key='TEST-A:'+sector,payload={'litres_per_day':100,'valid_from':today.isoformat(),
                'valid_to':(today+timedelta(days=30)).isoformat(),'reference_start':today.isoformat(),'reference_end':today.isoformat(),
                'source':'TEST demand evidence','assumptions':'TEST constant demand'}))
            db.add(Record(kind='supply',key='TEST-A:'+sector,payload={'source_id':'TEST-SOURCE','source_record_id':source.id,
                'valid_until':(today+timedelta(days=valid_days)).isoformat(),'litres_per_day':80,'opening_storage_litres':200,
                'storage_capacity_litres':1000,'delivery_limit_litres_per_day':100,'assumptions':'TEST disjoint sector reserves; net operator allocations',
                'storage_partition_verified':confirmed,'net_supply_after_losses':confirmed}))
        db.commit()
    return client,headers,today


def test_supply_outlook_seven_days_enough_but_fifteen_days_short(setup):
    c,h,today=supply_fixture(setup)
    path='/api/v1/villages/TEST-A/supply-outlook'
    assert c.get(path).status_code==401
    result=c.get(path,headers=h['f']).json()
    seven,fifteen=result['outlooks']
    assert result['target']=='water_supply_sufficiency' and result['model_trained'] is False
    assert seven['enough'] is True and seven['closing_storage_litres']==240
    assert fifteen['enough'] is False and fifteen['shortage_litres']==400
    assert fifteen['first_shortage_date']==(today+timedelta(days=11)).isoformat()


def test_expiring_source_plan_cannot_support_fifteen_day_claim(setup):
    c,h,_=supply_fixture(setup,valid_days=10)
    seven,fifteen=c.get('/api/v1/villages/TEST-A/supply-outlook',headers=h['a']).json()['outlooks']
    assert seven['enough'] is True
    assert fifteen['enough'] is None and fifteen['verdict']=='insufficient_data'


def test_missing_sector_or_unreviewed_losses_and_storage_never_means_enough(setup):
    c,h,_=supply_fixture(setup,confirmed=False,sectors=('household',))
    result=c.get('/api/v1/villages/TEST-A/supply-outlook',headers=h['a']).json()
    assert all(r['enough'] is None and r['shortage_litres'] is None and len(r['missing_inputs'])>=3 for r in result['outlooks'])


def test_daily_pipe_delivery_does_not_require_storage_capacity_and_balance_reconciles():
    result=budget([100,100],[150,150],capacity=0)
    assert result['unmet_litres']==0
    assert [d['overflow_litres'] for d in result['days']]==[50,50]
    for d in result['days']:
        assert d['inflow_litres']==d['delivered_litres']+d['closing_litres']+d['overflow_litres']
