"""Read the public MIDC water utility layers as industrial reference context."""
import hashlib
import json
from collections import Counter

import httpx
from shapely.geometry import shape

from scripts.sync_water_data import OUT, RAW, atomic, stamp

BASE = 'https://gis.midcindia.org/server/rest/services/Application/Department_Utility_Map_Service/MapServer'
LAYERS = {1: ('intake', 'Jackwell'), 2: ('valve', 'Valve'), 3: ('tank', 'Reservoir'),
          4: ('pump', 'Pump House'), 5: ('treatment', 'Water Treatment Plant'),
          6: ('industrial_pipeline', 'Water Pipeline'), 7: ('meter', 'Flow Meter'),
          8: ('other', 'Water Specials'), 9: ('meter', 'Water Meter')}


def response_json(client, url, params):
    response = client.get(url, params=params)
    response.raise_for_status()
    if len(response.content) > 20_000_000:
        raise ValueError('Utility response exceeds bounded size')
    data = response.json()
    if data.get('error'):
        raise ValueError('Public utility query unavailable')
    return data


def layer_snapshot(client, layer, kind, name):
    url = BASE + '/' + str(layer)
    metadata = response_json(client, url, {'f': 'json'})
    identity = metadata.get('objectIdField') or 'OBJECTID'
    fields = {f['name']: f for f in metadata.get('fields', [])}
    allowed = {identity, 'IA_NAME', 'IA_CODE', 'TYPE_OF_PIPE', 'DIAMETER', 'WATER_SUPPLY_CLASS',
               'YEAR_OF_COMMISSIONING', 'DATE_OF_INSTALLATION', 'LAST_DATE_OF_SERVICING',
               'RESERVOIR_TYPE', 'VALVE_TYPE', 'QTY_OF_PUMPS'}
    allowed |= {f for f in fields if f.endswith('_CODE') and f not in ('MDVNCODE', 'DVNCODE')}
    allowed &= fields.keys()
    ids = response_json(client, url + '/query', {'where': '1=1', 'returnIdsOnly': 'true', 'f': 'json'}).get('objectIds')
    if ids is None:
        ids = []
    if not isinstance(ids, list) or len(ids) > 25000:
        raise ValueError('Unsupported utility layer count')
    features = []
    received = set()
    for start in range(0, len(ids), 250):
        requested = ids[start:start + 250]
        data = response_json(client, url + '/query', {'objectIds': ','.join(map(str, requested)),
            'outFields': ','.join(sorted(allowed)), 'returnGeometry': 'true', 'outSR': 4326,
            'maxAllowableOffset': .0002, 'f': 'geojson'})
        if data.get('exceededTransferLimit'):
            raise ValueError('Truncated utility layer')
        batch_ids = set()
        for item in data.get('features', []):
            props = item['properties']
            object_id = props.get(identity, item.get('id'))
            batch_ids.add(object_id)
            asset = 'midc-' + str(layer) + '-' + str(object_id)
            features.append({'type': 'Feature', 'id': asset, 'geometry': item.get('geometry'),
                'properties': {'id': asset, 'name': (props.get('IA_NAME') or 'MIDC') + ' · ' + name + ' ' + str(object_id),
                    'kind': kind, 'agency': 'Maharashtra Industrial Development Corporation',
                    'source_url': url, 'relationship': 'geographic_context', 'purpose': 'industrial_water_network',
                    'prediction_use': False, 'survey_date': None, 'observed_at': None, 'measurements': [],
                    'asset_attributes': {k: v for k, v in props.items() if k in allowed and v is not None},
                    'note': 'Industrial water-network reference, not a verified rural drinking-water connection. Survey/update date and present operation are unknown. Pipe direction, valve state, pressure and delivered volume are not inferred.'}})
        if batch_ids != set(requested) or received & batch_ids:
            raise ValueError('Utility object IDs were missing or duplicated')
        received.update(batch_ids)
    if len(received) != len(ids):
        raise ValueError('Incomplete utility layer')
    return features, {'id': layer, 'name': name, 'records': len(features), 'url': url, 'survey_date': None}


def main():
    features = []
    layers = []
    with httpx.Client(timeout=40, follow_redirects=False) as client:
        for layer, (kind, name) in LAYERS.items():
            items, receipt = layer_snapshot(client, layer, kind, name)
            features.extend(items)
            layers.append(receipt)
    for feature in features:
        feature['bbox'] = list(shape(feature['geometry']).bounds) if feature.get('geometry') else None
    collection = {'type': 'FeatureCollection', 'updated_at': stamp(), 'features': features,
                  'source': BASE, 'layers': layers, 'survey_date': None, 'prediction_use': False}
    RAW.mkdir(parents=True, exist_ok=True)
    atomic(RAW / 'midc-water-utilities.json', collection)
    raw = (RAW / 'midc-water-utilities.json').read_bytes()
    collection['receipt'] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'retrieved_at': stamp()}
    atomic(OUT / 'utility-network.geojson', collection)
    print(json.dumps({'utility_features': len(features), 'kinds': dict(Counter(f['properties']['kind'] for f in features))}), flush=True)


if __name__ == '__main__':
    main()
