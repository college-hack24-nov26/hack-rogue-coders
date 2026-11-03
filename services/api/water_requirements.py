"""Explain actual coverage and display approximations without inventing measurements."""
APPROXIMATIONS = [
    'Display area: village boundary when supplied; otherwise +/-0.12 degrees around known coordinates. Without village coordinates, district station extent plus 0.05 degrees is used. These are not catchments or supply zones.',
    'District/name matching selects geographic context only. Nearby sources are never automatically classified as village supplies.',
    'NWIC timestamps without zones are treated as India time. Date-only reservoir readings are represented at 00:00 India time; their exact measurement time is unknown.',
    'Recent means within 48 hours: an app display rule, not a service guarantee. Missing delivery stays unknown, not zero.',
    'Reference geometry is simplified by 0.0002 degrees (roughly 20 metres). Survey dates and route accuracy are unknown.',
    'MIDC pipes and assets describe an industrial network of partial coverage. Their snapshot/survey date and present operation are unknown; meter layers returned no records. They do not establish rural drinking-water supply.',
    'Monitoring identities combine agency, name and coordinates rounded to five decimals. Independent agency IDs are not automatically merged.',
    'Statewide map responses default to 4,000 features (API maximum 12,000); the sidebar lists the first 150 matches. Zoom or filter to inspect further features. Counts describe records, not confirmed supplying sources.',
    'No straight-line pipe, downhill routing, default leakage, pump capacity, household size or source yield is assumed.',
    'Documented connections do not prove current flow. Expired reviews and delivery readings older than 48 hours are not treated as current supply.',
    'Reviews expire on the selected date, at most 366 days after their evidence date. This is an app review rule, not a government verification standard.',
    'Additional reservoir dashboard positions retain publisher precision. Publisher authority is pending independent confirmation; these records are excluded from prediction inputs.',
    'Map records and reviews are not new model inputs. Existing models still forecast groundwater at monitoring stations. No 2011 baseline is used.'
]


def village_requirements(centre, boundary, linked, reviews):
    measured = sum(r['effective_delivery_status'] == 'measured' and r['connection_status'] == 'documented' for r in reviews)
    return {
        'documented_connections': len(linked),
        'recent_delivery_readings': measured,
        'supply_prediction_ready': False,
        'requirements': [
            {'name': 'Village location', 'status': 'available' if centre or boundary else 'missing', 'detail': 'Reviewed coordinates or boundary required. District context is not a village location.'},
            {'name': 'Source-to-village connection', 'status': 'partial' if linked else 'missing', 'detail': 'Requires dated scheme/service-area evidence. The source list is not known to be exhaustive.'},
            {'name': 'Actual delivered water', 'status': 'partial' if measured else 'missing', 'detail': 'Dated meter or delivery evidence required. Dam storage and tap connections do not measure delivered water.'},
            {'name': 'Pipeline route and DMA flows', 'status': 'partial' if any(f['properties'].get('kind') in ('pipeline', 'industrial_pipeline') and f.get('geometry') for f in linked) else 'missing', 'detail': 'Surveyed routes, valve state, pump operation and DMA meters are separate inputs. Industrial context does not establish village supply.'},
            {'name': 'Current demand and tank storage', 'status': 'requires_review', 'detail': 'Current households/population, demand, tank capacity and opening storage need dated local records. No default values are filled in.'}],
        'official_checks': [
            {'name': 'JJM village schemes and sources', 'url': 'https://ejalshakti.gov.in/JJM/citizen_corner/villageinformation.aspx'},
            {'name': 'JJM API access guide', 'url': 'https://ejalshakti.gov.in/webapi/Content/JJM_Web_API.pdf'},
            {'name': 'Maharashtra village identity directory', 'url': 'https://mahavillages.mahabhumi.gov.in/all_list.php'}]
    }
