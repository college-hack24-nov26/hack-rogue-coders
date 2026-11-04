"""Offline, resumable quality screening of every NWIC candidate archive.

Use Python with pandas. Outputs are district/day environmental summaries,
not village water deliveries, measured supply labels or live-availability claims.
"""
import argparse
import concurrent.futures
import hashlib
import json
import re
from pathlib import Path

ROOT = Path('data/raw/training')
OUT = Path('data/raw/supply/history-context-v2')
VERSION = 'history-context-v2'
ALIASES = {'ahmednagar':'ahilyanagar', 'ahmadnagar':'ahilyanagar', 'ahmednager':'ahilyanagar', 'ahilyanager':'ahilyanagar',
           'aurangabad':'chhatrapatisambhajinagar', 'chsambhajinagar':'chhatrapatisambhajinagar',
           'osmanabad':'dharashiv', 'bid':'beed', 'buldana':'buldhana', 'gondiya':'gondia',
           'raigarh':'raigad', 'sindudurg':'sindhudurg', 'nasik':'nashik', 'mumbaisuburban':'mumbaisuburban'}
SENTINELS = {-9999, -999, -99.999, -999.999, -9999.999, 99999, 999999}


def district_key(value):
    key = re.sub(r'[^a-z0-9]', '', str(value).casefold())
    return ALIASES.get(key, key)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def atomic(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=True, allow_nan=False), encoding='utf-8')
    tmp.replace(path)


def metric_family(name, kind, unit=''):
    key = name.casefold(); unit = unit.casefold().strip()
    if 'rainfall' in key:
        return 'daily_rain_mm' if 'manual daily' in key else 'rain_sample_mm'
    if 'air temperature' in key:
        return 'air_temperature_c'
    if 'humidity' in key:
        return 'humidity_percent'
    if 'discharge' in key or unit in ('m3/sec','cusec','cumec'):
        return 'flow_m3_s' if unit in ('m3/sec','cusec','cumec') or 'm3/sec' in key or 'cusec' in key else 'other'
    if kind == 'groundwater' and 'level' in key:
        return 'groundwater_level_change_m'
    if 'level' in key or unit in ('meter','m','metre') and kind in ('river','reservoir','canal'):
        return 'surface_level_change_m'
    if 'wind speed' in key: return 'wind_speed_kmh'
    if 'wind direction' in key: return 'wind_direction_deg'
    if 'radiation' in key: return 'solar_radiation'
    if 'pressure' in key: return 'pressure_mb'
    if 'sunshine' in key: return 'sunshine_minutes'
    return 'water_quality' if kind == 'water_quality' else 'other'


def numerical(series, family):
    import numpy as np
    import pandas as pd
    values = pd.to_numeric(series, errors='coerce').astype('float64')
    good = np.isfinite(values) & ~values.isin(SENTINELS)
    ranges = {'daily_rain_mm':(0,2000), 'rain_sample_mm':(0,2000),
              'air_temperature_c':(-30,65), 'humidity_percent':(0,100),
              'flow_m3_s':(0,None), 'wind_speed_kmh':(0,400), 'wind_direction_deg':(0,360),
              'solar_radiation':(0,1600), 'pressure_mb':(500,1100), 'sunshine_minutes':(0,1440)}
    lo, hi = ranges.get(family, (0,None) if family == 'water_quality' else (None,None))
    if lo is not None: good &= values >= lo
    if hi is not None: good &= values <= hi
    return values.where(good)


def timestamps(values):
    import pandas as pd
    v = values.str.strip().str.replace('/', '-', regex=False)
    # Source ISO date is year-first; never apply day-first parsing to it.
    dmy = v.str.match(r'^\d{1,2}-\d{1,2}-\d{4}(?:\s|$)', na=False)
    result = pd.to_datetime(v.where(~dmy), format='ISO8601', errors='coerce', utc=True).dt.tz_localize(None)
    result.loc[dmy] = pd.to_datetime(v.loc[dmy], format='mixed', dayfirst=True, errors='coerce')
    return result.where(result.dt.year.between(2021,2025))


def one(job):
    import pandas as pd
    path, out, kind, allowed = job
    metadata = read_json(path.with_suffix('.metadata.json'))
    receipt = out/(path.stem+'.json')
    target = out/(path.stem+'.csv.gz')
    signature = sha(path)
    upgrade = None
    def cached(report):
        if report['version'] != VERSION or report['output'] != str(target):
            report.update(version=VERSION,output=str(target)); atomic(receipt,report)
        return report
    if receipt.exists() and target.exists():
        prior = read_json(receipt)
        if prior['input_sha256'] == signature and prior['output_sha256'] == sha(target):
            if prior['version'] == VERSION:
                return cached(prior)
            if prior['version'] == 'history-context-v1':
                if not prior['rows_excluded_identity_or_timestamp']:
                    return cached(prior)
                upgrade = prior
    headers = metadata['fields']
    clean = {x.strip():x for x in headers}
    time_name = clean.get('Data Acquisition Time') or clean['Date of Monitoring']
    district_name = clean.get('District') or clean['District Name']
    station = clean.get('Station Code') or clean.get('Station') or clean['Well ID']
    agency = clean.get('Agency Name') or clean['Agency']
    dimensions = [agency, station, clean['Latitude'], clean['Longitude']]
    scada = 'Data Value' in clean
    metrics = ['Data Value'] if scada else [x for x in headers[headers.index(time_name)+1:] if x not in ('Colour','Odour')]
    extra = ['Description','Parameter Type','Unit'] if scada else []
    cols = list(dict.fromkeys([time_name,district_name,*dimensions,*metrics,*extra]))
    df = pd.read_csv(path, usecols=cols, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    if len(df) != metadata['exported_rows']:
        raise ValueError(f'{path.name}: expected {metadata["exported_rows"]} rows, got {len(df)}')
    total = len(df)
    alias = {value:district_key(value) for value in df[district_name].unique()}
    df['district'] = df[district_name].map(alias)
    supplement = False
    if upgrade:
        spellings = {value for value in alias if re.sub(r'[^a-z0-9]','',str(value).casefold()) == 'ahmadnagar'}
        if not spellings:
            return cached(upgrade)
        # The original pass excluded this spelling. Recompute the entire file if
        # another spelling could refer to the same station/time in that file.
        if not any(key == 'ahilyanagar' and raw not in spellings for raw,key in alias.items()):
            df = df.loc[df[district_name].isin(spellings)].copy()
            supplement = True
    scanned_subset = len(df)
    df['stamp'] = timestamps(df[time_name])
    identity_valid = df['district'].isin(allowed) & df[station].str.strip().ne('') & df['stamp'].notna()
    excluded_identity = int((~identity_valid).sum())
    df = df.loc[identity_valid].copy()
    accepted = pd.Series(False, index=df.index)
    summary = []
    duplicates = conflicts = 0
    if scada:
        groups = ((f'{desc} [{param}] ({unit})', unit, group, 'Data Value')
                  for (desc,param,unit), group in df.groupby(extra, sort=False))
    else:
        groups = ((name, '', df, name) for name in metrics)
    keys = ['district',*dimensions,'stamp']
    for name, unit, group, column in groups:
        family = metric_family(name,kind,unit)
        values = numerical(group[column], family)
        valid = values.notna()
        if not valid.any(): continue
        temp = group.loc[valid, keys].copy()
        temp['value'] = values.loc[valid]
        if 'cusec' in name.casefold() or unit.strip().casefold() == 'cusec':
            temp['value'] *= 0.028316846592
        # Conflicting repeated time/station readings are removed, not averaged.
        repeated = temp.duplicated(keys, keep=False)
        if repeated.any():
            dup = temp.loc[repeated]
            spread = dup.groupby(keys,sort=False)['value'].transform('nunique')
            conflict_ids = dup.index[spread.gt(1)]
            conflicts += len(conflict_ids)
            temp = temp.drop(index=conflict_ids)
            duplicate_ids = temp.duplicated(keys,keep='first')
            duplicates += int(duplicate_ids.sum())
            temp = temp.loc[~duplicate_ids]
        if temp.empty: continue
        accepted.loc[temp.index] = True
        temp['date'] = temp['stamp'].dt.normalize()
        series = ['district',*dimensions]
        station_days = temp.groupby([*series,'date'],sort=False)['value'].agg(['mean','size']).reset_index()
        if family in ('groundwater_level_change_m','surface_level_change_m'):
            station_days = station_days.sort_values('date')
            by_station = station_days.groupby(series,sort=False)
            day_gap = (station_days['date']-by_station['date'].shift()).dt.days
            station_days['mean'] = ((station_days['mean']-by_station['mean'].shift())/day_gap).where(day_gap.between(1,120))
            station_days = station_days.dropna(subset=['mean'])
        if family == 'wind_direction_deg':
            # Arithmetic averaging of headings would be misleading. Recompute circular components.
            import numpy as np
            temp['sin'] = np.sin(np.deg2rad(temp['value'])); temp['cos'] = np.cos(np.deg2rad(temp['value']))
            components = temp.groupby([*series,'date'],sort=False)[['sin','cos']].mean().reset_index()
            for axis in ('sin','cos'):
                stats = components.groupby(['district','date'],sort=False)[axis].agg(value='mean',station_days='size').reset_index()
                stats['samples'] = None; stats['family'] = family+'_'+axis; stats['metric'] = name
                summary.append(stats)
            continue
        if station_days.empty: continue
        g = station_days.groupby(['district','date'],sort=False)
        stats = g['mean'].agg(value='mean',station_days='size').reset_index()
        stats['samples'] = g['size'].sum().to_numpy()
        stats['family'] = family; stats['metric'] = name
        summary.append(stats)
    result = pd.concat(summary,ignore_index=True) if summary else pd.DataFrame(columns=['district','date','value','station_days','samples','family','metric'])
    result['date'] = pd.to_datetime(result['date']).dt.strftime('%Y-%m-%d')
    retained = int(accepted.sum())
    if supplement:
        previous = pd.read_csv(target)
        if previous['district'].eq('ahilyanagar').any() or scanned_subset > upgrade['rows_excluded_identity_or_timestamp']:
            raise ValueError('Alias supplement overlaps previously retained records')
        result = pd.concat([previous,result],ignore_index=True)
        excluded_identity += upgrade['rows_excluded_identity_or_timestamp']-scanned_subset
        retained += upgrade['rows_with_retained_observation']
        duplicates += upgrade['duplicate_observations_removed']
        conflicts += upgrade['conflicting_observations_removed']
    tmp = target.with_suffix('.part')
    result.to_csv(tmp,index=False,compression={'method':'gzip','compresslevel':3,'mtime':0})
    tmp.replace(target)
    report = {'version':VERSION,'resource_id':path.stem,'name':metadata['name'],'source_url':metadata['url'],
        'input_sha256':signature,'output_sha256':sha(target),'scanned_rows':total,
        'rows_with_retained_observation':retained,'rows_excluded_identity_or_timestamp':excluded_identity,
        'rows_without_retained_value':total-excluded_identity-retained,'duplicate_observations_removed':duplicates,
        'conflicting_observations_removed':conflicts,'district_day_metric_rows':len(result),'output':str(target)}
    atomic(receipt,report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--workers',type=int,default=3)
    args=parser.parse_args(argv)
    args.output.mkdir(parents=True,exist_ok=True)
    catalogue=read_json(Path('data/water/catalogue.json'))
    kinds={r['id']:r['kind'] for r in catalogue['resources']}
    directory=read_json(Path('docs/LIVE_DIRECTORY_IMPORT.json'))
    allowed={district_key(d['district_name']) for d in directory['districts']}
    allowed.update(('palghar','yavatmal','washim','gondia'))
    sources=sorted(ROOT.glob('*.metadata.json'))
    if len(sources)!=98:
        raise ValueError('Expected all 98 downloaded archives; refusing a partial full-history run')
    jobs=[(p.with_name(p.name.removesuffix('.metadata.json')+'.csv'),args.output,
           kinds[p.name.removesuffix('.metadata.json')],allowed) for p in sources]
    jobs.sort(key=lambda j:-j[0].stat().st_size)
    rows=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(one,job):job for job in jobs}
        for future in concurrent.futures.as_completed(futures):
            item=future.result(); rows.append(item)
            print(f'{len(rows)}/98: {item["name"]}: {item["scanned_rows"]:,} scanned, {item["district_day_metric_rows"]:,} district/day summaries',flush=True)
    counts={key:sum(r[key] for r in rows) for key in ('scanned_rows','rows_with_retained_observation',
        'rows_excluded_identity_or_timestamp','rows_without_retained_value','district_day_metric_rows',
        'duplicate_observations_removed','conflicting_observations_removed')}
    atomic(args.output/'manifest.json',{'version':VERSION,'resources':sorted(rows,key=lambda r:r['resource_id']),
        'counts':counts,'years':[2021,2025],'historical_publication_times_verified':False,
        'district_alias_sources':{'ahmadnagar':'https://divcomnashik.maharashtra.gov.in/en/ahmednagar-district/'},
        'actual_supply_targets':0,'geographic_scope':'publisher district name with explicit aliases; no village/service-area join'})
    print(json.dumps(counts),flush=True)


if __name__=='__main__':
    main()
