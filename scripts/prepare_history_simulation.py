"""Use screened actual archive summaries in a separate simulated supply bundle."""
import argparse
import csv
import gzip
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean, median
from uuid import uuid4

from scripts.aggregate_supply_history import OUT, VERSION as ARCHIVE_VERSION, district_key, read_json, atomic, sha
from scripts.prepare_supply_data import stream_rows
from services.worker.supply_features import IST
from services.worker.supply_simulation import ASSUMPTIONS, POLICY, VERSION, simulate

HOLDOUT = date(2025, 1, 1)
DELAY = 2


def historical_partition(issued):
    if issued >= HOLDOUT:
        return 'validation'
    if issued+timedelta(days=29) < HOLDOUT:
        return 'train'
    return None


def feature_name(family, metric):
    if family in ('water_quality','other'):
        normalized = ' '.join(metric.casefold().split())
        suffix = re.sub(r'[^a-z0-9]+','_',normalized).strip('_')[:45]
        return family+'_'+suffix+'_'+hashlib.sha256(normalized.encode()).hexdigest()[:8]
    return family


def archive_inputs(root):
    manifest = read_json(root/'manifest.json')
    if manifest['version'] != ARCHIVE_VERSION or len(manifest['resources']) != 98 or manifest['counts']['scanned_rows'] != 39240902:
        raise ValueError('Full 98-resource archive audit is required')
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    counts = Counter(); fields = {}
    for source in manifest['resources']:
        path = Path(source['output'])
        if sha(path) != source['output_sha256']:
            raise ValueError('Archive summary hash mismatch: '+source['resource_id'])
        with gzip.open(path,'rt',encoding='utf-8',newline='') as stream:
            for row in csv.DictReader(stream):
                value = float(row['value']); counts['resource_summaries_read'] += 1
                if not math.isfinite(value) or abs(value)>1e12:
                    counts['resource_summaries_outside_numeric_bounds'] += 1; continue
                name = feature_name(row['family'],row['metric'])
                if row['family'] in ('groundwater_level_change_m','surface_level_change_m'):
                    value = abs(value)  # Magnitude, not a directional groundwater/surface-water proxy.
                data[row['district']][date.fromisoformat(row['date'])][name].append(value)
                fields[name] = row['family'] if row['family'] not in ('water_quality','other') else row['metric']
    return {district:{day:{key:median(values) for key,values in metrics.items()}
                      for day,metrics in days.items()} for district,days in data.items()}, counts, manifest, fields


def archived_features(days, issue):
    lag = days.get(issue-timedelta(days=DELAY),{})
    features = {'archive_'+name+'_lag2':value for name,value in lag.items()}
    for length in (7,30):
        observations = defaultdict(list)
        for i in range(DELAY,DELAY+length):
            for key,value in days.get(issue-timedelta(days=i),{}).items():
                observations[key].append(value)
        for key,values in observations.items():
            features[f'archive_{key}_prior{length}_mean'] = mean(values)
            features[f'archive_{key}_prior{length}_days'] = len(values)
    return features


def climate_drivers(days, issue, fallback):
    result=[]; counts=Counter()
    for i in range(45):
        observed=issue+timedelta(days=i-30)
        past_unavailable=i==29  # Issue minus one day is outside the assumed delay.
        actual={} if past_unavailable else days.get(observed,{})
        alternative=fallback[i % len(fallback)]
        rain=actual.get('daily_rain_mm'); temp=actual.get('air_temperature_c')
        counts['actual_rain_days' if rain is not None else 'fallback_rain_days']+=1
        counts['actual_temperature_days' if temp is not None else 'fallback_temperature_days']+=1
        result.append({'for_date':observed.isoformat(),'district_code_as_reported':alternative['district_code_as_reported'],
            'rain':alternative['rain'] if rain is None else rain,'temp_avg':alternative['temp_avg'] if temp is None else temp,
            'rain_basis':'archive_daily_rain' if rain is not None else 'illustrative_pocra_template',
            'temperature_basis':'archive_station_temperature' if temp is not None else 'illustrative_pocra_template'})
    return result,counts


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context',type=Path,default=OUT)
    parser.add_argument('--output',type=Path,default=Path('data/raw/supply/history-simulation'))
    parser.add_argument('--seed',type=int,default=1729)
    args=parser.parse_args(argv)
    data,counts,audit,fields=archive_inputs(args.context)
    profiles_path=Path('data/raw/supply/public-completion/jjm/village-households.jsonl')
    weather_path=Path('data/raw/supply/public-completion/pocra/weather-district-context.jsonl')
    input_hashes={p:sha(p) for p in (profiles_path,weather_path)}
    profiles=defaultdict(list); weather=defaultdict(list)
    for row in stream_rows(profiles_path): profiles[district_key(row['district'])].append(row)
    for row in stream_rows(weather_path): weather[district_key(row['district'])].append(row)
    for rows in profiles.values(): rows.sort(key=lambda row:row['jjm_village_id'])
    for rows in weather.values(): rows.sort(key=lambda row:row['for_date'])
    now=datetime.now(IST); folder=args.output/(now.strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:6]);folder.mkdir(parents=True)
    episodes=folder/'simulated-daily-episodes.jsonl.gz'; examples=folder/'simulated-examples.jsonl.gz'
    classes=defaultdict(Counter); coverage={}
    with gzip.open(episodes,'wt',encoding='utf-8',compresslevel=3) as daily, gzip.open(examples,'wt',encoding='utf-8',compresslevel=3) as training:
        for district,days in sorted(data.items()):
            seen=Counter()
            if not profiles.get(district) or not weather.get(district):
                seen['district_days_without_scenario_template']=len(days);counts.update(seen);coverage[district]=dict(seen);continue
            for anchor in sorted(days):
                issue=anchor+timedelta(days=DELAY)
                split=historical_partition(issue)
                if split is None or issue<date(2021,1,31):
                    seen['anchor_days_purged_or_warmup']+=1;continue
                key=f'{district}:{issue.isoformat()}'
                sample=int(hashlib.sha256(key.encode()).hexdigest()[:12],16)%len(profiles[district])
                original=profiles[district][sample]
                profile={**original,'jjm_village_id':original['jjm_village_id']+'@'+issue.isoformat()}
                drivers,driver_counts=climate_drivers(days,issue,weather[district]);seen.update(driver_counts)
                episode,rows=simulate(profile,drivers,args.seed,rotate_weather=False)
                features=archived_features(days,issue)
                episode.update(partition=split,issued_on=issue.isoformat(),archive_max_observed_on=anchor.isoformat(),
                    archive_district=district,archived_features=features,source_profile_id='jjm:'+original['jjm_village_id'],
                    climate_driver_basis=[[row['rain_basis'],row['temperature_basis']] for row in drivers])
                daily.write(json.dumps(episode,separators=(',',':'),allow_nan=False)+'\n')
                seen['episodes']+=1;seen['archived_feature_values']+=len(features)
                for row in rows:
                    row.update(partition=split,issued_on=issue.isoformat(),features={**row['features'],**features})
                    training.write(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n')
                    classes[f"{row['horizon_days']}d_{split}"][str(row['label_urgency_level'])]+=1
                    seen['examples']+=1
            counts.update(seen);coverage[district]=dict(seen)
            print(f'{district}: {seen["episodes"]:,} episodes; total {counts["episodes"]:,}',flush=True)
    if any(sha(path)!=digest for path,digest in input_hashes.items()):
        raise ValueError('A scenario input changed while the bundle was being built')
    audit_copy=folder/'archive-audit.json';atomic(audit_copy,audit)
    manifest={'schema_version':VERSION,'dataset_kind':'archive_conditioned','basis':'simulated','seed':args.seed,
        'created_at':now.isoformat(),'counts':dict(counts),'coverage_by_district':coverage,'archived_feature_dictionary':fields,
        'actual_environmental_inputs':audit['counts'],'archive_audit_file':audit_copy.name,
        'archive_audit_sha256':sha(audit_copy),'actual_supply_targets':0,
        'urgency_classes':{key:dict(value) for key,value in classes.items()},'policy':POLICY,
        'assumptions':{**ASSUMPTIONS,'weather':'Actual district-day rainfall and air-temperature aggregates where present; missing inputs use explicitly marked PoCRA example values within the simulator only.',
                       'archive_availability':'Archive predictors end at issue minus two days, an assumed delay rather than verified publication. The PoCRA fallback is illustrative, from a later snapshot; this is not a real historical forecast.',
                       'archive_metric_aggregation':'Median of resource/metric district-day summaries with compatible units. Levels use magnitude of within-station change, not inferred supply. No flows are summed or converted to delivery.',
                       'actual_context':'Sparse district/date predictors. Missing archive feature values remain missing. District aliases are not service-area links.'},
        'holdout_from':HOLDOUT.isoformat(),'archive_input_delay_days':DELAY,
        'split':'Reference dates 2021–2024 for training with a 15-day gap after the last training label window; 2025 onward for validation. Outcomes are simulated, not a real-supply backtest.',
        'inputs':[{'path':str(p),'sha256':digest} for p,digest in input_hashes.items()],
        'files':{'episodes':{'name':episodes.name,'sha256':sha(episodes)},'examples':{'name':examples.name,'sha256':sha(examples)}},
        'real_operations_written':0,'real_urgency_labels_written':0,'model_trained':False,'network_calls':0}
    manifest_path=folder/'simulation-manifest.json';atomic(manifest_path,manifest)
    atomic(args.output/'latest.json',{'dataset_directory':str(folder.resolve()),'manifest':str(manifest_path.resolve())})
    print(json.dumps({'dataset':str(folder),'counts':dict(counts),'classes':manifest['urgency_classes']},indent=2),flush=True)


if __name__=='__main__':main()
