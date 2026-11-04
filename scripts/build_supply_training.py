"""Engineer supply inputs and 7/15-day examples without synthesizing labels."""
import argparse
import hashlib
import json
from datetime import date, datetime
from pathlib import Path

from services.worker.supply_features import IST, build_examples, derive_fields, sensitivity, validate_record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--operations', type=Path, help='Reviewed village daily JSONL; no public environmental file can substitute')
    p.add_argument('--issued-on', type=date.fromisoformat, default=datetime.now(IST).date())
    p.add_argument('--all-issue-dates', action='store_true', help='Build historical examples for each recorded day, with purged holdout boundary')
    p.add_argument('--scenarios', type=Path, help='JSON with explicit demand/inflow/storage bounds, capacity and delivery limit in litres')
    p.add_argument('--output', type=Path, default=Path('data/raw/supply/training'))
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    receipt = None
    if args.operations:
        content = args.operations.read_bytes()
        receipt = {'input':str(args.operations), 'sha256':hashlib.sha256(content).hexdigest()}
        for line in content.decode('utf-8-sig').splitlines():
            if not line.strip():continue
            r = validate_record(json.loads(line))
            if date.fromisoformat(r['date']) >= datetime.now(IST).date():
                raise ValueError('Only completed historical local days can be operational observations')
            records.append({**r, 'fields':derive_fields(r.get('fields', {}))})
    engineered = args.output/'engineered-operations.jsonl'
    with engineered.open('w', encoding='utf-8') as h:
        for r in records:h.write(json.dumps(r, allow_nan=False)+'\n')
    issue_dates = sorted({date.fromisoformat(r['date']) for r in records}) if args.all_issue_dates else [args.issued_on]
    rows = []
    for issued in issue_dates:rows.extend(build_examples(records, issued))
    dataset = args.output/'examples.jsonl'
    with dataset.open('w', encoding='utf-8') as h:
        for r in rows:h.write(json.dumps(r, allow_nan=False)+'\n')
    scenarios = None
    if args.scenarios:
        s = json.loads(args.scenarios.read_text(encoding='utf-8'))
        scenarios = sensitivity(s['daily_demand_litres'], s['daily_net_inflow_litres'], s['opening_storage_litres'],
                                s['capacity_litres'], s['delivery_limit_litres_per_day'])
        (args.output/'sensitivity.json').write_text(json.dumps(scenarios, indent=2), encoding='utf-8')
    eligible = [r for r in rows if r['supervised_eligible']]
    report = {'generated_at':datetime.now(IST).isoformat(), 'input_receipt':receipt, 'operations_rows':len(records),
        'examples':len(rows), 'eligible_training_rows':sum(r['split']=='train' for r in eligible),
        'eligible_holdout_rows':sum(r['split']=='holdout' for r in eligible),
        'labelled_rows':sum(r['label_enough'] is not None for r in rows),
        'dataset_sha256':hashlib.sha256(dataset.read_bytes()).hexdigest(), 'model_trained':False,
        'status':'candidate_examples_require_dataset_review' if eligible else 'blocked_no_eligible_measured_supply_labels',
        'rules':['No 2011 inputs, fabricated population, zero-filled missing supply, invented source connections or simulated training targets.',
            'Measured, operator-reported, derived, assumed and modelled fields remain separate with operand lineage.',
            'Training horizons must end before 2026-01-01; straddling horizons are purged; 2026 remains holdout.',
            'Observed shortage or a balance from measured independent demand and measured user delivery must cover every future day and the complete named service scope.',
            'Minimum candidate history gate: seven complete known delivery days plus opening storage; this does not establish sufficient sample size.',
            'Public surface-flow features need reviewed connections, instrument overlap reconciliation and original publication times before joining.'],
        'missing_requirements':[] if eligible else ['Reviewed daily village/scope operations, measured unmet demand and complete 7/15-day follow-up']}
    (args.output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':main()
