"""Project-defined 0-5 water-supply urgency, distinct from climate drought."""
import csv
import hashlib
import io
import json
from datetime import date, datetime, time, timedelta

from services.worker.supply_features import IST, instant

POLICY = {
    'version':'supply-urgency-v1', 'name':'Water-supply urgency', 'levels':[
        {'level':0, 'name':'Normal', 'meaning':'Supply meets the reviewed service scope through the assessment period.'},
        {'level':1, 'name':'Watch', 'meaning':'Early supply stress or declining reserves; routine service is maintained.'},
        {'level':2, 'name':'Moderate', 'meaning':'Manageable intermittent supply deficits; routine adjustments are needed.'},
        {'level':3, 'name':'High', 'meaning':'Significant recurring deficits; planned mitigation is required.'},
        {'level':4, 'name':'Severe', 'meaning':'Severe sustained supply deficits; urgent contingency planning is required, without a verified tanker requirement in the first seven days.'},
        {'level':5, 'name':'Critical', 'meaning':'Reviewed outcome confirms tanker water is required within the first seven days, including day one.'}],
    'level_5_window_days':7,
    'limitations':[
        'Project operational rubric, not an official meteorological drought classification.',
        'Levels 1-4 are descriptive reviewer labels; quantitative local thresholds are not established or auto-invented.',
        'Tanker need is assessed need, not merely a dispatch, receipt, low reservoir or predicted shortage probability.',
        'Unknown/unreviewed outcomes are missing labels, never level zero.',
        'The score is ordinal; level five is not five times level one and is not a probability.']}


def truth(value):
    if value is True or value == 'true':return True
    if value is False or value in ('false', '', None):return False
    raise ValueError('Review flags must be true or false')


def validate_label(row, now):
    """Accept complete reviewed outcomes; never infer urgency from assumptions."""
    if ':' not in row.get('village_id','') or row.get('scope') not in ('whole_village','household'):
        raise ValueError('Urgency label requires namespaced village ID and scope')
    issued = date.fromisoformat(row['issued_on'])
    if issued < date(2021,1,1):raise ValueError('Urgency labels must be from 2021 onward')
    h, level = row.get('horizon_days'), row.get('level')
    if isinstance(h,str) and h in ('7','15'):h = int(h)
    if isinstance(level,str) and level in tuple(str(n) for n in range(6)):level = int(level)
    if type(h) is not int or h not in (7,15) or type(level) is not int or not 0 <= level <= 5:
        raise ValueError('Use horizon 7/15 and integer urgency level 0-5')
    if row.get('policy_version') != POLICY['version'] or row.get('basis') != 'observed_outcome':
        raise ValueError('Urgency targets require observed outcomes under supply-urgency-v1; scenarios cannot be labels')
    if not all(truth(row.get(k)) for k in ('reviewed','followup_complete','tanker_need_assessed')):
        raise ValueError('Urgency labels require review, complete follow-up and an explicit tanker-need assessment')
    if not str(row.get('source','')).strip() or not str(row.get('reviewer','')).strip() or not str(row.get('rationale','')).strip():
        raise ValueError('Urgency labels require source, reviewer and rationale')
    available = instant(row['available_at'])
    end = datetime.combine(issued+timedelta(days=h), time.min, IST)
    if available < end or available > now:
        raise ValueError('Urgency outcome must be available after complete follow-up and no later than the audit time')
    required = date.fromisoformat(row['tanker_required_on']) if row.get('tanker_required_on') else None
    if required and required < issued:raise ValueError('Record ongoing need on the issue date after review; do not use an earlier event date')
    if required and required > available.astimezone(IST).date():raise ValueError('Observed tanker requirement cannot occur after outcome availability')
    within_seven = required is not None and issued <= required < issued+timedelta(days=7)
    if level == 5 and not within_seven:
        raise ValueError('Level 5 requires a reviewed tanker-required date in days 1-7')
    if level < 5 and within_seven:
        raise ValueError('Confirmed tanker need in days 1-7 must be labelled level 5')
    return {**row, 'horizon_days':h, 'level':level, 'available_at':available.isoformat(),
            'tanker_required_on':required.isoformat() if required else None}


def read_labels(paths, now):
    labels, receipts = {}, []
    for path in sorted(set(p.resolve() for p in paths)):
        if not path.exists():raise ValueError('Urgency labels file does not exist: '+str(path))
        content = path.read_bytes()
        text = content.decode('utf-8-sig')
        if path.suffix.lower() == '.csv':
            reader = csv.DictReader(io.StringIO(text))
            if not {'village_id','scope','issued_on','horizon_days','level'}.issubset(reader.fieldnames or []):
                raise ValueError('Use templates/supply_urgency_labels.csv for outcome annotations')
            rows = [r for r in reader if any(r.values())]
        elif path.suffix.lower() == '.jsonl':rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:raise ValueError('Urgency labels must be CSV or JSONL')
        for number, row in enumerate(rows,1):
            try:r = validate_label(row, now)
            except (KeyError,ValueError,TypeError) as error:raise ValueError(f'{path}: invalid urgency label {number}: {error}') from error
            key = (r['village_id'],r['scope'],r['issued_on'],r['horizon_days'])
            if key in labels:raise ValueError('Duplicate village/scope/issue/horizon urgency labels require reconciliation')
            labels[key] = r
        receipts.append({'path':str(path),'sha256':hashlib.sha256(content).hexdigest(),'labels':len(rows)})
    # One confirmed first-week tanker need has the same meaning in both views.
    for (v,scope,issued,h), label in labels.items():
        other = labels.get((v,scope,issued,15 if h==7 else 7))
        if other and ((label['level']==5)!=(other['level']==5)):
            raise ValueError('Seven- and fifteen-day annotations disagree about tanker need in the first seven days')
        if h==7 and other and other['level'] < label['level']:
            raise ValueError('Maximum urgency over fifteen days cannot be lower than over its first seven days')
    return labels, receipts
