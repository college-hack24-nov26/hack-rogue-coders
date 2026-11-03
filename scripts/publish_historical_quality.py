"""Map latest available 2021+ historical water-quality observations, marked old."""
import json
from scripts.sync_water_data import OUT, RAW, atomic, merge_features, parse_resource, stamp


def main():
    catalogue = json.loads((OUT / 'catalogue.json').read_text(encoding='utf-8'))
    assets = {}
    resources = []
    for entry in catalogue['resources']:
        path = RAW / (entry['id'] + '.csv')
        if entry['kind'] != 'water_quality' or entry['role'] != 'history' or not path.exists():
            continue
        features, stats = parse_resource(entry, path)
        merge_features(assets, features)
        resources.append({'id': entry['id'], **stats})
    for feature in assets.values():
        feature['id'] += '-historical-quality'
        feature['properties']['id'] = feature['id']
        feature['properties'].update(prediction_use=False, historical_context=True,
            note='Latest available historical quality sample, from 2021 onward. This is not a current drinking-water safety certificate or a village supply connection.')
    atomic(OUT / 'historical-quality.geojson', {'type': 'FeatureCollection', 'updated_at': stamp(),
        'features': list(assets.values()), 'resources': resources, 'prediction_use': False})
    print(json.dumps({'historical_quality_sites': len(assets), 'profiled_resources': len(resources)}), flush=True)


if __name__ == '__main__':
    main()
