"""Load simulation-only bundles with outcome and feature recomputation."""
import gzip
import json
import math
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from scripts.prepare_supply_data import sha256
from services.worker.supply_simulation import POLICY, VERSION, history_features, outcome, partition, water_day


def load_parts(directory, *, target, seed_expected=None, min_train=100, min_validation=30, min_class=5):
    directory = Path(directory)
    if (directory/'latest.json').exists() and not (directory/'simulation-manifest.json').exists():
        directory = Path(json.loads((directory/'latest.json').read_text(encoding='utf-8'))['dataset_directory'])
    manifest_path = directory/'simulation-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest['basis'] != 'simulated' or manifest['schema_version'] != VERSION or manifest['policy'] != POLICY:
        raise ValueError('Use a supported, explicitly simulated dataset and policy')
    if seed_expected is not None and manifest['seed'] != seed_expected:
        raise ValueError('Simulation seed mismatch')
    paths = {}
    for key in ('episodes', 'examples'):
        item = manifest['files'][key]
        path = (directory/item['name']).resolve()
        if path.parent != directory.resolve() or sha256(path) != item['sha256']:
            raise ValueError('Simulation file path/hash mismatch')
        paths[key] = path
    parts = {h: {'train': [], 'validation': []} for h in (7, 15)}
    archived = manifest.get('dataset_kind') == 'archive_conditioned'
    if archived:
        from scripts.prepare_history_simulation import DELAY, HOLDOUT, historical_partition
        if manifest.get('holdout_from') != HOLDOUT.isoformat() or manifest.get('archive_input_delay_days') != DELAY:
            raise ValueError('Unsupported archive availability/holdout policy')
        audit = (directory/manifest['archive_audit_file']).resolve()
        if audit.parent != directory.resolve() or sha256(audit) != manifest['archive_audit_sha256']:
            raise ValueError('Archive audit path/hash mismatch')
        if json.loads(audit.read_text(encoding='utf-8'))['counts'] != manifest['actual_environmental_inputs']:
            raise ValueError('Archive audit counts do not reconcile')
    templates = set(); cases = set()
    with gzip.open(paths['episodes'], 'rt', encoding='utf-8') as episodes, \
         gzip.open(paths['examples'], 'rt', encoding='utf-8') as examples:
        for text in episodes:
            episode = json.loads(text)
            template, case = episode['template_id'], episode['case_id']
            if episode['basis'] != 'simulated' or not case.startswith('sim:') or template in templates or case in cases:
                raise ValueError('Duplicate or unlabelled simulation episode')
            templates.add(template); cases.add(case)
            if archived:
                issue = date.fromisoformat(episode['issued_on'])
                split = historical_partition(issue)
                if split is None or date.fromisoformat(episode['archive_max_observed_on']) > issue-timedelta(days=DELAY):
                    raise ValueError('Archive feature date crosses issue-time or split boundary')
            else:
                split = partition(template, manifest['seed'])
            if episode['partition'] != split or len(episode['days']) != 45:
                raise ValueError('Invalid simulation partition or follow-up')
            previous_closing = None
            for index, day in enumerate(episode['days']):
                balance = water_day(day['opening_storage_litres'], day['net_inflow_litres'],
                    day['sector_demand_litres'], episode['static']['usable_tank_capacity_litres_scenario'],
                    episode['static']['delivery_limit_litres_per_day_scenario'])
                if (day['relative_day'] != index-30 or any(day.get(key) != value for key,value in balance.items()) or
                    (previous_closing is not None and day['opening_storage_litres'] != previous_closing)):
                    raise ValueError('Simulated daily water balance does not reconcile')
                previous_closing = day['closing_storage_litres']
            features = history_features(episode['days'][:30], episode['static'])
            if archived:
                context = episode['archived_features']
                if not context or any(not key.startswith('archive_') for key in context):
                    raise ValueError('Invalid archived feature schema')
                features.update(context)
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                   for value in features.values()):
                raise ValueError('Non-finite simulated feature')
            for horizon in (7, 15):
                line = examples.readline()
                if not line:
                    raise ValueError('Truncated simulation examples')
                row = json.loads(line)
                expected = outcome(episode['days'][30:], horizon, episode['reference_demand_litres'])
                if (row['case_id'] != case or row['template_id'] != template or row['partition'] != split or
                    row['horizon_days'] != horizon or row['basis'] != 'simulated' or row['scope'] != 'whole_village' or
                    row['features'] != features or (archived and row.get('issued_on') != episode['issued_on']) or
                    any(row.get(key) != value for key, value in expected.items())):
                    raise ValueError('Simulation examples disagree with recomputed history/outcomes')
                row['features'] = features  # Both horizons share one in-memory history vector.
                parts[horizon][split].append(row)
            if archived and len(cases) % 10000 == 0:
                print(f'Checked {len(cases):,} archive-conditioned episodes...', flush=True)
        if examples.readline():
            raise ValueError('Unexpected extra simulation examples')
    if len(cases) != manifest['counts']['episodes'] or len(cases)*2 != manifest['counts']['examples']:
        raise ValueError('Simulation manifest row counts do not reconcile')
    problems = []
    for horizon, part in parts.items():
        summary = {'split_kind': 'held_out_reference_dates_simulated_outcomes' if archived else 'held_out_size_templates_not_real_world_backtest'}
        for split, required in [('train', min_train), ('validation', min_validation)]:
            rows = part[split]
            counts = Counter(str(row['label_urgency_level']) if target == 'urgency'
                             else 'enough' if row['label_enough'] else 'shortage' for row in rows)
            summary['training_rows' if split == 'train' else 'validation_rows'] = len(rows)
            summary[split+'_classes'] = dict(counts)
            summary[split+'_template_groups'] = len({row['template_id'] for row in rows})
            if len(rows) < required:
                problems.append(f'{horizon}d {split}: needs at least {required} simulation examples.')
            classes = [str(i) for i in range(6)] if target == 'urgency' else ['enough', 'shortage']
            if any(counts.get(key, 0) < min_class for key in classes):
                problems.append(f'{horizon}d {split}: each class needs at least {min_class} simulated examples.')
        part['summary'] = summary
    return parts, manifest, manifest_path, problems
