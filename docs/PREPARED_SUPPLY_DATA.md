# Prepared offline supply inputs

Prepared 4 November 2026. Latest bundle pointer: `artifacts/supply-data/latest.json`.

The preparation ran successfully on all three collected input tables:

| Table | Prepared rows | Identity/scope |
|---|---:|---|
| Village household/tap profiles | 40,297 | JJM village; administrative snapshot with unknown observation vintage |
| Weather | 504 | PoCRA district/day |
| River/canal flow | 147,069 | Resource + station series + day |
| Total | 187,870 | Different scopes; not 187,870 village training examples |

Each versioned bundle contains `village_profiles.jsonl`, `district_weather.jsonl`, `station_flow.jsonl` and `dataset-manifest.json`. Inputs and outputs have SHA-256 receipts in the manifest. Preparation makes no network or application-database calls.

Weather and flow have exact preceding 1/7/15-day lags and preceding 7/15-day counts, means and standard deviations. Means and standard deviations require a complete calendar window. Missing observations remain null; the issue day's observation is excluded from its lag features. Unknown historical publication times remain unknown, so these are candidate environmental features pending availability review, not a certified historical backtest.

Village profiles preserve household/tap counts and a derived connection-coverage fraction. Zero households produces a missing coverage fraction, not a divide-by-zero result. No population, water volume, tank level, demand or urgency outcome is generated from these counts. JJM, Census and LGD identifiers are not silently equated.

Weather keeps published rainfall, mean temperature and humidity; wind is excluded because units remain unverified. Flow units must be `m3/sec`; source/resources are not summed or integrated into assumed village litres. Duplicate keys, unsupported dates/units and non-finite values stop preparation.

Rebuild the bundle offline:

```powershell
.venv/Scripts/python.exe -m scripts.prepare_supply_data
```

**This prepares available inputs, not the missing observed supply targets.** The manifest explicitly records `ready_for_measured_supply_training: false` and zero eligible supervised rows. Keep these files outside `data/raw/supply/operations/`; they are not daily village operations. `train_offline.cmd` continues to require verified delivery/storage history and complete outcomes.

A separate formula-based simulation dataset has now been authorised and prepared: [Simulated supply training](SIMULATED_SUPPLY_TRAINING.md). It retains its assumptions, simulated target policy and separate output location; it cannot be imported as measured operations or reviewed real urgency labels. Its test scores describe agreement with a simulator, not demonstrated accuracy in Maharashtra villages.

Three focused checks passed for calendar gaps/future exclusion, missing-versus-zero behavior, duplicate detection and spatial/availability metadata. No model was trained.
