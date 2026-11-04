# Offline training with simulated supply fields

The user authorised simulation on 4 November 2026. **The dataset is ready for simulation-based prototype training.** It is not measured village supply history, and a resulting model is not yet validated for operational forecasts.

## Run training

From this project folder in PowerShell:

```powershell
.\train_offline.cmd --data-mode simulation --target urgency
```

From CMD:

```bat
train_offline.cmd --data-mode simulation --target urgency
```

This uses the existing full offline XGBoost configuration: separate 7-day and 15-day models, 200 trees each, depth 4, up to four CPU threads. It reads the entire prepared simulation dataset and fits on its training partition. There is no network/API/Neon access or dependency installation. It does not publish forecasts or register an approved model.

Check the dataset without training:

```powershell
.\train_offline.cmd --data-mode simulation --target urgency --check-only
```

Optional binary enough/shortage training on the same simulated balances:

```powershell
.\train_offline.cmd --data-mode simulation --target sufficiency
```

No model has been trained on the main generated dataset during preparation. Only isolated temporary test fixtures exercised model saving/loading.

## Dataset and output locations

Latest dataset pointer: `data/raw/supply/simulation/latest.json`. Each versioned dataset contains:

- `simulated-daily-episodes.jsonl.gz`: complete hypothetical daily balances and provenance.
- `simulated-examples.jsonl.gz`: feature vectors and explicitly simulated outcome labels.
- `simulation-manifest.json`: seed, source hashes, assumptions, policy, class counts and file hashes.

The full generated dataset uses all **40,297 available JJM household-count templates**, one episode per template. Every episode has **30 simulated history days and 15 simulated follow-up days**: **1,813,365 hypothetical daily balances** in total. It yields **80,594 examples**, one per horizon per episode. These are not 45 days of observed history for real villages. The remaining directory villages without these profiles are not invented or silently given measured inputs.

Each horizon has **32,171 training cases and 8,126 validation cases**. A deterministic 80/20 hash split holds out complete household-size templates. Both horizons and all daily records of a template stay in the same partition. This tests generalisation within the simulator, not real historical forecasting or performance on actual Maharashtra villages. The six parameter regimes are sampled equally, so class frequency is not a real shortage prevalence estimate.

Training saves new timestamped runs under `artifacts/supply-simulation-models/`, with:

- `simulated-urgency-7d.json` and `simulated-urgency-15d.json` (or `simulated-supply-*.json` for binary mode).
- `training-report.json`, including basis, assumptions, selected features, grouped validation metrics and hashes.
- Parent `latest-run.json`, pointing to that run.

Each model is reloaded and checked against its pre-save validation output. Reports and artifact names identify simulation training. Existing measured-data training remains the default when `--data-mode simulation` is omitted. It still requires actual operations and reviewed outcomes; simulation is not accepted as a substitute in that mode. Keep the simulated bundle outside `data/raw/supply/operations/`.

## Which information is real, borrowed or simulated

| Input | Basis and use |
|---|---|
| JJM household count and source village ID | Administrative size template, observation vintage unknown. ID is provenance only and is not a model feature or a prediction for that village. |
| Household count of zero | One template receives a positive synthetic size sampled from 50–1,500 households. The replacement is explicitly flagged; the original public profile is unchanged. |
| PoCRA district rain/temperature | A 14-day published example waveform, repeated across relative scenario days with a seeded offset. It is not reconstructed historical village weather or a forecast. |
| District template matching | 33 districts use matching reported codes. Palghar is 732 in the JJM extract and 601 in PoCRA: its 899 templates use a unique exact district-name match for scenario weather only. Both codes and the fallback are retained; no operational village crosswalk is asserted. |
| Population, livestock, irrigated area and sector demand | Simulated. No 2011 population or present-day demographic claim is used. |
| Sources, pipes/service links, flow, runtime, outages, losses, tank capacity/levels and tanker volumes | Simulated. No actual scheme connection, meter, pump calibration or tanker receipt is asserted. |
| Shortages and 0–5 targets | Computed simulated outcomes under the policy below. No real review flags or measured urgency labels are created. |
| NWIC historical river/canal/groundwater archives | Retained separately as environmental context. They are not automatically converted into village supply or labelled outcomes. |

## Formulas and assumptions

All ranges below are **experimental sampling choices, not calibrated Maharashtra distributions**. Random seed: **1729**. Cases have relative days −30 through −1 as history and 0 through 14 as follow-up. There is no assertion that the simulated days occurred on the public weather dates.

Household size is uniform from 3 to 6 people per household. Base household demand is simulated population × **55 litres/person/day**. The 55 LPCD service benchmark is documented by the [Ministry of Jal Shakti/PIB](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2226993&lang=1&reg=1); it is not measured consumption. Daily demand varies by a 0.97–1.03 multiplier, with a further assumed 0.5% increase per °C above 30°C.

Livestock count is simulated at 0.05–0.7 heads per person, rounded, with an assumed mixed-animal demand of 20–60 L/head/day. Other demand is 2–20% of base household demand. These values do not represent a surveyed animal mix or institutional inventory.

Irrigated area is chosen so its dry reference demand is 0–150% of base household demand. Daily irrigation uses:

`10,000 × area_ha × max(0, Kc × ET0 − 0.6 × rain_mm − soil_mm) / efficiency`

ET0 is sampled from 3–7 mm/day, Kc from 0.5–1.2, efficiency from 0.45–0.85 and soil contribution from 0–0.5 mm/day. Rainfall effectiveness is assumed to be 60%. Crop, soil and irrigated area are not observed village parameters. Waterlogging, crop stages, paddy/leaching and groundwater recharge are not modelled.

Four disjoint simulated channels are available: pipeline, pumped groundwater, allocated surface water and routine tanker volume. Each case selects 1–4 channels and random positive shares. These are hypothetical service connections. There is no direct conversion of river gauge flow or groundwater depth into village litres.

Six equally sampled operating regimes span:

| Regime | Net daily capacity / reference demand | Usable tank capacity, reference demand-days | Daily delivery limit / reference demand |
|---|---:|---:|---:|
| 1 | 1.40–2.00 | 1.00–4.00 | 1.10–1.40 |
| 2 | 1.03–1.15 | 0.05–0.35 | 1.05–1.30 |
| 3 | 0.93–0.99 | 0.05–0.30 | 0.97–1.10 |
| 4 | 0.78–0.89 | 0.10–0.60 | 0.85–1.05 |
| 5 | 0.45–0.70 | 0.10–1.00 | 0.65–1.00 |
| 6 | 0.01–0.30 | 0.05–0.80 | 0.20–0.80 |

The regime is sampled before the balance is calculated. It is neither a forced class label nor a predictor. Upstream loss is 5–35%; planned operating time is 6–20 hours/day. Daily source-capacity drift is −0.4% to +0.4%, pump variation is ±4%, and outage-start probability is sampled from 0–2.5% per day. An ongoing outage recovers with 60% probability each day. Outages reduce pumped flow to 10%; routine tanker inflow is unaffected. These probabilities are not inferred from Maharashtra outage records.

Initial usable storage is 20–95% of usable tank capacity. Tank capacity already excludes unusable storage. For every day:

`delivered = min(total demand, opening usable storage + net inflow, delivery limit)`

`closing = min(usable capacity, opening + inflow − delivered)`

`overflow = max(0, opening + inflow − delivered − usable capacity)`

Daily balances conserve volume and carry closing storage into the next opening storage. A hypothetical common pool serves household demand first, then livestock, other demand and agriculture. Actual village systems may have separate allocations/pools; this common-pool assumption requires later replacement. Daily totals do not resolve hourly supply, pressure, treatment, potability or distribution equity. No automatic rainfall recharge is added.

## Simulated urgency policy

Policy: `simulated-supply-urgency-v1`, separate from the reviewed real-outcome policy.

| Level | Rule |
|---|---|
| 0 | No shortage within the horizon; reserves never drop below half a reference demand-day. |
| 1 | No shortage, but reserves fall below half a reference demand-day. |
| 2 | Worst daily total-demand deficit is positive but below 10%. |
| 3 | Worst daily deficit is at least 10% but below 25%. |
| 4 | Worst daily deficit is at least 25%, without a first-week level-5 event. A simulated essential failure only in days 8–15 remains level 4 in the 15-day view. |
| 5 | Household delivery is below **60% of that day's household demand on any of days 1–7**. The scenario assumes tanker water is the only emergency fallback. |

The 60%, 10%, 25% and half-day thresholds are project simulation assumptions, **not government drought/tanker standards**. No extra emergency tanker intervention is added after a simulated need event; these are counterfactual balances without that response. Both horizons agree about first-week tanker need. The 15-day urgency cannot be lower than the 7-day urgency.

Binary sufficient means demand is met on **every** day within the horizon, up to numerical tolerance. A sufficient sum across the horizon cannot cancel an earlier simulated shortage. A level-1 watch can still be sufficient.

## Features and validation

Features use only the 30 preceding simulated days and scenario parameters treated as known at issue time: 1/7/15-day lags, preceding 7/15-day means and variability, opening usable storage, storage-demand ratio, inflow-demand ratio, delivery trend, source contributions, pump hours, preceding rain/temperature and static demand/capacity parameters. Future outcomes, outage/drift random parameters, source village IDs and sampling regime are excluded.

The loader checks file hashes, group separation and class coverage, recomputes daily water balances, recalculates features from history and recalculates outcomes from follow-up. It refuses mismatched/tampered examples. No simulation is marked measured or reviewed. Training reports remain unapproved; validation metrics measure simulator agreement and do not establish probabilities or accuracy for real villages.

The full generated dataset passed the final offline check for both horizons, including all 1,813,365 daily balances. Eighteen focused simulator/urgency/trainer tests passed, including tampered-data rejection, conservation, first-week tanker semantics, template separation and save/load tests on isolated temporary fixtures. Compact readiness summary: `data/water/supply-simulation-data.json`. The main dataset remains untrained.

Regenerate entirely offline from local public templates:

```powershell
.venv/Scripts/python.exe -m scripts.prepare_supply_simulation
```

Older bundles are retained. The generator does not train, write to Neon, alter real operations or enable app predictions.
