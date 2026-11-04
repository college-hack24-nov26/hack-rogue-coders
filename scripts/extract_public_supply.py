"""Read official cached tanker files without exporting recipient/contact details.

Run with Python providing openpyxl and pypdf. No network, database or trainer
inputs are touched. Trip columns describe scheduled/required trips, not verified
delivery. A source date is accepted only from a dated worksheet heading.
"""
import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path('data/raw/supply/public-completion')
REPORT = Path('data/water/public-supply-file-audit.json')
DATE = re.compile(r'(?<!\d)(\d{1,2})\s*[-./]\s*(\d{1,2})\s*[-./]\s*(\d{4})(?!\d)')
DIGITS = str.maketrans('०१२३४५६७८९', '0123456789')


def dates_in(value, today=None):
    """Do not guess two-digit years, swap month/day, or accept future dates."""
    today = today or date.today()
    result = set()
    for day, month, year in DATE.findall(str(value).translate(DIGITS)):
        try:
            d = date(int(year), int(month), int(day))
            if date(2021, 1, 1) <= d <= today:
                result.add(d.isoformat())
        except ValueError:
            pass
    return result


def count_value(value):
    if value is None or str(value).strip() == '':
        return None
    if isinstance(value, bool):
        raise ValueError('Boolean trip count')
    text = str(value).strip().translate(DIGITS)
    if not re.fullmatch(r'\d+(?:\.0+)?', text):
        raise ValueError('Non-integer/negative/unavailable trip count')
    return int(text.split('.')[0])


def columns(row):
    result = {}
    for i, value in enumerate(row):
        text = re.sub(r'\s+', '', str(value or ''))
        if 'खेपा' in text and text.startswith('शेड्य'):
            result['scheduled'] = i
        elif 'खेपा' in text and ('आवश्यकते' in text or 'अवश्कते' in text):
            result['required'] = i
        elif text in ('अ.क्र.', 'अ.क्र'):
            result['serial'] = i
    return result if set(result) == {'scheduled', 'required', 'serial'} else None


def summarize_sheet(rows, title='', today=None):
    """Rows may contain PII in other columns; return only aggregate diagnostics."""
    iterator = iter(rows)
    top = []
    mapping = None
    header_row = None
    for number in range(1, 13):
        row = next(iterator, None)
        if row is None:
            break
        mapping = columns(row)
        if mapping:
            header_row = number
            break
        top.append(row)
    if mapping is None:
        return {'status': 'no_supported_table'}
    heading_dates = set()
    for row in top:
        for value in row:
            text = str(value or '')
            if 'दिनांक' in text or re.search(r'\bdate\s*:', text, re.I):
                heading_dates |= dates_in(text, today)
    title_dates = dates_in(title, today)
    observed = next(iter(heading_dates)) if len(heading_dates) == 1 else None
    conflict = bool(observed and title_dates and title_dates != {observed})
    totals = {'scheduled': 0, 'required': 0}
    present = Counter()
    serials = set()
    duplicates = invalid = row_count = 0
    for row in iterator:
        if len(row) <= max(mapping.values()):
            continue
        try:
            serial = count_value(row[mapping['serial']])
        except ValueError:
            continue  # Headers, subtotals and notes are not recipient rows.
        if serial is None:
            continue
        row_count += 1
        duplicates += serial in serials
        serials.add(serial)
        for key in totals:
            try:
                value = count_value(row[mapping[key]])
            except ValueError:
                invalid += 1
                continue
            if value is not None:
                totals[key] += value
                present[key] += 1
    return {
        'status': 'profiled', 'header_row': header_row,
        'heading_date_candidates': sorted(heading_dates),
        'title_date_candidates': sorted(title_dates),
        'date_conflict': conflict, 'content_date': observed,
        'date_usable': observed is not None and not conflict,
        'recipient_rows': row_count, 'duplicate_serial_rows': duplicates,
        'invalid_trip_cells': invalid,
        'reported_scheduled_trips_sum': totals['scheduled'] if present['scheduled'] else None,
        'reported_required_trips_sum': totals['required'] if present['required'] else None,
        'scheduled_cells_present': present['scheduled'], 'required_cells_present': present['required'],
        'completed_dispatches_verified': False, 'delivered_litres': None,
        'village_id': None, 'urgency_label': None, 'prediction_use': False,
    }


class ListingRows(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows = []; self.active = False; self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.active = True; self.values = []; self.links = []
        if self.active and tag in ('td', 'th'):
            self.cell = ''
        if self.active and tag == 'a':
            href = dict(attrs).get('href', '')
            if '.pdf' in href:
                self.links.append(href)

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.values.append(self.cell.strip()); self.cell = None
        if tag == 'tr' and self.active:
            self.rows.append({'values': self.values, 'links': self.links}); self.active = False


def verify_file(entry):
    path = Path(entry['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry['receipt']['sha256']:
        raise ValueError('Cached source hash mismatch')
    return path


def main():
    import openpyxl
    from pypdf import PdfReader

    pmc = json.loads((ROOT/'pmc/downloads.json').read_text(encoding='utf-8'))
    sheets = []; unique = set(); duplicate_files = errors = 0
    for entry in pmc:
        if entry['status'] != 'downloaded':
            continue
        try:
            path = verify_file(entry)
            digest = entry['receipt']['sha256']
            if digest in unique:
                duplicate_files += 1; continue
            unique.add(digest)
            workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
            try:
                for number, sheet in enumerate(workbook, 1):
                    result = summarize_sheet(sheet.iter_rows(values_only=True), entry.get('title', ''))
                    if result['status'] != 'profiled':
                        continue
                    sheets.append({**result, 'file_id': entry['file_id'], 'sheet_number': number,
                        'source_url': entry['file_url'], 'source_sha256': digest,
                        'retrieved_at': entry['receipt']['retrieved_at'],
                        'upload_date_as_reported': entry.get('upload_date')})
            finally:
                workbook.close()
        except (ValueError, KeyError, OSError) as e:
            errors += 1
            sheets.append({'file_id': entry['file_id'], 'status': 'failed', 'error': type(e).__name__})
    out = ROOT/'pmc/register-sheet-audit.jsonl'
    out.write_text(''.join(json.dumps(r, ensure_ascii=True)+'\n' for r in sheets), encoding='utf-8')

    listings = {}
    for path in sorted((ROOT/'wssd').glob('listing-*.html')):
        parser = ListingRows(); parser.feed(path.read_text(encoding='utf-8'))
        for row in parser.rows:
            for url in row['links']:
                listings[url] = row['values'][:2]
    pdfs = []
    for entry in json.loads((ROOT/'wssd/downloads.json').read_text(encoding='utf-8')):
        if entry['status'] != 'downloaded':
            continue
        try:
            path = verify_file(entry); reader = PdfReader(path)
            text = '\n'.join(p.extract_text() or '' for p in reader.pages)
            labels = listings.get(entry['url'], [])
            listing_dates = set().union(*(dates_in(x) for x in labels))
            pdfs.append({'source_url': entry['url'], 'path': str(path), 'listing_labels': labels,
                'listing_report_date': next(iter(listing_dates)) if len(listing_dates) == 1 else None,
                'source_sha256': entry['receipt']['sha256'], 'pages': len(reader.pages),
                'extracted_characters': len(text), 'content_date_candidates': sorted(dates_in(text)),
                'table_values_verified': False, 'village_delivery_verified': False})
        except (ValueError, OSError) as e:
            pdfs.append({'source_url': entry['url'], 'status': 'failed', 'error': type(e).__name__})
    (ROOT/'wssd/report-file-audit.json').write_text(json.dumps(pdfs, indent=2), encoding='utf-8')
    profiled = [r for r in sheets if r['status'] == 'profiled']
    usable = [r['content_date'] for r in profiled if r['date_usable']]
    pdf_dates = [r['listing_report_date'] for r in pdfs if r.get('listing_report_date')]
    report = {'checked_at': datetime.now(timezone.utc).isoformat(),
        'pmc': {'downloaded_files': len(pmc), 'unique_content_files': len(unique),
            'duplicate_content_files_skipped': duplicate_files, 'profiled_sheets': len(profiled),
            'errors': errors, 'sheets_with_usable_heading_date': len(usable),
            'sheets_with_conflicting_title_date': sum(r['date_conflict'] for r in profiled),
            'sheets_with_duplicate_serials': sum(r['duplicate_serial_rows'] > 0 for r in profiled),
            'heading_date_range': [min(usable, default=None), max(usable, default=None)],
            'output': str(out),
            'meaning': 'Reported scheduled/required trips. Completion, litres, village links and reasons unverified; no recipient/contact fields exported.'},
        'wssd': {'profiled_pdfs': len(pdfs), 'text_extractable_pdfs': sum(r.get('extracted_characters', 0) > 100 for r in pdfs),
            'listing_report_date_range': [min(pdf_dates, default=None), max(pdf_dates, default=None)],
            'output': str(ROOT/'wssd/report-file-audit.json'),
            'meaning': 'Statewide district summaries; listing report dates retained separately from content dates. Tables need visual verification; no village volumes inferred.'},
        'eligible_daily_village_supply_records_added': 0, 'reviewed_urgency_labels_added': 0}
    REPORT.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True))


if __name__ == '__main__':
    main()
