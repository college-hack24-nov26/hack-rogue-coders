"""Map supported 2021+ manual well readings as historical monitoring context."""
import json
from scripts.sync_water_data import OUT, RAW, atomic, parse_resource, stamp
from scripts.collect_water_history import ENCODINGS

RESOURCE = 'bb185a88-c7c3-483f-b06e-784ce5322ff8'


def main():
    catalogue = json.loads((OUT / 'catalogue.json').read_text(encoding='utf-8'))
    entry = next(r for r in catalogue['resources'] if r['id'] == RESOURCE)
    assets, stats = parse_resource(entry, RAW / (RESOURCE + '.csv'), encoding=ENCODINGS[RESOURCE])
    for feature in assets.values():
        feature['id'] += '-historical-well'
        props = feature['properties']
        if props.get('source_village_text'):
            props['name'] = props['source_village_text'].strip() + ' · monitoring well ' + props['name']
        feature['properties'].update(id=feature['id'], historical_context=True, historical_type='well_monitoring', prediction_use=False,
            note='Latest supported manual well reading from 2021 onward. This is not current source yield, drinking-water safety or a verified village supply. No village identity is inferred from the source village name.')
    atomic(OUT / 'historical-wells.geojson', {'type': 'FeatureCollection', 'updated_at': stamp(),
        'features': list(assets.values()), 'source_resource': RESOURCE, 'stats': stats, 'prediction_use': False})
    print(json.dumps({'historical_well_sites': len(assets), **stats}), flush=True)


if __name__ == '__main__':
    main()
