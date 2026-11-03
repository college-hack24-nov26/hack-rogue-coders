"""Retrieve an explicitly public reservoir feed; publish evidence/access limits."""
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

import httpx

from scripts.sync_water_data import OUT, RAW, SOURCE_TZ, atomic, stamp

URL = 'https://pravahaimwrd.in/api/v1/public/dams/latest'


def parse_dams(data):
    features = []
    rejected = unlocated = 0
    if data.get('truncated') or not isinstance(data.get('data'), list) or len(data['data']) != data.get('total'):
        raise ValueError('Incomplete reservoir feed')
    for row in data['data']:
        try:
            observed = datetime.fromisoformat(row['date']).replace(tzinfo=SOURCE_TZ)
            if not 2021 <= observed.year or observed.date() > datetime.now(SOURCE_TZ).date():
                raise ValueError('Invalid observation date')
            measurements = []
            for field, label, unit in [('live_storage_mcum', 'Live storage', 'million cubic metres'),
                    ('gross_storage_mcum', 'Gross storage', 'million cubic metres'),
                    ('storage_percentage', 'Live storage percentage', '%'), ('level_rl', 'Water level RL', 'metres'),
                    ('rainfall_mm', 'Reported rainfall', 'mm')]:
                if row.get(field) is None:
                    continue
                value = float(row[field])
                if not math.isfinite(value):
                    continue
                measurements.append({'label': label, 'value': value, 'units': unit, 'observed_at': observed.isoformat(), 'source_url': URL})
            if not row.get('dam_id') or not row.get('dam_name_en') or not measurements:
                raise ValueError('No identity or measurement')
        except (KeyError, ValueError, TypeError):
            rejected += 1
            continue
        try:
            lat, lon = float(row['lat']), float(row['lng'])
            if not (15.5 <= lat <= 22.2 and 72.5 <= lon <= 81.1):
                raise ValueError('No valid Maharashtra coordinate')
        except (ValueError, TypeError, KeyError):
            unlocated += 1
            continue
        identity = 'pravah-dam-' + str(row['dam_id'])
        features.append({'type': 'Feature', 'id': identity, 'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
            'properties': {'id': identity, 'name': row['dam_name_en'], 'kind': 'reservoir', 'district': row.get('district'),
                'taluka': row.get('taluka'), 'source_url': URL, 'agency': 'Pravah-AI public dashboard (WRD branded)',
                'publisher_status': 'authority_unconfirmed', 'relationship': 'geographic_context', 'prediction_use': False,
                'observed_at': observed.isoformat(), 'time_precision': 'date_only', 'measurements': measurements,
                'note': 'Publisher authority pending independent confirmation. Storage is not the volume allocated or delivered to this village. Date-only observations are represented at 00:00 India time; coordinates retain source precision.'}})
    return features, {'received': len(data['data']), 'mapped': len(features), 'unlocated': unlocated, 'rejected': rejected}


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    sources = []
    try:
        response = httpx.get(URL, timeout=60, follow_redirects=False)
        response.raise_for_status()
        if len(response.content) > 15_000_000:
            raise ValueError('Reservoir response exceeds limit')
        features, counts = parse_dams(response.json())
        if not features:
            raise ValueError('No valid reservoir records; previous snapshot retained')
        (RAW / 'pravah-reservoirs.json').write_bytes(response.content)
        receipt = {'url': URL, 'retrieved_at': stamp(), 'sha256': hashlib.sha256(response.content).hexdigest(),
                   'bytes': len(response.content), **counts}
        atomic(RAW / 'pravah-reservoirs.receipt.json', receipt)
        atomic(OUT / 'reservoirs.geojson', {'type': 'FeatureCollection', 'features': features, 'updated_at': stamp(), 'receipt': receipt})
        sources.append({'id': 'public_reservoirs', 'name': 'Pravah-AI public dam storage', 'url': URL,
            'status': 'downloaded_authority_unconfirmed', 'records': counts['mapped'], 'coverage': counts,
            'note': 'WRD-branded public feed; publisher authority not independently confirmed. Context only; no name-based merge with NWIC and no village supply inference. ' + str(counts['unlocated']) + ' records have no valid coordinate.'})
    except (httpx.HTTPError, ValueError, KeyError) as error:
        sources.append({'id': 'public_reservoirs', 'name': 'Pravah-AI public dam storage', 'url': URL,
            'status': 'retrieval_failed', 'note': type(error).__name__ + '; last valid local snapshot retained.'})
    sources.extend([
        {'id': 'jjm_sources', 'name': 'JJM village schemes, sources and service areas', 'url': 'https://ejalshakti.gov.in/JJM/citizen_corner/villageinformation.aspx',
         'status': 'public_portal_api_approval_required', 'note': 'Public village details exist; bulk authenticated API requires registration and approval. JJM village IDs are not assumed equal to LGD IDs. Scheme record is not a current-flow measurement.'},
        {'id': 'jjm_guide', 'name': 'JJM API help guide v1.02 (PDF)', 'url': 'https://ejalshakti.gov.in/webapi/Content/JJM_Web_API.pdf',
         'status': 'documentation_verified', 'note': 'Documents registration, competent-authority approval, API permissions and bearer token. No account or application has been submitted.'},
        {'id': 'sujalam', 'name': 'Sujalam Bharat source-to-tap data sharing', 'url': 'https://www.pib.gov.in/PressReleasePage.aspx?PRID=2301566&lang=1&reg=3',
         'status': 'governed_access', 'note': 'Policy published 20 August 2026. Request scheme/service-area IDs and source-to-tap asset exports from the State JJM/WSSD authority; no public statewide export verified.'},
        {'id': 'mrsac', 'name': 'MRSAC / GSDA GIS', 'url': 'https://jsin.mrsac.org.in/mahagsda/',
         'status': 'legacy_boundary_excluded', 'note': 'Public configuration references admin2011 village/state boundaries. Excluded under the current-data requirement; no modern village geometry or drinking-water pipeline feed verified.'},
        {'id': 'wrd', 'name': 'Maharashtra WRD official storage portal', 'url': 'https://wrd.maharashtra.gov.in/',
         'status': 'portal_verified_export_unavailable', 'note': 'WRD links mwrdpravah.in/damstorage; retrieval of that portal and the public storage PDF failed TLS verification here. No unverified figures were extracted from it.'},
        {'id': 'imd', 'name': 'IMD weather forecast API', 'url': 'https://api.imd.gov.in/public/api_reference.html',
         'status': 'api_key_required', 'note': 'Previously checked forecast endpoint returned 401. No future rainfall is invented; existing Open-Meteo integration remains a separately labelled non-government grid forecast.'},
        {'id': 'local_operations', 'name': 'Village operations: DMA, tanks, pumps, meters and deliveries', 'url': 'https://water.maharashtra.gov.in/',
         'status': 'authority_export_required', 'note': 'Need dated surveyed pipelines, valve/pump operation, inlet/outlet meters, tank levels/capacity, tanker delivery logs and source yields. No statewide public operational feed verified.'},
        {'id': 'demand', 'name': 'Current village demand and population', 'url': 'https://ejalshakti.gov.in/JJM/citizen_corner/villageinformation.aspx',
         'status': 'dated_local_records_required', 'note': 'Household connections are not persons or consumption. No 2011 population or assumed household size is substituted; agriculture/livestock/industrial demand also need current local records.'}])
    utility_path = OUT / 'utility-network.geojson'
    utility = json.loads(utility_path.read_text(encoding='utf-8')) if utility_path.exists() else {}
    sources.extend([
        {'id': 'midc', 'name': 'MIDC public industrial water-network GIS',
         'url': 'https://gis.midcindia.org/server/rest/services/Application/Department_Utility_Map_Service/MapServer',
         'status': 'reference_geometry_downloaded' if utility else 'not_downloaded', 'records': len(utility.get('features', [])),
         'note': '660 pipe features, 175 valves, 32 tanks/reservoirs, 7 pump houses, 6 treatment plants and 1 intake at audit. Industrial network only; survey/update date unknown. Flow-meter and water-meter layers are empty. No rural village service connection is inferred.'},
        {'id': 'mrsac_wssd', 'name': 'MRSAC WSSD scheme-point and pipeline services',
         'url': 'https://jsin.mrsac.org.in/mahawssd/', 'status': 'services_identified_retrieval_failed',
         'note': 'Public configuration lists PWS/regional/spot scheme points and PWS/regional pipe lines. All five referenced service metadata requests failed TLS retrieval here. No village service links or geometry were fabricated.'},
        {'id': 'pocra', 'name': 'PoCRA agricultural water-budget portal',
         'url': 'https://gis.mahapocra.gov.in/html/water-budget-service/water-budget.html', 'status': 'current_budget_not_verified',
         'note': 'Public code includes modelled crop deficit/soil-moisture layers. A budget request hard-codes 2025-06-08; the footer uses yesterday’s system date. Neither proves current measured village supply. Not imported as current drinking-water demand or delivery.'}])
    atomic(OUT / 'additional-sources.json', {'updated_at': stamp(), 'sources': sources})
    print(json.dumps({'additional_sources': len(sources), 'reservoirs': len(features) if 'features' in locals() else 0}), flush=True)


if __name__ == '__main__':
    main()
