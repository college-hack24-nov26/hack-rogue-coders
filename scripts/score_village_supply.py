"""Score two standardized supply scenarios per registered village and publish a local snapshot."""
import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from uuid import uuid4

import numpy as np
from sqlalchemy import select
from xgboost import XGBClassifier

from scripts.aggregate_supply_history import OUT, district_key
from scripts.prepare_history_simulation import DELAY, archive_inputs, archived_features, climate_drivers
from scripts.prepare_supply_data import stream_rows
from services.api.config import settings
from services.api.db import Session, Village
from services.worker.supply_simulation import POLICY, simulate
from services.worker.village_supply_predictions import SCENARIOS, SNAPSHOT

PUBLIC = Path('data/raw/supply/public-completion')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_models(root):
    pointer = json.loads((root/'supply-history-models/latest-run.json').read_text(encoding='utf-8'))
    path = Path(pointer['report']).resolve()
    path.relative_to((root/'supply-history-models').resolve())
    report = json.loads(path.read_text(encoding='utf-8'))
    if (report.get('dataset_kind') != 'archive_conditioned' or report.get('status') != 'trained_simulation_prototypes'
            or report.get('training_mode') != 'urgency' or report.get('urgency_policy') != POLICY):
        raise ValueError('The latest run must contain trained archive-conditioned urgency models')
    models = {}
    for entry in report['models']:
        artifact = (path.parent/entry['artifact']).resolve()
        if artifact.parent != path.parent or digest(artifact) != entry['sha256']:
            raise ValueError('Saved model checksum mismatch')
        model = XGBClassifier(n_jobs=4)
        model.load_model(artifact)
        if model.n_features_in_ != len(entry['features']) or model.n_classes_ != 6:
            raise ValueError('Unexpected saved model feature or class count')
        models[entry['horizon_days']] = (model, entry['features'])
    if set(models) != {7, 15}:
        raise ValueError('Both urgency horizons are required')
    return models, path.parent.name


def name_key(name):
    return re.sub(r'[^a-z0-9]+', '', name.casefold())


def village_households(villages, profiles):
    by_name, by_district = defaultdict(list), defaultdict(list)
    for row in profiles:
        district = district_key(row['district'])
        name = name_key(row['village_name'])
        value = row['reported_households']
        if not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value > 0:
            by_district[district].append(value)
        if name:
            by_name[district, name].append(value)
    roster_names = Counter((district_key(v.district), name_key(v.name)) for v in villages)
    district_sizes = {district: median(values) for district, values in by_district.items()}
    for v in villages:
        district = district_key(v.district)
        key = district, name_key(v.name)
        matches = by_name[key]
        if roster_names[key] == 1 and len(matches) == 1 and matches[0] in by_district[district]:
            yield v, district, matches[0], 'public_village_name_match'
        else:
            size = district_sizes.get(district)
            yield v, district, size, 'district_median' if size is not None else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', type=Path, default=OUT)
    args = parser.parse_args(argv)
    root = Path(settings.model_artifact_root)
    models, run_id = load_models(root)
    with Session() as db:
        villages = list(db.execute(select(Village.id, Village.name, Village.district).order_by(Village.id)))
    if not villages:
        raise ValueError('Import the village registry before generating scenario estimates')
    print(f'Registered villages: {len(villages):,}', flush=True)
    history, _, _, _ = archive_inputs(args.context)
    fallback = defaultdict(list)
    for row in stream_rows(PUBLIC/'pocra/weather-district-context.jsonl'):
        fallback[district_key(row['district'])].append(row)
    contexts = {}
    for district, observations in history.items():
        if fallback[district]:
            issue = max(observations)+timedelta(days=DELAY)
            weather = sorted(fallback[district], key=lambda row: row['for_date'])
            drivers, _ = climate_drivers(observations, issue, weather)
            contexts[district] = (issue, drivers[:30], archived_features(observations, issue))

    entries, groups = {}, defaultdict(list)
    profiles = stream_rows(PUBLIC/'jjm/village-households.jsonl')
    for village, district, size, basis in village_households(villages, profiles):
        entry = {'households': size, 'household_basis': basis, 'scenarios': {}}
        entries[village.id] = entry
        if district in contexts and size is not None:
            groups[district, size].append(entry)
            entry['reference_date'] = contexts[district][0].isoformat()
        else:
            gaps = []
            if size is None:
                gaps.append('Household size template unavailable')
            if district not in contexts:
                gaps.append('District environmental inputs unavailable')
            entry['missing_inputs'] = gaps

    # Equal-size villages in the same district share model inputs under the same assumptions.
    group_items = list(groups.items())
    for offset in range(0, len(group_items), 512):
        batch = group_items[offset:offset+512]
        for scenario, (_, regime) in SCENARIOS.items():
            features = []
            for (district, size), _ in batch:
                _, drivers, context = contexts[district]
                profile = {'jjm_village_id': 'standard-supply-scenario', 'reported_households': size,
                           'observed_on': None, 'jjm_district_code': drivers[0]['district_code_as_reported']}
                _, examples = simulate(profile, drivers, rotate_weather=False, regime_index=regime)
                features.append({**examples[0]['features'], **context})
            predictions = {}
            for horizon, (model, columns) in models.items():
                matrix = np.asarray([[row.get(column, np.nan) for column in columns] for row in features], dtype=np.float32)
                scores = model.predict_proba(matrix)
                if scores.shape != (len(batch), 6) or not np.isfinite(scores).all():
                    raise ValueError('Model returned invalid scores')
                predictions[str(horizon)] = scores.argmax(axis=1).tolist()
            for i, (_, same_inputs) in enumerate(batch):
                levels = {horizon: values[i] for horizon, values in predictions.items()}
                for entry in same_inputs:
                    entry['scenarios'][scenario] = levels
        if offset % 4096 == 0:
            print(f'Scored {min(offset+len(batch), len(groups)):,} of {len(groups):,} distinct input groups', flush=True)

    scored = sum(bool(entry['scenarios']) for entry in entries.values())
    snapshot = {'schema': 1, 'generated_at': datetime.now(timezone.utc).isoformat(),
                'model_run': run_id, 'villages': entries}
    path = root/SNAPSHOT
    temporary = path.with_name(f'.{path.name}.{uuid4().hex}.tmp')
    try:
        temporary.write_text(json.dumps(snapshot, separators=(',', ':'), allow_nan=False), encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    print(f'Published {scored:,} scored villages and {len(entries)-scored:,} with missing inputs to {path.resolve()}', flush=True)


if __name__ == '__main__':
    main()
