import gzip
import json
import socket
from copy import deepcopy

import pytest

from scripts.prepare_supply_data import sha256
from scripts.prepare_supply_simulation import main as prepare
from scripts.simulation_training_data import load_parts
from scripts.train_supply_offline import main as train
from services.worker.supply_simulation import POLICY, history_features, outcome, simulate, water_day


def profile(identity='TEST1'):
    return {'jjm_village_id': identity, 'reported_households': 100, 'district': 'TEST',
            'jjm_district_code': '527', 'observed_on': None}


def weather():
    return [{'for_date': f'2026-10-{day:02}', 'district': 'TEST', 'district_code_as_reported': 527,
             'rain': 0 if day % 2 else 3, 'temp_avg': 28} for day in range(1, 15)]


def test_water_balance_conserves_volume_and_prioritises_households():
    demands = {'household': 100, 'livestock': 20, 'other': 30, 'agriculture': 50}
    row = water_day(40, 50, demands, 100, 1000)
    assert row['delivered_litres'] == 90 and row['unmet_litres'] == 110
    assert row['sector_delivered_litres']['household'] == 90
    assert row['sector_delivered_litres']['agriculture'] == 0
    assert row['closing_storage_litres'] == 0
    row = water_day(80, 300, demands, 100, 120)
    assert row['delivered_litres'] == 120 and row['closing_storage_litres'] == 100
    assert row['overflow_litres'] == 160
    assert 80+300 == row['delivered_litres']+row['closing_storage_litres']+row['overflow_litres']
    with pytest.raises(ValueError):
        water_day(101, 0, demands, 100, 120)


def test_simulation_urgency_boundaries_and_first_week_tanker_meaning():
    base = water_day(1000, 200, {'household':100, 'livestock':0, 'other':100, 'agriculture':0}, 2000, 1000)
    for deficit, expected in [(0,0), (10,2), (20,3), (50,4)]:
        future = [deepcopy(base) for _ in range(15)]
        future[0]['unmet_litres'] = deficit
        assert outcome(future, 7, 200)['label_urgency_level'] == expected
    future = [deepcopy(base) for _ in range(15)]
    future[0]['closing_storage_litres'] = 99
    assert outcome(future, 7, 200)['label_urgency_level'] == 1
    future[0]['sector_delivered_litres']['household'] = 59
    assert outcome(future, 7, 200)['label_urgency_level'] == 5
    assert outcome(future, 15, 200)['simulated_tanker_required_relative_day'] == 0
    future = [deepcopy(base) for _ in range(15)]
    future[7]['sector_delivered_litres']['household'] = 50
    future[7]['unmet_litres'] = 50
    assert outcome(future, 7, 200)['label_urgency_level'] == 0
    assert outcome(future, 15, 200)['label_urgency_level'] == 4


def test_seeded_episode_reproducibility_conservation_and_future_exclusion():
    first, rows = simulate(profile(), weather())
    assert (first, rows) == simulate(profile(), weather())
    assert first['basis'] == 'simulated' and all(row['label_basis'] == 'simulated_outcome' for row in rows)
    assert rows[0]['features'] == rows[1]['features']
    for day in first['days']:
        assert day['opening_storage_litres']+day['net_inflow_litres'] == pytest.approx(
            day['delivered_litres']+day['closing_storage_litres']+day['overflow_litres'])
        assert sum(day['sector_delivered_litres'].values()) == pytest.approx(day['delivered_litres'])
        assert sum(day[key] for key in ('pipeline_inflow_litres','groundwater_inflow_litres',
            'surface_inflow_litres','routine_tanker_litres')) == pytest.approx(day['net_inflow_litres'])
    first['days'][30]['net_inflow_litres'] = 1e99
    assert history_features(first['days'][:30], first['static']) == rows[0]['features']
    assert rows[1]['label_urgency_level'] >= rows[0]['label_urgency_level']
    assert (rows[1]['label_urgency_level'] == 5) == (rows[0]['label_urgency_level'] == 5)


@pytest.fixture()
def bundle(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Offline simulation tried to call network')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    profiles = tmp_path/'profiles.jsonl'
    profiles.write_text(''.join(json.dumps(profile(str(i)))+'\n' for i in range(700)), encoding='utf-8')
    drivers = tmp_path/'weather.jsonl'
    drivers.write_text(''.join(json.dumps(row)+'\n' for row in weather()), encoding='utf-8')
    root = tmp_path/'simulation'
    assert prepare(['--profiles',str(profiles),'--weather',str(drivers),'--output',str(root)]) == 0
    path = json.loads((root/'latest.json').read_text())['dataset_directory']
    return root, __import__('pathlib').Path(path)


def test_bundle_is_trainable_and_holds_out_complete_template_groups(bundle):
    root, folder = bundle
    parts, manifest, _, problems = load_parts(root, target='urgency')
    assert problems == []
    assert manifest['counts']['examples'] == 1400
    assert manifest['real_operations_written'] == manifest['real_urgency_labels_written'] == 0
    for part in parts.values():
        train_ids = {row['template_id'] for row in part['train']}
        validation_ids = {row['template_id'] for row in part['validation']}
        assert not train_ids & validation_ids
        assert len(train_ids | validation_ids) == 700
        assert all(row['features'] == parts[15]['train'][i]['features'] for i,row in enumerate(parts[7]['train']))


def test_tampered_targets_are_recomputed_even_if_file_hash_is_updated(bundle):
    _, folder = bundle
    path = folder/'simulated-examples.jsonl.gz'
    with gzip.open(path, 'rt') as stream:
        rows = [json.loads(line) for line in stream]
    rows[0]['label_urgency_level'] = (rows[0]['label_urgency_level']+1) % 6
    with gzip.open(path, 'wt') as stream:
        for row in rows:
            stream.write(json.dumps(row)+'\n')
    manifest_path = folder/'simulation-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['files']['examples']['sha256'] = sha256(path)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='recomputed'):
        load_parts(folder, target='urgency')


def test_invalid_balance_is_rejected_even_with_an_updated_file_hash(bundle):
    _, folder = bundle
    path = folder/'simulated-daily-episodes.jsonl.gz'
    with gzip.open(path, 'rt') as stream:
        rows = [json.loads(line) for line in stream]
    rows[0]['days'][0]['closing_storage_litres'] += 10
    with gzip.open(path, 'wt') as stream:
        for row in rows:
            stream.write(json.dumps(row)+'\n')
    manifest_path = folder/'simulation-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['files']['episodes']['sha256'] = sha256(path)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='balance'):
        load_parts(folder, target='urgency')


def test_explicit_mode_saves_loadable_simulation_models_only_in_test_folder(bundle, tmp_path):
    root, _ = bundle
    output = tmp_path/'test-models'
    assert train(['--data-mode','simulation','--simulation-dataset',str(root),'--output',str(output),
                  '--trees','2','--threads','1']) == 0
    pointer = json.loads((output/'latest-run.json').read_text())
    report = json.loads(__import__('pathlib').Path(pointer['report']).read_text())
    assert report['training_data_basis'] == 'simulated' and not report['approved']
    assert not report['app_forecasts_published'] and report['network_calls'] == 0
    for model in report['models']:
        assert model['artifact'].startswith('simulated-urgency-')
        assert model['training_data_basis'] == 'simulated'
        assert model['policy_version'] == POLICY['version']


def test_simulation_path_requires_explicit_simulation_mode(tmp_path):
    with pytest.raises(SystemExit) as error:
        train(['--simulation-dataset',str(tmp_path)])
    assert error.value.code == 2
