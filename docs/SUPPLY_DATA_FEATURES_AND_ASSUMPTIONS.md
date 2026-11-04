# Supply data, features and assumptions

Checked and implemented **4 November 2026, India time**. Target: usable water must meet demand **on every day** of the next 7 and 15 days. A sufficient horizon total cannot cancel an earlier shortage.

## Obtained evidence

Portable audit: `data/water/supply-evidence.json`. Raw responses, hashes and generated features: ignored `data/raw/supply/`. Counts describe this collection, not all records held privately by village operators.

| Source checked | Result | Use |
| --- | --- | --- |
| Six NWIC resources: Maharashtra SW river, CWC river and SW canal discharge; historical and current | **147,069 daily station/parameter records**, filtered to 2021 onward. Current resources downloaded again. Latest CWC/canal observations: **2 November 2026**; SW river ends 30 September. | Publisher observations and hydrological context, not village delivered litres. |
| CWC river resources | Historical and current records include **Satara**. This expands the earlier audit of four different resources. | Source/intake/service-area connection still required. |
| Legacy JJM `/jjmreport/Iot/IoTMonitoring.aspx` | Receiving list: 308 rows/79 village IDs, Gujarat. All-pilot list: 942 rows/284 IDs, Gujarat and Uttar Pradesh. Maharashtra filter empty. Trend response contains one date, 28 October 2026. | Access/coverage evidence; duplicates, units and sensor validity unreviewed. Empty is unknown, not zero supply. |
| JJM root `/jjmreport/IoTMonitoring.aspx` | One Maharashtra pilot listing, **Janori**, Nashik, JJM ID `0000230826`. | Discovery metadata; not a current observation or verified LGD crosswalk. |
| Janori profile and sensor requests | Two source and two scheme records. Inventory names Palkhed Dam; profile lists open wells. Source status is null and scheme status undated. Supply summary: `[[],[],[]]`; device readings: `[]`. | Resolve identity/service-area/date differences. No dated delivery, current population or source yield inferred. |
| CSIR-NEERI Har Ghar Nal | 44 devices; `live=0` (saved mode). Prefixes DL/CH/WB do not independently establish a location. | No current Maharashtra delivery history verified. |
| Maharashtra JJM Functionality Assessment 2024 | Downloaded; quantity tables visually checked and **34 district profiles** extracted. Survey: July-October 2024, 1,023 villages, 12,276 households. | Historical weighted survey context; not 2026 village readings or shortage probabilities. |
| Daily village targets obtained from these public requests | **Zero verified daily village delivery/shortage target records.** | Builder produces zero eligible training rows; no supply model trained. |

Exact URLs, request bodies, retrieval times, hashes, observation ranges and excluded rows are retained in the audit. Dashboard methods are unversioned public read requests, not guaranteed production APIs. No login or approval was bypassed. Older scheme sanctions are inventory metadata, not an old population/supply baseline.

Sources:

- [NWIC CWC river discharge](https://nwdp.nwic.gov.in/dataset/river-discharge-manual-dailly-central-water-commission-cwc), [SW river discharge](https://nwdp.nwic.gov.in/dataset/river-discharge-manual-dailly-maharashtra-surface-water-department), [canal discharge](https://nwdp.nwic.gov.in/dataset/canal-discharge-dataset-telemetry-hourly-maharashtra-surface-water-department).
- [JJM root pilot dashboard](https://ejalshakti.gov.in/jjmreport/IoTMonitoring.aspx), [legacy pilot dashboard](https://ejalshakti.gov.in/jjmreport/Iot/IoTMonitoring.aspx), [village profile](https://ejalshakti.gov.in/jjmreport/JJMVillage_Profile.aspx).
- [NEERI dashboard](https://hargharnal.neeri.res.in/), [official CSIR description](https://csirnews.niscpr.res.in/home/article/841).
- [Assessment listing](https://jaljeevanmission.gov.in/functionality-report-2024), [Maharashtra report PDF](https://jaljeevanmission.gov.in/sites/default/files/2025-12/FHTC_Maharashtra_State%20Report.pdf).
- [JJM API approval guide PDF](https://ejalshakti.gov.in/webapi/Content/JJM_Web_API.pdf). User has not applied; no application sent.
- [DAHD statistics listing](https://dahd.gov.in/en/schemes/programmes/animal-husbandry-statistics): 21st-census manuals found; current Maharashtra village livestock results not verified. Older 20th-census counts are not silently used as current animals.

## Implemented formulas

`services/worker/supply_features.py` preserves each input's basis (`measured`, `operator_reported`, `derived`, `assumed`, `modelled`), source, availability time, unit and all formula operands. A supplied value is never overwritten. No missing field becomes zero.

| Estimate | Formula | Assumptions/evidence required |
| --- | --- | --- |
| Population | occupied households × current mean household size | Dated 2021+ inputs for the same service area. No default household size or 2011 growth projection. |
| Household demand, L/day | population × selected LPCD | **55 LPCD is a JJM household service benchmark**, not measured consumption. Explicit input labelled `assumed`; no automatic norm. Other sectors separate. |
| Usable opening storage, L | 1,000 × (capacity m³ × volume fill fraction − unusable m³) | Current calibrated volume fraction; height fraction only where tank geometry supports it. Dead storage/reserve explicit. |
| Gross stream inflow, L/day | flow L/s × actual runtime hours × 3,600 | Representative flow during actual runtime at the documented boundary. No assumed 24-hour pumping; nameplate capacity alone insufficient. |
| Net stream inflow | gross inflow × (1 − loss fraction) | Stream-specific loss evidence or declared bounds. No default leakage. Apply each loss once; downstream meters may already include upstream losses. |
| Tank outlet delivery | opening + net inflow − closing − downstream physical losses − overflow | Identical daily boundary; explicit losses/overflow, including evidenced zeros. Negative balance rejected. Estimated outlet volume is not metered user delivery or demand. |
| Irrigation, L/day | 10,000 × hectares × max(0, Kc × ET0 − effective rain − soil contribution) / efficiency | Current crop area/stage/Kc/weather and efficiency. [FAO method](https://www.fao.org/4/x0490e/x0490e0a.htm). Raw rain is not automatically effective rain. Not a complete paddy/leaching/soil model. |
| Potential roof capture, L/day | rain mm × connected roof m² × runoff coefficient × capture efficiency | Connected capture, treatment/usability and tank limits. Not recharge or guaranteed drinking water; not automatically added to net inflow. |
| Whole-village demand | household + agriculture + livestock + other | Same boundary/day and no overlaps. Missing sector is not zero. Livestock coefficients and counts remain explicit. |
| Daily shortage | max(0, demand − delivered to users) | Estimated demand produces a scenario deficit. Observed target only if independent demand and user delivery were measured and complete coverage verified. Restricted consumption is not unrestricted demand. |

Daily available water = previous usable storage + usable inflow. Delivery is capped by demand, available water and delivery capacity. Remaining water is capped by storage capacity; excess becomes overflow. This conserves water but assumes within-day availability; pressure, hourly outages and morning-versus-evening timing remain unresolved.

Cusec conversion is **0.028316846592 m³/s per cusec**. River/canal sample means are not integrated into assumed 24-hour volumes. Reservoir level needs an elevation-storage curve, then allocation/intake/treatment/conveyance/operation evidence before village litres. Groundwater depth needs pumping/yield evidence. Neither is converted into delivered litres.

## Features and target protections

Public output: `data/raw/supply/surface-flow-daily.jsonl`. Every gate/parameter/resource stays separate. Features: observed sample mean/min/max and count; 1/7/15-day lags; complete preceding 7-day mean; 7-day change. Identical timestamp duplicates are deduplicated, conflicting values excluded. No missing-day interpolation. Reported zeros retained but not certified as valid sensors. Sample means are not time-weighted daily means. Cross-resource and agency overlaps are never summed automatically; datum/instrument/physical-range validation remains outstanding.

Village features: supply/delivery/demand/shortage lags, preceding 7/15-day means and variability, measured/estimated counts, previous closing storage, storage-days-without-inflow, inflow/demand ratio, delivery trend, weekday and annual seasonality. Weather, surface flow and district survey percentages are **not automatically joined**: reviewed asset mappings and historical publication times are required. Environmental observation dates do not prove availability at an old forecast issue date.

Issue time: 00:00 India time. Daily totals cannot be available before the reporting day ends. Features use only information available at issue time. Labels require all 7/15 future days, complete coverage and explicit `household` or `whole_village` scope. Enough means every day's observed shortage is zero. Missing days, estimates, groundwater forecasts, district percentages and the scenario's own outputs cannot fill targets.

Targets may use measured `unmet_litres`, or a mathematical deficit using **measured independent demand and measured user delivery** plus `demand_independent_of_supply_verified=true`. Deficits calculated from service norms/estimated flow remain scenarios. This supports legitimate derivation without inventing ground truth.

Default split: training horizons finish before **1 January 2026**; 2026 stays holdout; crossing horizons are purged. Final evaluation still requires rolling temporal tests, at least a 15-day gap between label windows, and additional held-out villages/seasons. Per-row eligibility does not establish sample adequacy or model accuracy. No evaluation/model approval is claimed.

## Uncertainty and remaining measurements

`sensitivity()` accepts explicit low/high daily demand, net inflow and storage, plus known capacity and delivery limits. Results: enough throughout tested bounds, short throughout, or sensitive to assumptions. Bounds are **scenarios, not probabilities/confidence intervals**. Rates remain constant within each scenario; supply covers one disjoint usable pool. No arbitrary leakage or demand multipliers inserted. Operator evidence or an explicit planning choice must justify bounds; the code does not establish that reality lies inside them.

Still needed: verified village/service area; current population/demand; usable storage/capacity; deliveries or calibrated flow/runtime; connections/allocations; losses or bounds; crop/livestock/other demand; and observed shortage history. Tanker counts need actual trip volumes/receipts to become litres. A scheme marked functional does not prove delivery today.

## Reproduce and import

```powershell
.venv/Scripts/python.exe -m scripts.collect_supply_evidence
.venv/Scripts/python.exe -m scripts.collect_supply_evidence --offline
.venv/Scripts/python.exe -m scripts.build_supply_training --operations PATH_TO_REVIEWED_JSONL --all-issue-dates
```

The optional PDF table extractor uses the bundled PDF Python runtime: `python -m scripts.extract_supply_survey`. It checks the visually reviewed source hash and refuses changed reports.

Operations JSONL: `village_id` namespaced (e.g. `jjm:0000230826`), completed local `date`, `scope`, `complete_day`, `coverage_verified`, and `fields`. Each field needs `value`, exact `unit`, `basis`, `source`, timezone-aware `available_at`; measurements also need `method`. Population/household fields need `observed_on`. Flags require evidence review; they do not themselves verify a source. Janori's undated inventory population is not imported.

Without operations, the builder produces an empty dataset and missing-data report, not sample villages. Optional `--scenarios` accepts JSON with `[low, high]` for `daily_demand_litres`, `daily_net_inflow_litres`, `opening_storage_litres`, plus `capacity_litres` and `delivery_limit_litres_per_day`. Generated outputs remain ignored; portable evidence/assumption docs are small, reviewable repository files.

This work adds collection and offline feature/formula tools. It does not automatically write estimates into the app's reviewed inputs, enable daily scheduling, train/approve a model or change Maps connection-verification rules.
