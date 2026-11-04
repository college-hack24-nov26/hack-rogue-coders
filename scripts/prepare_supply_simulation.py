"""Generate a separate offline simulated supply dataset; no measured labels."""
import argparse
import gzip
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from scripts.prepare_supply_data import sha256, stream_rows
from services.worker.supply_features import IST
from services.worker.supply_simulation import ASSUMPTIONS, POLICY, VERSION, simulate

DEFAULT_ROOT = Path('data/raw/supply/simulation')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profiles', type=Path, default=Path('data/raw/supply/public-completion/jjm/village-households.jsonl'))
    parser.add_argument('--weather', type=Path, default=Path('data/raw/supply/public-completion/pocra/weather-district-context.jsonl'))
    parser.add_argument('--output', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--seed', type=int, default=1729)
    args = parser.parse_args(argv)
    now = datetime.now(IST)
    folder = args.output/(now.strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:6])
    folder.mkdir(parents=True, exist_ok=False)
    before = {str(p): sha256(p) for p in (args.profiles, args.weather)}
    weather = defaultdict(list)
    for row in stream_rows(args.weather):
        if row['rain'] is None or row['temp_avg'] is None:
            raise ValueError('Weather driver values missing; no defaults inserted')
        weather[str(row['district_code_as_reported'])].append(row)
    for rows in weather.values():
        rows.sort(key=lambda r: r['for_date'])
        if len({row['for_date'] for row in rows}) != len(rows):
            raise ValueError('Duplicate weather date within district')
    weather_by_name = {}
    for rows in weather.values():
        name = rows[0]['district'].casefold().strip()
        if name in weather_by_name:
            raise ValueError('Ambiguous district weather template name')
        weather_by_name[name] = rows
    counts = Counter(); classes = defaultdict(Counter); seen = set()
    episodes = folder/'simulated-daily-episodes.jsonl.gz'
    examples = folder/'simulated-examples.jsonl.gz'
    with gzip.open(episodes, 'wt', encoding='utf-8', compresslevel=3) as daily, \
         gzip.open(examples, 'wt', encoding='utf-8', compresslevel=3) as output:
        for profile in sorted(stream_rows(args.profiles), key=lambda r: r['jjm_village_id']):
            key = profile['jjm_village_id']
            if key in seen:
                raise ValueError('Duplicate village size template')
            seen.add(key)
            drivers = weather.get(str(profile['jjm_district_code']))
            if not drivers:
                # Scenario waveform selection only; preserve both source codes.
                drivers = weather_by_name.get(profile['district'].casefold().strip())
            if not drivers:
                raise ValueError('No district weather template; no geographic guess made')
            episode, rows = simulate(profile, drivers, args.seed)
            daily.write(json.dumps(episode, separators=(',', ':'), allow_nan=False)+'\n')
            counts['episodes'] += 1
            counts['zero_household_templates_replaced'] += episode['template_households_replaced_with_synthetic_size']
            counts['district_weather_name_fallback'] += episode['weather_template_match'] != 'reported_code'
            for row in rows:
                output.write(json.dumps(row, separators=(',', ':'), allow_nan=False)+'\n')
                counts['examples'] += 1
                classes[f"{row['horizon_days']}d_{row['partition']}"][str(row['label_urgency_level'])] += 1
            if counts['episodes'] % 2000 == 0:
                print(f"Simulated {counts['episodes']:,} episodes...", flush=True)
    for path in (args.profiles, args.weather):
        if sha256(path) != before[str(path)]:
            raise ValueError('Source changed during simulation')
    manifest = {'schema_version': VERSION, 'basis': 'simulated', 'created_at': now.isoformat(),
        'purpose': 'Prototype training against explicit hypothetical balances; no real-world accuracy established.',
        'seed': args.seed, 'counts': dict(counts), 'urgency_classes': {key: dict(value) for key, value in classes.items()},
        'inputs': [{'path': path, 'sha256': digest} for path, digest in before.items()],
        'files': {'episodes': {'name': episodes.name, 'sha256': sha256(episodes)},
                  'examples': {'name': examples.name, 'sha256': sha256(examples)}},
        'policy': POLICY, 'assumptions': ASSUMPTIONS,
        'split': '80/20 hash split by source village size template. Both horizons and all days of a template stay together. This is not a real temporal backtest.',
        'model_trained': False, 'real_operations_written': 0, 'real_urgency_labels_written': 0,
        'network_calls': 0, 'application_database_access': False,
        'release_blockers': ['Simulated labels only. Metrics assess simulator agreement, not Maharashtra forecast accuracy.',
            'Require measured village history/outcomes, verified service-area connections and independent prospective validation before operational use.']}
    manifest_path = folder/'simulation-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding='utf-8')
    (args.output/'latest.json').write_text(json.dumps({'dataset_directory': str(folder.resolve()),
        'manifest': str(manifest_path.resolve())}, indent=2), encoding='utf-8')
    print(json.dumps({'dataset': str(folder), 'counts': dict(counts), 'classes': manifest['urgency_classes']}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
