"""Export selected official records from 2021 onward, retaining source lineage."""
import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

from scripts.sync_water_data import download, read_date, stamp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('resource_id', help='Resource ID from the water-data catalogue')
    parser.add_argument('--before', default=str(datetime.now().year) + '-01-01', help='Exclusive cutoff; current year is held out by default')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cutoff = datetime.fromisoformat(args.before)
    if cutoff <= datetime(2021, 1, 1):
        raise ValueError('Cutoff must be after 2021-01-01')
    catalogue = json.loads(Path('data/water/catalogue.json').read_text(encoding='utf-8'))
    resource = next((r for r in catalogue['resources'] if r['id'] == args.resource_id), None)
    if not resource:
        raise ValueError('Resource is absent from the reviewed Maharashtra catalogue')
    raw, receipt = download(resource)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.part')
    count = rejected = 0
    with raw.open(encoding='utf-8-sig', newline='') as source, temporary.open('w', encoding='utf-8', newline='') as target:
        reader = csv.DictReader(source)
        fields = reader.fieldnames or []
        time_key = next((k for k in fields if 'acquisition time' in k.lower()), None)
        if not time_key:
            raise ValueError('Observation timestamp field requires review')
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for row in reader:
            observed = read_date(row.get(time_key))
            if observed is None or not (datetime(2021, 1, 1) <= observed < cutoff):
                rejected += 1
                continue
            state_key = next((k for k in fields if k.lower() == 'state'), None)
            if state_key and row[state_key].strip().lower() != 'maharashtra':
                rejected += 1
                continue
            writer.writerow(row)
            count += 1
    temporary.replace(args.output)
    report = dict(resource_id=resource['id'], source=resource['url'], retrieved_at=stamp(), source_receipt=receipt,
                  start_inclusive='2021-01-01', end_exclusive=args.before, exported_rows=count, excluded_rows=rejected,
                  sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),
                  limitations='Source rows require unit, instrument, missingness and issue-time review. No model is trained or approved by this export.')
    args.output.with_suffix('.metadata.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
