"""Extract reviewed district survey tables using pypdf (optional PDF tool).

Run with the bundled PDF Python runtime; it is not an application dependency.
"""
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader

SOURCE = Path('data/raw/supply/maharashtra-functionality-2024.pdf')
OUTPUT = Path('data/water/supply-survey-2024.json')
REVIEWED_SHA256 = 'a9bde2ade9bccaa1714684ee652d834d5c2b21bd83259ca07ae321cb7638e66a'


def extract(reader):
    # Reviewed PDF pages 26-27; later page contains a different quality table.
    text = '\n'.join(reader.pages[i].extract_text() for i in (25,26))
    rows = []
    for district, adequate, partial, inadequate in re.findall(
            r'^([A-Za-z][A-Za-z ]+?)\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s*$', text, re.M):
        values = [float(v) for v in (adequate, partial, inadequate)]
        if any(not 0 <= v <= 100 for v in values) or abs(sum(values)-100) > .21:
            raise ValueError('Survey category percentages require manual review: '+district)
        rows.append({'district_as_published':district.strip(), 'adequate_quantity_percent':values[0],
                     'partially_adequate_quantity_percent':values[1], 'inadequate_quantity_percent':values[2]})
    if len(rows) != 34 or len({r['district_as_published'] for r in rows}) != 34:
        raise ValueError('Expected exactly 34 distinct survey districts')
    return rows


def main():
    receipt = json.loads(SOURCE.with_suffix('.receipt.json').read_text(encoding='utf-8'))
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if digest != receipt['sha256'] or digest != REVIEWED_SHA256:raise ValueError('Report hash changed; review it again')
    reader = PdfReader(SOURCE)
    result = {'title':'Maharashtra Functionality Assessment of Household Tap Connections 2024',
        'source_url':receipt['url'], 'source_sha256':digest, 'retrieved_at':receipt['retrieved_at'],
        'survey_period_start':'2024-07', 'survey_period_end':'2024-10', 'publication_available_at':None,
        'pdf_pages':[26,27], 'basis':'weighted_sample_survey', 'district_count':34,
        'villages_sampled':1023, 'households_sampled':12276, 'rows':extract(reader),
        'use':'historical district context only', 'eligible_as_daily_village_target':False,
        'limitations':['District percentages are weighted survey estimates, not village shortage probabilities or daily service rates.',
            'Sample covered 1,023 villages and 12,276 households in 34 districts; not every Maharashtra village.',
            'Supply quantity was estimated from bucket flow measurements and supply duration; intermittent supply used weekly estimates.',
            'Report labels around exactly 40/55 LPCD are inconsistent between prose and table; preserve published categories without reclassifying individual records.',
            'No individual daily measurements or verified current village population are supplied by these tables.',
            'District names are retained as published. No automatic merge with current LGD districts.',
            'Historical publication availability is unknown; excluded from automatic issue-time feature joins.']}
    OUTPUT.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'output':str(OUTPUT), 'districts':len(result['rows']), 'sample_villages':1023, 'sample_households':12276}))


if __name__ == '__main__':main()
