"""Train offline 7/15-day supply-urgency (0-5) or binary sufficiency candidates.

Measured mode reads reviewed operations. Explicit simulation mode uses separate
simulated bundles/artifacts. No network, database, downloads or app forecasts.
"""
import argparse
import csv
import hashlib
import json
import os
import platform
import sys
import time
from collections import Counter
from datetime import date, datetime, time as day_time, timedelta
from pathlib import Path
from uuid import uuid4

from services.worker.supply_features import (
    IST, UNITS, derive_fields, examples_from_index, index_records, instant, validate_record,
)
from services.worker.supply_urgency import POLICY as URGENCY_POLICY, read_labels

DEFAULT_OPERATIONS = Path('data/raw/supply/operations')
DEFAULT_URGENCY_LABELS = Path('data/raw/supply/urgency-labels.csv')
CSV_META = {'village_id', 'date', 'scope', 'available_at', 'basis', 'evidence_source',
            'measurement_method', 'complete_day', 'coverage_verified',
            'demand_independent_of_supply_verified', 'notes'}
FIELD_META = ('basis', 'source', 'method', 'available_at', 'observed_on')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''):h.update(block)
    return h.hexdigest()


def write_json(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=True, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def flag(value):
    if value in (None, ''):return False
    if str(value).strip().lower() not in ('true', 'false'):
        raise ValueError('Verification flags must be true or false')
    return str(value).strip().lower() == 'true'


def from_csv(row):
    """Empty numeric cells stay missing; evidence metadata is explicitly supplied."""
    if None in row or any(v is None for v in row.values()):
        raise ValueError('CSV row has a different number of columns from its header')
    record = {k:row.get(k, '').strip() for k in ('village_id', 'date', 'scope')}
    for key in ('complete_day', 'coverage_verified', 'demand_independent_of_supply_verified'):
        record[key] = flag(row.get(key))
    fields = {}
    for name, unit in UNITS.items():
        raw = row.get(name, '').strip()
        if not raw:continue
        item = {'value':float(raw), 'unit':unit,
            'basis':row.get(name+'_basis', '').strip() or row.get('basis', '').strip(),
            'source':row.get(name+'_source', '').strip() or row.get('evidence_source', '').strip(),
            'method':row.get(name+'_method', '').strip() or row.get('measurement_method', '').strip(),
            'available_at':row.get(name+'_available_at', '').strip() or row.get('available_at', '').strip()}
        if row.get(name+'_observed_on'):item['observed_on'] = row[name+'_observed_on'].strip()
        fields[name] = item
    record['fields'] = fields
    return record


def discover(paths):
    found = set()
    for path in paths:
        path = path.resolve()
        if path.is_file():
            if path.suffix.lower() not in ('.csv', '.jsonl'):raise ValueError('Operations must be CSV or JSONL: '+str(path))
            found.add(path)
        elif path.is_dir():
            found.update(p.resolve() for p in path.rglob('*') if p.is_file() and p.suffix.lower() in ('.csv', '.jsonl'))
        elif path != DEFAULT_OPERATIONS.resolve():
            raise ValueError('Operations path does not exist: '+str(path))
    return sorted(found)


def read_operations(paths, now):
    records, receipts = [], []
    for path in paths:
        before = digest(path)
        count = 0
        with path.open(encoding='utf-8-sig', newline='') as stream:
            if path.suffix.lower() == '.csv':
                reader = csv.DictReader(stream)
                headers = reader.fieldnames or []
                allowed = CSV_META | set(UNITS) | {k+'_'+m for k in UNITS for m in FIELD_META}
                if not {'village_id','date','scope'}.issubset(headers) or len(headers) != len(set(headers)) or set(headers)-allowed:
                    raise ValueError('Unrecognized operations CSV header: '+str(path)+'. Use templates/village_supply_daily.csv; NWIC context files are not village operations.')
                items = ((line, from_csv(row)) for line,row in enumerate(reader, 2) if any(row.values()))
            else:
                items = ((line, json.loads(text)) for line,text in enumerate(stream, 1) if text.strip())
            try:
                for line, record in items:
                    validate_record(record)
                    if not record.get('fields'):raise ValueError('No operational values')
                    if date.fromisoformat(record['date']) >= now.date():
                        raise ValueError('Operations must cover completed India-local days, not today/future plans')
                    fields = record['fields']
                    # Recompute derived fields from operands; do not accept invented formula labels.
                    operands = {k:v for k,v in fields.items() if v['basis'] != 'derived'}
                    derived = derive_fields(operands)
                    for key,item in fields.items():
                        if item['basis'] == 'derived' and key not in derived:
                            raise ValueError('Derived value lacks supported operands: '+key)
                    record = {**record, 'fields':derived}
                    validate_record(record)
                    records.append(record);count += 1
            except (KeyError, ValueError, TypeError, AttributeError) as e:
                raise ValueError(f'{path}: invalid row near {count+1}: {e}') from e
        if digest(path) != before:raise ValueError('Operations file changed while reading: '+str(path))
        receipts.append({'path':str(path), 'sha256':before, 'records':count})
        print(f'Read {count:,} daily records from {path.name}', flush=True)
    return records, receipts


def prepare_examples(records, run_dir, scope, now, target='sufficiency', urgency_labels=None):
    urgency_labels = urgency_labels or {}
    counts = Counter(r['scope'] for r in records)
    selected = [r for r in records if r['scope'] == scope]
    groups = index_records(selected)
    rows, exclusions = [], Counter()
    with (run_dir/'engineered-operations.jsonl').open('w', encoding='utf-8') as f:
        for r in selected:f.write(json.dumps(r, allow_nan=False)+'\n')
    # Index once: all dates in a village reuse the same validated history.
    with (run_dir/'examples.jsonl').open('w', encoding='utf-8') as f:
        for key, history in sorted(groups.items()):
            dates = set(history)
            if target == 'urgency':
                dates.update(date.fromisoformat(k[2]) for k in urgency_labels if k[:2] == key)
            for issued in sorted(dates):
                for r in examples_from_index({key:history}, issued, holdout_from=date(9999,1,1), as_of=now):
                    latest = max((instant(e['available_at']) for e in r['label_evidence']), default=None)
                    compact = {k:r[k] for k in ('village_id','scope','issued_on','horizon_days','features',
                        'label_enough','label_shortage_litres','label_days_available','supervised_eligible')}
                    if target == 'urgency':
                        label = urgency_labels.get((key[0],key[1],r['issued_on'],r['horizon_days']))
                        history_ready = (r['features']['delivered_litres_previous_7d_count'] == 7
                                         and r['features']['opening_storage_litres'] is not None)
                        compact['label_urgency_level'] = label['level'] if label else None
                        compact['urgency_label_evidence'] = label
                        compact['supervised_eligible'] = bool(label and history_ready)
                        latest = instant(label['available_at']) if label else None
                    compact['latest_label_available_at'] = latest.isoformat() if latest else None
                    f.write(json.dumps(compact, allow_nan=False)+'\n')
                    if compact['supervised_eligible']:rows.append(compact)
                    else:exclusions['missing_reviewed_outcomes_or_previous_delivery_storage' if target=='urgency'
                                    else 'incomplete_measured_labels_or_previous_delivery_storage'] += 1
    return rows, {'scope_records':dict(counts), 'selected_scope':scope, 'selected_records':len(selected),
                  'villages':len(groups), 'eligible_examples':len(rows), 'excluded_examples':dict(exclusions)}


def split_examples(rows, validation_from=None, purge_days=15, min_train=100, min_validation=30, min_class=5, target='sufficiency'):
    dates = sorted({r['issued_on'] for r in rows})
    if len(dates) < 2:return None, {}, ['No eligible 7/15-day outcome labels with previous delivery/storage history.']
    cutoff = validation_from or date.fromisoformat(dates[min(len(dates)-1, int(len(dates)*.8))])
    cutoff_at = datetime.combine(cutoff, day_time.min, IST)
    train_end = cutoff-timedelta(days=purge_days)
    parts, problems = {}, []
    for horizon in (7,15):
        train, validation, excluded = [], [], Counter()
        for row in rows:
            if row['horizon_days'] != horizon:continue
            issue = date.fromisoformat(row['issued_on'])
            end = issue+timedelta(days=horizon-1)
            if issue >= cutoff:validation.append(row)
            elif end < train_end and instant(row['latest_label_available_at']) <= cutoff_at:train.append(row)
            else:excluded['purge_overlap_or_labels_unavailable_at_training_cutoff'] += 1
        def class_name(row):
            return str(row['label_urgency_level']) if target=='urgency' else 'enough' if row['label_enough'] else 'shortage'
        required_classes = tuple(str(n) for n in range(6)) if target=='urgency' else ('enough','shortage')
        train_classes = Counter(class_name(r) for r in train)
        val_classes = Counter(class_name(r) for r in validation)
        if len(train) < min_train:problems.append(f'{horizon} days: {len(train)} training rows; at least {min_train} required.')
        if len(validation) < min_validation:problems.append(f'{horizon} days: {len(validation)} validation rows; at least {min_validation} required.')
        for name, classes in [('training',train_classes),('validation',val_classes)]:
            if any(classes[c] < min_class for c in required_classes):
                problems.append(f'{horizon} days: {name} needs at least {min_class} observed examples of each class ({", ".join(required_classes)}).')
        parts[horizon] = {'train':train, 'validation':validation, 'summary':{
            'training_rows':len(train), 'validation_rows':len(validation),
            'training_classes':dict(train_classes), 'validation_classes':dict(val_classes),
            'training_issue_range':[min((r['issued_on'] for r in train),default=None), max((r['issued_on'] for r in train),default=None)],
            'validation_issue_range':[min((r['issued_on'] for r in validation),default=None), max((r['issued_on'] for r in validation),default=None)],
            'validation_unique_issue_dates':len({r['issued_on'] for r in validation}),
            'excluded':dict(excluded)}}
    return cutoff, parts, problems


def metrics(y, probability, baseline_probability):
    import numpy as np
    y = np.asarray(y, dtype=int)
    probability = np.asarray(probability, dtype=float)
    predicted = probability >= .5
    tp,fn = int(((y==1)&predicted).sum()),int(((y==1)&~predicted).sum())
    fp,tn = int(((y==0)&predicted).sum()),int(((y==0)&~predicted).sum())
    brier = float(((probability-y)**2).mean())
    baseline_brier = float(((baseline_probability-y)**2).mean())
    return {'samples':len(y), 'accuracy':float((predicted==y).mean()),
        'shortage_recall':tp/(tp+fn) if tp+fn else None, 'shortage_precision':tp/(tp+fp) if tp+fp else None,
        'brier_score':brier, 'train_prevalence_baseline_brier':baseline_brier,
        'beats_baseline_brier':brier < baseline_brier,
        'confusion':{'true_shortage':tp,'missed_shortage':fn,'false_shortage':fp,'true_enough':tn}}


def urgency_metrics(y, probability, baseline):
    import numpy as np
    y = np.asarray(y, dtype=int);probability = np.asarray(probability, dtype=float)
    if probability.shape != (len(y),6) or not np.isfinite(probability).all():raise ValueError('Expected six finite class probabilities')
    predicted = probability.argmax(axis=1)
    confusion = [[int(((y==i)&(predicted==j)).sum()) for j in range(6)] for i in range(6)]
    one_hot = np.eye(6)[y]
    brier = float(((probability-one_hot)**2).sum(axis=1).mean())
    baseline_brier = float(((np.asarray(baseline)-one_hot)**2).sum(axis=1).mean())
    critical = y == 5
    return {'samples':len(y),'accuracy':float((predicted==y).mean()),
        'mean_absolute_level_error':float(np.abs(predicted-y).mean()),
        'within_one_level_accuracy':float((np.abs(predicted-y)<=1).mean()),
        'level_5_recall':float((predicted[critical]==5).mean()) if critical.any() else None,
        'missed_level_5_cases':int((critical&(predicted<5)).sum()),
        'severely_underestimated_level_5_cases':int((critical&(predicted<4)).sum()),
        'brier_score':brier,'train_prevalence_baseline_brier':baseline_brier,
        'beats_baseline_brier':brier<baseline_brier,'confusion_rows_actual_columns_predicted':confusion}


def fit_candidates(parts, run_dir, trees=200, threads=4, target='sufficiency', *, policy=None, simulated=False):
    import numpy as np
    import xgboost
    models = []
    policy = policy or URGENCY_POLICY
    for horizon, part in sorted(parts.items()):
        train, validation = part['train'], part['validation']
        names = sorted(set().union(*(r['features'] for r in train)))
        def matrix(rows):
            return np.asarray([[r['features'].get(k) if r['features'].get(k) is not None else np.nan for k in names] for r in rows], dtype=np.float32)
        def target_value(row):return row['label_urgency_level'] if target=='urgency' else int(not row['label_enough'])
        y = np.asarray([target_value(r) for r in train])
        y_val = np.asarray([target_value(r) for r in validation])
        # Train-only constant features are removed; no validation-based selection/tuning.
        x = matrix(train); xv = matrix(validation)
        keep = [i for i in range(len(names)) if len(np.unique(x[:,i][np.isfinite(x[:,i])])) > 1]
        if not keep:raise ValueError('No varying training features after missing/constant filtering')
        x, xv, names = x[:,keep], xv[:,keep], [names[i] for i in keep]
        objective = {'objective':'multi:softprob','num_class':6,'eval_metric':'mlogloss'} if target=='urgency' else {
            'objective':'binary:logistic','eval_metric':'logloss'}
        model = xgboost.XGBClassifier(n_estimators=trees, max_depth=4, learning_rate=.05,
            subsample=.85, colsample_bytree=.9, random_state=1729, n_jobs=threads,
            **objective, tree_method='hist', device='cpu')
        print(f'Training {horizon}-day candidate: {len(train):,} rows; validating on {len(validation):,} held-out rows...', flush=True)
        started = time.perf_counter()
        model.fit(x, y)
        all_probability = model.predict_proba(xv)
        scores = urgency_metrics(y_val, all_probability, np.bincount(y,minlength=6)/len(y)) if target=='urgency' else metrics(y_val, all_probability[:,1], float(y.mean()))
        prefix = 'simulated-' if simulated else ''
        model_path = run_dir/f'{prefix}{"urgency" if target=="urgency" else "supply"}-{horizon}d.json'
        model.save_model(model_path)
        # Verify the saved artifact independently loads with identical validation output.
        restored = xgboost.XGBClassifier();restored.load_model(model_path)
        if not np.allclose(restored.predict_proba(xv), all_probability, rtol=1e-6, atol=1e-7):
            raise ValueError('Saved-model roundtrip mismatch')
        archive_splits = {names[int(key[1:])]:count for key,count in model.get_booster().get_score(importance_type='weight').items()
                          if key.startswith('f') and key[1:].isdigit() and names[int(key[1:])].startswith('archive_')}
        models.append({'horizon_days':horizon, 'artifact':model_path.name, 'sha256':digest(model_path),
            'features':names,
            'archive_input_features':sum(name.startswith('archive_') for name in names),
            'archive_features_used_in_splits':len(archive_splits),
            'training_data_basis':'simulated' if simulated else 'reviewed_operations',
            **({'classes':policy['levels'],'policy_version':policy['version'],
                'output_type':'ordered_six_class_label_0_to_5','probabilities_calibrated':False}
               if target=='urgency' else {'positive_class':'shortage_on_any_day_in_horizon', 'negative_class':'enough_on_every_day'}),
            'fit_and_validation_seconds':round(time.perf_counter()-started,3), 'metrics':scores,
            'split':part['summary'], 'xgboost_version':xgboost.__version__})
    return models


def run(args):
    if args.data_mode == 'simulation':
        return run_simulation(args)
    started = time.perf_counter()
    now = datetime.now(IST)
    folder = args.output/(now.strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:6])
    folder.mkdir(parents=True, exist_ok=False)
    report = {'status':'checking_local_data', 'offline':True, 'model_trained':False, 'approved':False,
        'generated_at':now.isoformat(), 'target':'water_supply_urgency_0_to_5' if args.target=='urgency' else 'village_water_supply_sufficiency', 'horizons':[7,15],
        'training_mode':args.target,
        'scope':args.scope, 'python_version':platform.python_version(), 'input_files':[],
        'network_calls':0, 'database_access':False, 'app_forecasts_published':False,
        'drought_intensity':{'included_in_training':False, 'status':'not_implemented',
            'requirement':'docs/DROUGHT_INTENSITY_REQUIREMENT.md',
            'reason':'Supply shortage events are not drought severity labels. Dated drought-index observations, reference periods and spatial mappings remain required.'},
        'environmental_archive_use':'Not automatically used: river/groundwater/weather rows are not village supply targets; reviewed joins and issue-time availability are still required.',
        'assumptions_file':'docs/SUPPLY_DATA_FEATURES_AND_ASSUMPTIONS.md',
        'release_blockers':['Research candidate only; independent village/season validation, calibration and prospective review remain required.']}
    if args.target=='urgency':report['urgency_policy'] = URGENCY_POLICY
    exit_code = 2
    try:
        files = discover(args.operations or [DEFAULT_OPERATIONS])
        print(f'Offline mode. Found {len(files)} local operations file(s). No API or Neon connection.', flush=True)
        records, receipts = read_operations(files, now)
        report['input_files'] = receipts
        report['operation_records'] = len(records)
        labels, label_receipts = {}, []
        if args.target=='urgency':
            paths = args.urgency_labels or ([DEFAULT_URGENCY_LABELS] if DEFAULT_URGENCY_LABELS.exists() else [])
            labels, label_receipts = read_labels(paths, now)
            report['urgency_label_input_files'] = label_receipts
            report['urgency_labels'] = len(labels)
        rows, summary = prepare_examples(records, folder, args.scope, now, args.target, labels)
        report['data'] = summary
        cutoff, parts, problems = split_examples(rows, args.validation_from, min_train=args.min_train_rows,
            min_validation=args.min_validation_rows, min_class=args.min_class_rows, target=args.target)
        report.update(validation_from=cutoff.isoformat() if cutoff else None,
            temporal_split='Latest 20% of eligible issue dates held out unless explicit cutoff; training labels end at least 15 calendar days before validation starts and must have been available at that cutoff.',
            partitions={str(h):p['summary'] for h,p in parts.items()})
        if problems:
            report.update(status='blocked_missing_measured_supply_training_data', problems=problems,
                next_step='Add reviewed daily operations under data/raw/supply/operations and, for urgency mode, observed 0-5 outcome labels in data/raw/supply/urgency-labels.csv. Then rerun. No NWIC source flow or simulated emergency labels can substitute.')
            print('Training did not start: suitable reviewed village outcomes/history are missing or insufficient.', flush=True)
            for problem in problems:print('  '+problem, flush=True)
        elif args.check_only:
            report.update(status='ready_for_offline_candidate_training', problems=[])
            exit_code = 0
            print('Both horizons pass the candidate data checks. Check-only: no models trained.', flush=True)
        else:
            models = fit_candidates(parts, folder, args.trees, args.threads, args.target)
            report.update(status='trained_research_candidates', model_trained=True, models=models,
                baseline_comparison_passed=all(m['metrics']['beats_baseline_brier'] for m in models))
            if not report['baseline_comparison_passed']:
                report['release_blockers'].append('One or both horizons failed the held-out train-prevalence Brier baseline.')
            exit_code = 0
            print('Saved both research candidates. No application predictions were created.', flush=True)
    except (ValueError, KeyError, TypeError, OSError, ImportError) as error:
        report.update(status='blocked_invalid_inputs_or_missing_dependency', problems=[str(error)], error_class=type(error).__name__)
        print('Training stopped: '+str(error), file=sys.stderr, flush=True)
    except Exception as error:
        report.update(status='training_failed', problems=[str(error)], error_class=type(error).__name__)
        print('Training failed: '+str(error), file=sys.stderr, flush=True)
        exit_code = 1
    report['total_seconds'] = round(time.perf_counter()-started,3)
    report['exit_code'] = exit_code
    write_json(folder/'training-report.json', report)
    write_json(args.output/'latest-run.json', {'run_directory':str(folder.resolve()), 'report':str((folder/'training-report.json').resolve()),
        'status':report['status'], 'model_trained':report['model_trained'], 'exit_code':exit_code})
    print('Report: '+str((folder/'training-report.json').resolve()), flush=True)
    return exit_code


def run_simulation(args):
    from scripts.simulation_training_data import load_parts
    from services.worker.supply_simulation import POLICY
    started = time.perf_counter()
    folder = args.output/(datetime.now(IST).strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:6])
    folder.mkdir(parents=True, exist_ok=False)
    report = {'status':'checking_simulation_data', 'offline':True, 'training_data_basis':'simulated',
        'training_mode':args.target, 'scope':args.scope, 'horizons':[7,15], 'model_trained':False,
        'approved':False, 'network_calls':0, 'database_access':False, 'app_forecasts_published':False,
        'urgency_policy':POLICY, 'generated_at':datetime.now(IST).isoformat(),
        'release_blockers':['Simulation-only prototype. Validation measures agreement with the simulator, not real-world supply accuracy.',
                            'Actual village supply/outcomes and independent validation are required before operational use.'],
        'assumptions_file':'docs/SIMULATED_SUPPLY_TRAINING.md'}
    report['drought_intensity'] = {'included_in_training':False, 'status':'not_implemented',
        'reason':'Simulated operational urgency is not official climate-drought intensity.'}
    code = 2
    try:
        if args.operations or args.urgency_labels or args.validation_from or args.scope != 'whole_village':
            raise ValueError('Simulation mode uses its own whole-village bundle and recorded split; do not mix measured paths or temporal-cutoff flags.')
        directory = args.simulation_dataset or Path('data/raw/supply/simulation')
        print('SIMULATION mode: hypothetical supply/outcomes only. No network or Neon connection.', flush=True)
        parts, manifest, path, problems = load_parts(directory, target=args.target,
            min_train=args.min_train_rows, min_validation=args.min_validation_rows, min_class=args.min_class_rows)
        report.update(dataset_manifest=str(path.resolve()), dataset_manifest_sha256=digest(path),
            dataset_counts=manifest['counts'], assumptions=manifest['assumptions'],
            partitions={str(h):part['summary'] for h,part in parts.items()},
            validation_meaning=manifest['split'], problems=problems)
        if manifest.get('dataset_kind') == 'archive_conditioned':
            report.update(dataset_kind='archive_conditioned', actual_environmental_inputs=manifest['actual_environmental_inputs'],
                          actual_supply_targets=0, assumptions_file='docs/HISTORICAL_SUPPLY_TRAINING.md')
        if problems:
            report['status'] = 'blocked_insufficient_simulation_data'
            for problem in problems:print(problem, flush=True)
        elif args.check_only:
            code = 0;report['status'] = 'ready_for_simulation_prototype_training'
            print('Both horizons pass simulation data checks. No models trained.', flush=True)
        else:
            models = fit_candidates(parts, folder, args.trees, args.threads, args.target, policy=POLICY, simulated=True)
            report.update(status='trained_simulation_prototypes', model_trained=True, models=models,
                baseline_comparison_passed=all(model['metrics']['beats_baseline_brier'] for model in models))
            code = 0
            print('Saved two SIMULATION prototypes. No operational forecasts or real-world validation claimed.', flush=True)
    except (ValueError, KeyError, TypeError, OSError, ImportError) as error:
        report.update(status='blocked_invalid_simulation_data', problems=[str(error)])
        print('Simulation check stopped: '+str(error), file=sys.stderr, flush=True)
    except Exception as error:
        code = 1;report.update(status='simulation_training_failed', problems=[str(error)])
    report.update(total_seconds=round(time.perf_counter()-started,3), exit_code=code)
    write_json(folder/'training-report.json', report)
    write_json(args.output/'latest-run.json', {'run_directory':str(folder.resolve()),
        'report':str((folder/'training-report.json').resolve()), 'status':report['status'],
        'model_trained':report['model_trained'], 'exit_code':code})
    print('Report: '+str((folder/'training-report.json').resolve()), flush=True)
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-mode', choices=['measured','simulation'], default='measured', help='Simulation must be selected explicitly; never mixes with measured records')
    parser.add_argument('--simulation-dataset', type=Path, help='Simulation bundle directory or parent with latest.json')
    parser.add_argument('--operations', type=Path, action='append', help='Local CSV/JSONL file or folder; repeat to combine all records. Default: data/raw/supply/operations')
    parser.add_argument('--output', type=Path, help='New timestamped run directory; default separates measured and simulated model artifacts')
    parser.add_argument('--scope', choices=['whole_village','household'], default='whole_village')
    parser.add_argument('--target', choices=['urgency','sufficiency'], default='urgency', help='Default: six urgency classes 0-5. Sufficiency preserves the earlier binary enough/shortage training.')
    parser.add_argument('--urgency-labels', type=Path, action='append', help='Reviewed observed-outcome CSV/JSONL, separate from daily operations. Default: data/raw/supply/urgency-labels.csv')
    parser.add_argument('--validation-from', type=date.fromisoformat, help='Optional first held-out issue date; default latest 20%% of issue dates')
    parser.add_argument('--check-only', action='store_true', help='Read and validate local records without fitting models')
    parser.add_argument('--trees', type=int, default=200)
    parser.add_argument('--threads', type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument('--min-train-rows', type=int, default=100)
    parser.add_argument('--min-validation-rows', type=int, default=30)
    parser.add_argument('--min-class-rows', type=int, default=5)
    args = parser.parse_args(argv)
    if args.simulation_dataset and args.data_mode != 'simulation':
        parser.error('--simulation-dataset requires explicit --data-mode simulation')
    args.output = args.output or Path('artifacts/supply-simulation-models' if args.data_mode == 'simulation' else 'artifacts/supply-offline')
    if not 1 <= args.trees <= 5000 or not 1 <= args.threads <= 64:parser.error('Use 1-5000 trees and 1-64 CPU threads')
    if args.min_train_rows < 20 or args.min_validation_rows < 10 or args.min_class_rows < 2:
        parser.error('Minimum data checks cannot be below 20 training, 10 validation and 2 examples per class')
    return run(args)


if __name__ == '__main__':raise SystemExit(main())
