import httpx
import pytest

from scripts.sync_public_utilities import layer_snapshot


def utility_client(ids=(1, 3), returned=(1, 3)):
    def respond(request):
        if not request.url.path.endswith('/query'):
            return httpx.Response(200, json={'objectIdField': 'OBJECTID', 'fields': [{'name': n} for n in ['OBJECTID', 'IA_NAME', 'DIAMETER', 'OFFICE_INCHARGE']]})
        if request.url.params.get('returnIdsOnly'):
            return httpx.Response(200, json={'objectIds': list(ids)})
        assert 'OFFICE_INCHARGE' not in request.url.params['outFields']
        return httpx.Response(200, json={'features': [
            {'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': [[74.3,18.1],[74.4,18.2]]},
             'properties': {'OBJECTID': n, 'IA_NAME': 'TEST industry', 'DIAMETER': 100}} for n in returned]})
    return httpx.Client(transport=httpx.MockTransport(respond))


def test_utility_geometry_remains_industrial_context_without_flow_or_village_links():
    with utility_client() as client:
        features, receipt = layer_snapshot(client, 6, 'industrial_pipeline', 'Water Pipeline')
    assert receipt['records'] == 2
    assert features[0]['properties']['purpose'] == 'industrial_water_network'
    assert features[0]['properties']['prediction_use'] is False
    assert features[0]['properties']['measurements'] == []
    assert features[0]['properties']['relationship'] == 'geographic_context'
    assert features[0]['properties']['survey_date'] is None
    assert 'village_ids' not in features[0]['properties']


def test_utility_import_rejects_missing_object_ids():
    with utility_client(returned=(1,)) as client:
        with pytest.raises(ValueError, match='missing or duplicated'):
            layer_snapshot(client, 6, 'industrial_pipeline', 'Water Pipeline')
