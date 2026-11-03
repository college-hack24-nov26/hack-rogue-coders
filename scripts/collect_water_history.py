"""Resumable official historical downloads, date profiling and 2021+ candidate exports.

Preserves source columns/units. This is not model training or quality approval.
"""
import argparse
import concurrent.futures
import csv
import hashlib
import json
import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
import httpx

from scripts.sync_water_data import OUT, RAW, atomic, official_url, read_date, stamp

# Reviewed source exception: this legacy CSV contains only ASCII plus byte AE
# (registered sign, 278 occurrences), identical in Windows-1252 and Latin-1.
# UTF-8 decoding fails. Do not guess an encoding for other resources.
ENCODINGS = {'bb185a88-c7c3-483f-b06e-784ce5322ff8': 'cp1252'}


def range_bytes(client, url, start, end, etag=None, total=None):
    headers = {'Range': f'bytes={start}-{end}'}
    if etag:
        headers['If-Range'] = etag
    with client.stream('GET', url, headers=headers) as response:
        response.raise_for_status()
        match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('content-range', ''))
        version = response.headers.get('etag')
        if response.status_code != 206 or not match or not version or version.startswith('W/'):
            raise ValueError('A stable range-download entity is required')
        first, last, size = map(int, match.groups())
        if (first, last) != (start, end) or size > 800_000_000 or total is not None and total != size or etag and version != etag:
            raise ValueError('Archive range, length or entity changed during download')
        data = bytearray()
        for block in response.iter_bytes(64 * 1024):
            data.extend(block)
            if len(data) > end - start + 1:
                raise ValueError('Range response exceeds requested length')
        if len(data) != end - start + 1:
            raise ValueError('Incomplete archive range')
        return data, size, version


def download_chunks(entry):
    """Validate HTTP ranges and entity versions; resume only the same server entity."""
    if not official_url(entry['url']):
        raise ValueError('Unreviewed download host')
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / (entry['id'] + '.csv')
    receipt_path = path.with_suffix('.receipt.json')
    revision = entry.get('last_modified') or entry.get('metadata_modified')
    if path.exists() and receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        if receipt.get('revision') == revision and receipt.get('bytes') == path.stat().st_size:
            with path.open('rb') as source:
                if hashlib.file_digest(source, 'sha256').hexdigest() == receipt['sha256']:
                    return path, receipt
    temporary = path.with_suffix('.history.part')
    progress = path.with_suffix('.history-progress.json')
    start = 0
    chunk = 8 * 1024 * 1024
    with httpx.Client(timeout=30, follow_redirects=False, headers={'Accept-Encoding': 'identity'}) as client:
        _, total, etag = range_bytes(client, entry['url'], 0, 0)
        if temporary.exists() and progress.exists():
            saved = json.loads(progress.read_text(encoding='utf-8'))
            if saved.get('etag') == etag and saved.get('total') == total and isinstance(saved.get('bytes'), int) and 0 <= saved['bytes'] <= total and temporary.stat().st_size >= saved['bytes']:
                start = saved['bytes']
                # A crash after writing a range but before its checkpoint may leave
                # an uncommitted tail. Retain only the validated checkpoint prefix.
                with temporary.open('r+b') as partial:
                    partial.truncate(start)
        with temporary.open('ab' if start else 'wb') as output:
            while start < total:
                end = min(start + chunk, total) - 1
                for attempt in range(3):
                    try:
                        content, _, _ = range_bytes(client, entry['url'], start, end, etag, total)
                        break
                    except httpx.HTTPError:
                        if attempt == 2:
                            raise
                        time.sleep(attempt + 1)
                output.write(content)
                output.flush()
                start = end + 1
                atomic(progress, {'etag': etag, 'total': total, 'bytes': start})
    if temporary.stat().st_size != total:
        raise ValueError('Incomplete archive')
    with temporary.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    temporary.replace(path)
    receipt = {'url': entry['url'], 'retrieved_at': stamp(), 'revision': revision,
               'bytes': total, 'sha256': digest, 'etag': etag, 'method': 'validated_http_ranges'}
    atomic(receipt_path, receipt)
    return path, receipt


def collect(entry):
    result = {'id': entry['id'], 'name': entry['name'], 'url': entry['url'], 'status': 'pending'}
    try:
        path, receipt = download_chunks(entry)
        result.update(status='downloaded', bytes=receipt['bytes'], sha256=receipt['sha256'])
        target = Path('data/raw/training') / (entry['id'] + '.csv')
        metadata = target.with_suffix('.metadata.json')
        if metadata.exists() and target.exists():
            saved = json.loads(metadata.read_text(encoding='utf-8'))
            if saved.get('sha256') == receipt['sha256'] and saved.get('before_year') == datetime.now().year:
                return saved
        target.parent.mkdir(parents=True, exist_ok=True)
        years = Counter()
        invalid = outside = rows = exported = 0
        earliest = latest = None
        temporary = target.with_suffix('.tmp')
        encoding = ENCODINGS.get(entry['id'], 'utf-8-sig')
        with path.open(encoding=encoding, newline='') as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames or []
            date_key = next((f for f in fields if 'acquisition time' in f.lower() or f.lower().strip() == 'date of monitoring'), None)
            state_key = next((f for f in fields if f.lower().strip() in ('state', 'state name')), None)
            if not date_key:
                return {**result, 'status': 'unsupported_date_columns', 'fields': fields}
            with temporary.open('w', encoding='utf-8', newline='') as output:
                writer = csv.DictWriter(output, fieldnames=fields)
                writer.writeheader()
                for row in reader:
                    rows += 1
                    if state_key and (row.get(state_key) or '').strip().lower() != 'maharashtra':
                        outside += 1
                        continue
                    # Cache dates rather than millions of repeated observation times.
                    observed = read_date((row.get(date_key) or '').strip()[:10])
                    if not observed or observed > datetime.now():
                        invalid += 1
                        continue
                    years[str(observed.year)] += 1
                    earliest = min(earliest, observed) if earliest else observed
                    latest = max(latest, observed) if latest else observed
                    if 2021 <= observed.year < datetime.now().year:
                        writer.writerow(row)
                        exported += 1
        temporary.replace(target)
        result.update(status='profiled', rows=rows, years=dict(sorted(years.items())), invalid_dates=invalid,
                      outside_state_rows=outside, earliest_date=earliest.date().isoformat() if earliest else None,
                      latest_date=latest.date().isoformat() if latest else None, exported_rows=exported,
                      before_year=datetime.now().year, minimum_year=2021, fields=fields,
                      export_path=str(target), source_encoding=encoding, export_encoding='utf-8',
                      units_policy='Original columns and units retained; no conversion/imputation',
                      quality_status='candidate_only', limitations=['Duplicates, physical ranges, gaps and source identity still require modelling validation.',
                      'Calendar dates profiled; intra-day timestamps and time zones not normalized in this export.',
                      'Resource geography identifies Maharashtra when no State column exists.'])
        atomic(metadata, result)
    except Exception as error:
        result.update(status='failed', error_class=type(error).__name__)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, choices=range(1, 7), default=6)
    parser.add_argument('--resource-id', action='append', help='Retry selected resource UUIDs, preserving the full collection report')
    args = parser.parse_args()
    catalogue = json.loads((OUT / 'catalogue.json').read_text(encoding='utf-8'))
    entries = [r for r in catalogue['resources'] if r['role'] == 'history']
    results = {}
    if args.resource_id:
        report_path = OUT / 'history-collection.json'
        if report_path.exists():
            results = {r['id']: r for r in json.loads(report_path.read_text(encoding='utf-8')).get('resources', [])}
        if not set(args.resource_id) <= {e['id'] for e in entries}:
            parser.error('Resource ID must be in the reviewed historical catalogue')
    selected = sorted([e for e in entries if not args.resource_id or e['id'] in args.resource_id], key=lambda e: e.get('size') or 0)
    def publish():
        values = list(results.values())
        atomic(OUT / 'history-collection.json', {'updated_at': stamp(), 'total': len(entries),
            'downloaded': sum(bool(r.get('sha256')) for r in values), 'profiled': sum(r['status'] == 'profiled' for r in values),
            'failed': sum(r['status'] == 'failed' for r in values), 'processed': len(values),
            'exported_rows': sum(r.get('exported_rows', 0) for r in values), 'minimum_year': 2021,
            'before_year': datetime.now().year, 'quality_approved': False, 'resources': values})
    publish()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(collect, entry) for entry in selected]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results[result['id']] = result
            publish()
            print(json.dumps({k: result[k] for k in ('id', 'status', 'rows', 'exported_rows', 'error_class') if k in result}), flush=True)
    print(json.dumps({'completed': len(results), 'report': str(OUT / 'history-collection.json')}), flush=True)
    from scripts.publish_historical_quality import main as publish_quality
    publish_quality()
    if (RAW / 'bb185a88-c7c3-483f-b06e-784ce5322ff8.csv').exists():
        from scripts.publish_historical_wells import main as publish_wells
        publish_wells()


if __name__ == '__main__':
    main()
