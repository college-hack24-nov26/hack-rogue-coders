"""Supply feature engineering with provenance and no manufactured target values.

Daily records represent a reviewed, named scope (household or whole_village).
Public river/canal readings are environmental context, never village deliveries.
"""
import math
from datetime import date, datetime, time, timedelta
from statistics import mean, pstdev
from zoneinfo import ZoneInfo

from services.api.calculations import budget

IST = ZoneInfo('Asia/Kolkata')
BASES = {'measured', 'operator_reported', 'derived', 'assumed', 'modelled'}
UNITS = {
    'population': 'people', 'households': 'households', 'household_size': 'people/household',
    'household_lpcd': 'litres/person/day', 'tank_capacity_m3': 'm3', 'tank_fill_fraction': 'fraction',
    'dead_storage_m3': 'm3', 'flow_lps': 'litres/second', 'runtime_hours': 'hours/day',
    'loss_fraction': 'fraction', 'area_ha': 'ha', 'et0_mm': 'mm/day', 'kc': 'coefficient',
    'effective_rain_mm': 'mm/day', 'soil_contribution_mm': 'mm/day', 'irrigation_efficiency': 'fraction',
    'rain_mm': 'mm/day', 'roof_area_m2': 'm2', 'runoff_coefficient': 'fraction',
    'capture_efficiency': 'fraction',
    **{k: 'litres' for k in ('storage_litres', 'gross_inflow_litres', 'net_inflow_litres',
       'household_demand_litres', 'agriculture_demand_litres', 'livestock_demand_litres',
       'other_demand_litres', 'demand_litres', 'delivered_litres', 'unmet_litres',
       'closing_storage_litres', 'physical_losses_litres', 'overflow_litres', 'rain_capture_litres')},
}
DAILY_TOTALS = {k for k in UNITS if k.endswith('_litres') and k != 'storage_litres'} | {
    'rain_mm', 'et0_mm', 'runtime_hours', 'effective_rain_mm', 'soil_contribution_mm'}


def instant(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Availability timestamps must include a timezone')
    return result


def validate_fields(fields):
    for key, item in fields.items():
        if key not in UNITS:
            raise ValueError('Unknown supply field: ' + key)
        value = item.get('value')
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError('Supply values must be finite and nonnegative: ' + key)
        if item.get('unit') != UNITS[key] or item.get('basis') not in BASES or not item.get('source'):
            raise ValueError('Unit, basis and source are required: ' + key)
        instant(item['available_at'])
        if item['basis'] == 'measured' and not item.get('method'):
            raise ValueError('Measured values need an instrument/measurement method: ' + key)
        if key in ('population', 'households', 'household_size'):
            observed = date.fromisoformat(item['observed_on'])
            if observed < date(2021, 1, 1):
                raise ValueError('Use a dated 2021+ population/household record, not a 2011 projection')
            if observed > instant(item['available_at']).astimezone(IST).date():
                raise ValueError('Observation cannot occur after its availability date')
        if key in ('tank_fill_fraction', 'loss_fraction', 'runoff_coefficient', 'capture_efficiency') and value > 1:
            raise ValueError('Fraction exceeds one: ' + key)
        if key == 'irrigation_efficiency' and not 0 < value <= 1:
            raise ValueError('Irrigation efficiency must be in (0, 1]')
        if key == 'runtime_hours' and value > 24:
            raise ValueError('Runtime exceeds a day')
    return fields


def derive_fields(fields):
    """Fill only derivable quantities; measured/reported input is never overwritten.

    Derived quantities are estimates even if their operands were measured. The
    full operand lineage and assumptions survive in the output.
    """
    out = {k: dict(v) for k, v in validate_fields(fields).items()}

    def derive(key, operands, formula, method, assumptions):
        if key in out or not all(k in out for k in operands):
            return
        value = formula(*(out[k]['value'] for k in operands))
        if not math.isfinite(value) or value < 0:
            raise ValueError('Inconsistent operands for ' + key)
        out[key] = {'value': value, 'unit': UNITS[key], 'basis': 'derived', 'method': method,
                    'available_at': max((instant(out[k]['available_at']) for k in operands)).isoformat(),
                    'source': 'calculated from supplied evidence', 'inputs': {k: out[k] for k in operands},
                    'assumptions': assumptions, 'eligible_as_measured_target': False}
        if key == 'population':
            out[key]['observed_on'] = min(out[k]['observed_on'] for k in operands)

    derive('population', ['households', 'household_size'], lambda h, s: h*s,
           'occupied_households * current_average_household_size',
           ['Household count and size refer to the same occupied service area and period; not a census population count.'])
    derive('household_demand_litres', ['population', 'household_lpcd'], lambda p, q: p*q,
           'population * selected_litres_per_person_per_day',
           ['Per-capita service norm estimates household demand; it is not measured consumption or total village demand.'])
    derive('storage_litres', ['tank_capacity_m3', 'tank_fill_fraction', 'dead_storage_m3'],
           lambda c, f, d: (c*f-d)*1000, '1000 * (capacity_m3 * volume_fill_fraction - unusable_m3)',
           ['Fill fraction is a calibrated VOLUME fraction, not height fraction in an arbitrary tank.',
            'Dead storage includes unavailable reserve; no default reserve or opening level is assumed.'])
    derive('gross_inflow_litres', ['flow_lps', 'runtime_hours'], lambda q, h: q*h*3600,
           'flow_litres_per_second * actual_runtime_hours * 3600',
           ['Flow is representative during actual runtime at the stated supply boundary; pump nameplate capacity alone is insufficient.',
            'This is one stream; do not add the same water again at its pump, tank and inlet.'])
    derive('net_inflow_litres', ['gross_inflow_litres', 'loss_fraction'], lambda q, l: q*(1-l),
           'gross_inflow_litres * (1 - explicit_loss_fraction)',
           ['Loss fraction covers this stream upstream of the village supply boundary; not inferred from pipe age or length.'])
    derive('agriculture_demand_litres', ['area_ha', 'et0_mm', 'kc', 'effective_rain_mm',
           'soil_contribution_mm', 'irrigation_efficiency'],
           lambda a, e, k, r, s, eff: a*10000*max(0, e*k-r-s)/eff,
           '10000 * area_ha * max(0, Kc*ET0 - effective_rain - soil_contribution) / efficiency',
           ['FAO crop-coefficient planning estimate; crop stage, irrigated area, effective rainfall and efficiency require evidence.',
            'Not a complete paddy, salinity/leaching or soil-moisture simulation; raw rainfall is not automatically effective rainfall.'])
    derive('rain_capture_litres', ['rain_mm', 'roof_area_m2', 'runoff_coefficient', 'capture_efficiency'],
           lambda r, a, c, e: r*a*c*e, 'rain_mm * connected_roof_m2 * runoff_coefficient * capture_efficiency',
           ['Only connected usable roof capture before storage constraints; not aquifer recharge or guaranteed potable supply.',
            'Not added to net inflow automatically: confirm connection, treatment and no double counting.'])
    derive('delivered_litres', ['storage_litres', 'net_inflow_litres', 'closing_storage_litres',
           'physical_losses_litres', 'overflow_litres'], lambda o, i, c, l, w: o+i-c-l-w,
           'opening_storage + net_inflow - closing_storage - downstream_losses - overflow',
           ['All readings cover the same daily boundary and tank system; downstream losses and overflow need explicit values.',
            'Balance-derived outlet volume is an estimate, not a metered delivery target or unconstrained demand.'])
    derive('demand_litres', ['household_demand_litres', 'agriculture_demand_litres',
           'livestock_demand_litres', 'other_demand_litres'], lambda *x: sum(x),
           'sum of four non-overlapping sector demands',
           ['All four sector demands cover the same village boundary/day; excluded sectors require an evidence-backed explicit zero.'])
    derive('unmet_litres', ['demand_litres', 'delivered_litres'], lambda d, q: max(0, d-q),
           'max(0, independently_recorded_demand - delivered_to_users)',
           ['Demand must be independent of supply restrictions; metered consumption alone underestimates demand during a shortage.',
            'Inlet flow is not consumer delivery. Norm/estimated demand creates a scenario deficit, not a measured shortage label.'])
    if out.get('unmet_litres', {}).get('method') == 'max(0, independently_recorded_demand - delivered_to_users)':
        out['unmet_litres']['candidate_observed_balance'] = all(out[k]['basis'] == 'measured' for k in ('demand_litres', 'delivered_litres'))
    return out


def sensitivity(demand_range, inflow_range, storage_range, capacity_litres, delivery_limit_litres):
    """Conditional bound tests, not probabilities or calibrated confidence bands."""
    for pair in (demand_range, inflow_range, storage_range):
        if len(pair) != 2 or any(isinstance(v, bool) or not math.isfinite(v) or v < 0 for v in pair) or pair[0] > pair[1]:
            raise ValueError('Use explicit ordered nonnegative [low, high] bounds')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0
           for v in (capacity_litres, delivery_limit_litres)):
        raise ValueError('Explicit capacity and delivery limits must be nonnegative finite numbers')
    if storage_range[1] > capacity_litres:
        raise ValueError('Storage bound exceeds capacity')
    results = []
    for horizon in (7, 15):
        optimistic = budget([demand_range[0]]*horizon, [inflow_range[1]]*horizon,
                            storage_range[1], capacity_litres, delivery_limit_litres)
        conservative = budget([demand_range[1]]*horizon, [inflow_range[0]]*horizon,
                              storage_range[0], capacity_litres, delivery_limit_litres)
        low, high = optimistic['unmet_litres'], conservative['unmet_litres']
        status = 'enough_in_tested_bounds' if high == 0 else 'short_in_tested_bounds' if low > 0 else 'sensitive_to_assumptions'
        results.append({'days': horizon, 'status': status, 'shortage_range_litres': [low, high]})
    return {'method': 'explicit_bounds_daily_water_balance', 'outlooks': results,
            'assumptions': ['Bounds are user-supplied scenarios, not confidence intervals or learned error distributions.',
                'Demand and net inflow stay constant within each tested scenario; quantities cover one disjoint usable supply pool.',
                'Daily totals cannot establish pressure, potable quality or hourly delivery reliability.']}


def validate_record(record):
    day = date.fromisoformat(record['date'])
    if day < date(2021, 1, 1):
        raise ValueError('Daily supply records must be from 2021 onward')
    if ':' not in record.get('village_id', '') or record.get('scope') not in ('household', 'whole_village'):
        raise ValueError('Use a namespaced village ID and explicit scope')
    validate_fields(record.get('fields', {}))
    # Complete daily totals cannot be available before that India-local day ends.
    end = datetime.combine(day+timedelta(days=1), time.min, IST)
    for key, item in record.get('fields', {}).items():
        if key in DAILY_TOTALS and item['basis'] in ('measured', 'operator_reported'):
            if instant(item['available_at']) >= end:
                continue
            raise ValueError('Daily totals must not be available before the reporting day ends')
    return record


def index_records(records):
    """Validate once and index by village/scope/day; duplicates require review."""
    groups = {}
    for raw in records:
        r = validate_record(raw)
        key = (r['village_id'], r['scope'])
        day = date.fromisoformat(r['date'])
        if day in groups.setdefault(key, {}):
            raise ValueError('Duplicate village/scope/day; reconcile versions before feature engineering')
        groups[key][day] = r
    return groups


def build_examples(records, issued_on, *, holdout_from=date(2026, 1, 1), as_of=None):
    """Build rows for one issue date; future measurements are labels only."""
    return examples_from_index(index_records(records), issued_on, holdout_from=holdout_from, as_of=as_of)


def examples_from_index(groups, issued_on, *, holdout_from=date(2026, 1, 1), as_of=None):
    """Reuse validated histories when building every date in an offline dataset.

    Targets require measured unmet litres, or a deficit calculated from measured
    independent demand and measured user delivery, plus complete scope coverage.
    Norm-based deficits and operator-reported/estimated shortages are not targets.
    """
    issue = datetime.combine(issued_on, time.min, IST)
    as_of = as_of or datetime.now(IST)
    if as_of.tzinfo is None or issue > as_of:
        raise ValueError('Issue date must not be after the timezone-aware audit time')
    result = []
    for (village, scope), days in sorted(groups.items()):
        features, provenance = {}, {}
        for name in ('net_inflow_litres', 'delivered_litres', 'demand_litres', 'unmet_litres'):
            for window in (7, 15):
                values, evidence = [], []
                for lag in range(1, window+1):
                    record = days.get(issued_on-timedelta(days=lag), {})
                    item = record.get('fields', {}).get(name)
                    if item and instant(item['available_at']) <= issue:
                        values.append(item['value']);evidence.append({'date':record['date'], **item})
                prefix = f'{name}_previous_{window}d'
                features[prefix+'_count'] = len(values)
                features[prefix+'_measured_count'] = sum(e['basis'] == 'measured' for e in evidence)
                features[prefix+'_estimated_count'] = sum(e['basis'] in ('derived', 'assumed', 'modelled') for e in evidence)
                # Partial-window means stay missing. Count describes the gap.
                features[prefix+'_mean'] = mean(values) if len(values) == window else None
                features[prefix+'_std'] = pstdev(values) if len(values) == window else None
                provenance[prefix] = evidence
            for lag in (1, 7, 15):
                item = days.get(issued_on-timedelta(days=lag), {}).get('fields', {}).get(name)
                features[f'{name}_lag_{lag}d'] = item['value'] if item and instant(item['available_at']) <= issue else None
        previous = days.get(issued_on-timedelta(days=1), {}).get('fields', {})
        storage = previous.get('closing_storage_litres')
        features['opening_storage_litres'] = storage['value'] if storage and instant(storage['available_at']) <= issue else None
        provenance['opening_storage_litres'] = storage if features['opening_storage_litres'] is not None else None
        demand = features['demand_litres_previous_7d_mean']
        incoming = features['net_inflow_litres_previous_7d_mean']
        opening = features['opening_storage_litres']
        features['storage_days_without_inflow'] = opening/demand if opening is not None and demand is not None and demand > 0 else None
        features['net_inflow_demand_ratio'] = incoming/demand if incoming is not None and demand is not None and demand > 0 else None
        delivery7 = features['delivered_litres_previous_7d_mean']
        delivery15 = features['delivered_litres_previous_15d_mean']
        features['delivery_7d_minus_15d_mean'] = delivery7-delivery15 if delivery7 is not None and delivery15 is not None else None
        features['weekday'] = issued_on.weekday()
        features['season_sin'] = math.sin(2*math.pi*(issued_on.timetuple().tm_yday-1)/365.2425)
        features['season_cos'] = math.cos(2*math.pi*(issued_on.timetuple().tm_yday-1)/365.2425)
        for horizon in (7, 15):
            future, label_evidence = [], []
            for offset in range(horizon):
                record = days.get(issued_on+timedelta(days=offset), {})
                item = record.get('fields', {}).get('unmet_litres')
                day_end = datetime.combine(issued_on+timedelta(days=offset+1), time.min, IST)
                observed_balance = (item and item['basis'] == 'derived'
                    and item.get('method') == 'max(0, independently_recorded_demand - delivered_to_users)'
                    and all(item.get('inputs', {}).get(k, {}).get('basis') == 'measured' for k in ('demand_litres', 'delivered_litres'))
                    and record.get('demand_independent_of_supply_verified') is True)
                if (record.get('complete_day') is True and record.get('coverage_verified') is True and item
                    and (item['basis'] == 'measured' or observed_balance)
                    and day_end <= as_of and instant(item['available_at']) <= as_of):
                    future.append(item['value']);label_evidence.append({'date':record['date'], **item})
            complete = len(future) == horizon
            end = issued_on+timedelta(days=horizon-1)
            split = 'train' if end < holdout_from else 'holdout' if issued_on >= holdout_from else 'purged_at_split'
            enough_history = features['delivered_litres_previous_7d_count'] == 7 and opening is not None
            result.append({'village_id':village, 'scope':scope, 'issued_on':issued_on.isoformat(), 'horizon_days':horizon,
                'features':features, 'feature_provenance':provenance, 'split':split,
                'label_enough': all(v == 0 for v in future) if complete else None,
                'label_shortage_litres':sum(future) if complete else None, 'label_days_available':len(future),
                'label_evidence':label_evidence, 'supervised_eligible':complete and enough_history and split != 'purged_at_split',
                'limitations':['Measured unmet demand must be independently recorded; never backfilled from the scenario or a groundwater forecast.',
                    'Feature availability is checked at 00:00 India time on issue date; no interpolation or future weather actuals.',
                    'Eligibility is a per-row data gate, not evidence of adequate training size, source validity or model accuracy.']})
    return result
