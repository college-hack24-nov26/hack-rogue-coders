"""Shared contract for the local village scenario snapshot."""
from .supply_simulation import ASSUMPTIONS, POLICY

SCENARIOS = {'tight_supply': ('Tight supply', 2), 'lower_supply': ('Lower supply', 4)}
LEVELS = {item['level']: item['name'] for item in POLICY['levels']}
SNAPSHOT = 'village-supply-predictions.json'
SCENARIO_METADATA = {
    key: {'label': label, **ASSUMPTIONS['parameter_regimes'][index]}
    for key, (label, index) in SCENARIOS.items()
}
