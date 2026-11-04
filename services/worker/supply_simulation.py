"""Explicit hypothetical water balances. Never measured village operations."""
import hashlib
import math
import random
from statistics import mean, pstdev

VERSION = 'supply-simulation-v1'
POLICY = {
    'version': 'simulated-supply-urgency-v1',
    'name': 'Simulated water-supply urgency',
    'basis': 'simulated_outcome',
    'levels': [
        {'level': 0, 'name': 'Normal', 'meaning': 'No simulated deficit; reserves stay at least half a reference demand day.'},
        {'level': 1, 'name': 'Watch', 'meaning': 'No simulated deficit; reserves fall below half a reference demand day.'},
        {'level': 2, 'name': 'Moderate', 'meaning': 'Worst daily simulated deficit is positive and below 10% of total demand.'},
        {'level': 3, 'name': 'High', 'meaning': 'Worst daily simulated deficit is at least 10% and below 25%.'},
        {'level': 4, 'name': 'Severe', 'meaning': 'Worst daily deficit is at least 25%, without first-week essential household failure.'},
        {'level': 5, 'name': 'Critical', 'meaning': 'Simulated household delivery falls below 60% of household demand in days 1–7; tanker is assumed the only emergency fallback.'},
    ],
    'limitations': ['Experimental thresholds, not official drought or emergency standards.',
                   'No actual tanker need, actual village outcome or measured supply is asserted.',
                   'Both horizons share the same first-week level-5 trigger.'],
}
ASSUMPTIONS = {
    'history_days': 30, 'future_days': 15,
    'household_size_people_uniform': [3, 6],
    'household_lpcd_benchmark': 55,
    'benchmark_source': 'https://www.pib.gov.in/PressReleasePage.aspx?PRID=2226993&lang=1&reg=1',
    'zero_household_template_replacement_uniform_integer': [50, 1500],
    'livestock_heads_per_simulated_person_uniform': [.05, .7],
    'mixed_livestock_litres_per_head_uniform': [20, 60],
    'other_demand_as_household_fraction_uniform': [.02, .2],
    'agriculture_reference_as_household_fraction_uniform': [0, 1.5],
    'irrigation_et0_mm_uniform': [3, 7], 'crop_coefficient_uniform': [.5, 1.2],
    'irrigation_efficiency_uniform': [.45, .85], 'effective_rain_fraction': .6,
    'soil_contribution_mm_uniform': [0, .5],
    'loss_fraction_uniform': [.05, .35], 'planned_pumping_hours_uniform': [6, 20],
    'daily_source_capacity_drift_uniform': [-.004, .004],
    'daily_pump_noise_fraction_uniform': [-.04, .04],
    'daily_outage_start_probability_uniform': [0, .025],
    'outage_recovery_probability': .6, 'outage_pumped_flow_fraction': .1,
    'ordinary_day_demand_noise_uniform': [.97, 1.03],
    'initial_usable_storage_fraction_uniform': [.2, .95],
    'critical_household_delivery_fraction': .6, 'watch_reserve_reference_days': .5,
    'moderate_deficit_fraction_upper': .1, 'high_deficit_fraction_upper': .25,
    'source_channels': ['pipeline', 'groundwater', 'allocated_surface', 'routine_tanker'],
    'source_mix': 'Random positive shares over 1–4 channels, not surveyed connections.',
    'allocation_order': ['household', 'livestock', 'other', 'agriculture'],
    'water_pool': 'One hypothetical disjoint usable pool shared across sectors; not a factual village allocation.',
    'potability': 'All simulated usable inflows assumed usable; no water-quality or pressure model.',
    'weather': 'Published district weather provides a repeating 14-day example waveform, not a dated forecast or historical village weather reconstruction.',
    'rainfall_to_supply': 'No automatic rainfall-to-recharge or river-flow-to-delivery conversion.',
    'emergency_response': 'Counterfactual without extra emergency tankers. Routine tankers are a separate simulated inflow channel.',
    'sampling': 'Six equally sampled parameter regimes cover stress conditions; their frequencies are not Maharashtra prevalence.',
}
# Net capacity / reference daily demand, usable tank days, delivery-limit ratio.
REGIMES = [((1.4, 2), (1, 4), (1.1, 1.4)),
           ((1.03, 1.15), (.05, .35), (1.05, 1.3)),
           ((.93, .99), (.05, .3), (.97, 1.1)),
           ((.78, .89), (.1, .6), (.85, 1.05)),
           ((.45, .7), (.1, 1), (.65, 1)),
           ((.01, .3), (.05, .8), (.2, .8))]
ASSUMPTIONS['parameter_regimes'] = [
    {'net_capacity_to_reference_demand': list(ratio), 'usable_tank_reference_days': list(tank),
     'delivery_limit_to_reference_demand': list(limit)} for ratio, tank, limit in REGIMES]


def rng_for(identity, seed):
    return random.Random(int.from_bytes(hashlib.sha256(f'{seed}:{identity}'.encode()).digest()[:8], 'big'))


def partition(identity, seed):
    return 'validation' if int(hashlib.sha256(f'split:{seed}:{identity}'.encode()).hexdigest()[:8], 16) % 5 == 0 else 'train'


def water_day(opening, incoming, demands, capacity, delivery_limit):
    values = [opening, incoming, capacity, delivery_limit, *demands.values()]
    if any(isinstance(v, bool) or not math.isfinite(v) or v < 0 for v in values) or opening > capacity:
        raise ValueError('Invalid simulated water balance')
    total = sum(demands.values())
    delivered = min(opening+incoming, total, delivery_limit)
    remaining = opening+incoming-delivered
    closing = min(capacity, remaining)
    overflow = max(0, remaining-capacity)
    left = delivered; allocation = {}
    for sector in ASSUMPTIONS['allocation_order']:
        allocation[sector] = min(left, demands[sector]); left -= allocation[sector]
    return {'opening_storage_litres': opening, 'net_inflow_litres': incoming,
            'demand_litres': total, 'delivered_litres': delivered, 'unmet_litres': total-delivered,
            'closing_storage_litres': closing, 'overflow_litres': overflow,
            'sector_demand_litres': demands, 'sector_delivered_litres': allocation}


def outcome(future, horizon, reference_demand):
    if horizon not in (7, 15) or len(future) < 15 or reference_demand <= 0:
        raise ValueError('Require a complete 15-day scenario and positive demand')
    critical_day = next((i for i, day in enumerate(future[:7])
        if day['sector_delivered_litres']['household'] <
        ASSUMPTIONS['critical_household_delivery_fraction'] * day['sector_demand_litres']['household']-1e-6), None)
    days = future[:horizon]
    fractions = [day['unmet_litres']/day['demand_litres'] for day in days]
    worst = max(fractions)
    if critical_day is not None:
        level = 5
    elif worst >= .25:
        level = 4
    elif worst >= .1:
        level = 3
    elif worst > 1e-9:
        level = 2
    elif min(day['closing_storage_litres'] for day in days) < .5*reference_demand:
        level = 1
    else:
        level = 0
    return {'label_urgency_level': level, 'label_enough': worst <= 1e-9,
            'label_shortage_litres': sum(day['unmet_litres'] for day in days),
            'simulated_tanker_required_relative_day': critical_day,
            'label_basis': 'simulated_outcome', 'policy_version': POLICY['version']}


def history_features(history, static):
    if len(history) != 30:
        raise ValueError('Simulation requires 30 preceding days')
    names = ('net_inflow_litres', 'delivered_litres', 'demand_litres', 'unmet_litres',
             'runtime_hours', 'rain_mm', 'temperature_c', 'pipeline_inflow_litres',
             'groundwater_inflow_litres', 'surface_inflow_litres', 'routine_tanker_litres')
    features = dict(static)
    for name in names:
        for lag in (1, 7, 15):
            features[name+f'_lag_{lag}d'] = history[-lag][name]
        for length in (7, 15):
            values = [day[name] for day in history[-length:]]
            features[name+f'_previous_{length}d_mean'] = mean(values)
            features[name+f'_previous_{length}d_std'] = pstdev(values)
    demand = features['demand_litres_previous_7d_mean']
    opening = history[-1]['closing_storage_litres']
    features.update(opening_storage_litres=opening, storage_days_without_inflow=opening/demand,
        net_inflow_demand_ratio=features['net_inflow_litres_previous_7d_mean']/demand,
        delivery_7d_minus_15d_mean=features['delivered_litres_previous_7d_mean']-features['delivered_litres_previous_15d_mean'])
    return features


def simulate(profile, weather, seed=1729, *, rotate_weather=True, regime_index=None):
    if (isinstance(profile['reported_households'], bool) or
        not math.isfinite(profile['reported_households']) or profile['reported_households'] < 0):
        raise ValueError('Invalid household size template')
    if not weather or any(not math.isfinite(row[key]) or (key == 'rain' and row[key] < 0)
                          for row in weather for key in ('rain', 'temp_avg')):
        raise ValueError('Invalid weather template')
    template = 'jjm:'+profile['jjm_village_id']
    rng = rng_for(template, seed)
    uniform = rng.uniform
    replacement = profile['reported_households'] <= 0
    households = rng.randint(50, 1500) if replacement else profile['reported_households']
    population = households*uniform(3, 6)
    domestic = population*55
    livestock_heads = round(population*uniform(.05, .7))
    livestock_lpd = uniform(20, 60)
    other = domestic*uniform(.02, .2)
    et0, kc, efficiency, soil = uniform(3, 7), uniform(.5, 1.2), uniform(.45, .85), uniform(0, .5)
    area = domestic*uniform(0, 1.5)*efficiency/(10000*max(.1, et0*kc-soil))
    reference = domestic+livestock_heads*livestock_lpd+other+area*10000*max(0, et0*kc-soil)/efficiency
    sampled_regime = rng.randrange(len(REGIMES))
    regime = REGIMES[sampled_regime if regime_index is None else regime_index]
    ratio, tank_days, limit_ratio = (uniform(*bounds) for bounds in regime)
    capacity, limit = reference*tank_days, reference*limit_ratio
    loss, planned_hours = uniform(.05, .35), uniform(6, 20)
    gross_reference = reference*ratio/(1-loss)
    active = rng.sample(range(4), rng.randint(1, 4))
    weights = [0.0]*4
    for i in active:
        weights[i] = uniform(.1, 1)
    total = sum(weights); weights = [v/total for v in weights]
    drift, outage_p = uniform(-.004, .004), uniform(0, .025)
    stored, outage = capacity*uniform(.2, .95), False
    offset = rng.randrange(len(weather)) if rotate_weather else 0
    days = []
    for index in range(45):
        driver = weather[(offset+index) % len(weather)]
        rain, temperature = driver['rain'], driver['temp_avg']
        if outage:
            outage = rng.random() >= .6
        else:
            outage = rng.random() < outage_p
        runtime = min(24, max(0, planned_hours*(.1 if outage else 1)*uniform(.96, 1.04)))
        gross = gross_reference*max(.1, 1+drift*index)
        volumes = [gross*weight*(1-loss)*(1 if i == 3 else runtime/planned_hours)
                   for i, weight in enumerate(weights)]
        household = domestic*uniform(.97, 1.03)*(1+max(0, temperature-30)*.005)
        demands = {'household': household, 'livestock': livestock_heads*livestock_lpd,
                   'other': other, 'agriculture': area*10000*max(0, et0*kc-.6*rain-soil)/efficiency}
        day = water_day(stored, sum(volumes), demands, capacity, limit)
        day.update(relative_day=index-30, runtime_hours=runtime, pump_outage=outage,
            rain_mm=rain, temperature_c=temperature, pipeline_inflow_litres=volumes[0],
            groundwater_inflow_litres=volumes[1], surface_inflow_litres=volumes[2],
            routine_tanker_litres=volumes[3], upstream_loss_litres=sum(volumes)*loss/(1-loss))
        days.append(day); stored = day['closing_storage_litres']
    static = {'population_scenario': population, 'households_size_template': households,
        'household_size_scenario': population/households, 'household_lpcd_scenario': 55,
        'livestock_heads_scenario': livestock_heads, 'livestock_lpd_scenario': livestock_lpd,
        'irrigated_area_ha_scenario': area, 'et0_mm_scenario': et0, 'kc_scenario': kc,
        'irrigation_efficiency_scenario': efficiency, 'loss_fraction_scenario': loss,
        'usable_tank_capacity_litres_scenario': capacity, 'delivery_limit_litres_per_day_scenario': limit,
        'planned_runtime_hours_scenario': planned_hours,
        'nominal_equivalent_flow_lps_scenario': gross_reference/(planned_hours*3600)}
    # Future days, random event parameters and the sampling regime never enter features.
    features = history_features(days[:30], static)
    case = 'sim:'+hashlib.sha256(f'{VERSION}:{seed}:{template}'.encode()).hexdigest()[:24]
    episode = {'case_id': case, 'basis': 'simulated', 'template_id': template,
        'template_household_observation_date': profile['observed_on'],
        'template_households_replaced_with_synthetic_size': replacement,
        'partition': partition(template, seed), 'reference_demand_litres': reference,
        'static': static, 'days': days,
        'weather_template_dates': [row['for_date'] for row in weather],
        'profile_district_code_as_reported': profile['jjm_district_code'],
        'weather_district_code_as_reported': str(weather[0]['district_code_as_reported']),
        'weather_template_match': 'reported_code' if str(weather[0]['district_code_as_reported']) == str(profile['jjm_district_code']) else 'unique_exact_district_name_for_scenario_only'}
    examples = [{'case_id': case, 'template_id': template, 'basis': 'simulated',
        'partition': episode['partition'], 'scope': 'whole_village', 'horizon_days': horizon,
        'features': features, **outcome(days[30:], horizon, reference)} for horizon in (7, 15)]
    return episode, examples
