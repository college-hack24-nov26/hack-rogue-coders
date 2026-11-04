# Offline village water-supply training

Use **train_offline.cmd** from CMD or PowerShell. It uses the project's already installed `.venv` and makes no internet, API, Neon or application-database requests. It does not install dependencies. Training creates local research candidates only; application predictions are separate work.

**Authorised simulation option:** the missing fields now have a separate, labelled prototype dataset. Run `train_offline.cmd --data-mode simulation --target urgency` (PowerShell: `.\train_offline.cmd --data-mode simulation --target urgency`). Dataset counts, assumptions, policy and saved-model locations are in [Simulated supply training](SIMULATED_SUPPLY_TRAINING.md). All measured-data rules below continue to apply to the default measured mode; simulated outcomes do not satisfy those rules.

**Updated default:** the requested [0-5 water-supply urgency scale](SUPPLY_URGENCY_SCALE.md), with level 5 meaning assessed tanker need within seven days. `--target sufficiency` keeps the earlier binary training mode. Urgency training additionally requires reviewed historical outcome annotations; the class numbers are not invented from the public archives.

## Commands

PowerShell:

```powershell
Set-Location 'E:\Z-PROJECTS\PHALTAN HACKTHON\Phalatan-hackathon'
.\train_offline.cmd
```

CMD:

```bat
cd /d "E:\Z-PROJECTS\PHALTAN HACKTHON\Phalatan-hackathon"
train_offline.cmd
```

Check the records without fitting models:

```powershell
.\train_offline.cmd --check-only
```

Optional: combine every operations file in additional folders, or individual files:

```powershell
.\train_offline.cmd --operations "D:\village-logs" --operations "D:\other-logs\daily.jsonl"
```

When `--operations` is specified it replaces the default input folder; repeat the option to include all desired folders. Repeated references to the same physical file are deduplicated. Duplicate village/scope/day records across different files stop training so revisions/overlapping logs can be reconciled.

## Put actual records here

Default input folder: **data/raw/supply/operations/**. Every `.csv` and `.jsonl` in that folder and its subfolders is considered. Other file types are ignored. A header-only CSV is provided at `templates/village_supply_daily.csv`; the local `daily.csv` copy starts empty. Do not enter invented examples in the real training folder. Records remain local and are ignored by Git.

The current downloaded public data contains **zero verified village daily supply/shortage targets and zero reviewed urgency labels**. The launcher therefore currently produces a missing-data report and exit code **2**; this is expected. It will train when reviewed operations provide enough valid history and target outcomes. Existing groundwater, weather, river/canal archives and survey tables do not supply village target labels and are not automatically fed into this trainer. The command does not retrain the old groundwater models.

Further public collection on 4 November added JJM profiles, PMC tanker registers, state tanker reports and PoCRA weather. Their coverage and concrete limits are documented in [Public supply-data status](PUBLIC_SUPPLY_DATA_STATUS.md). Their raw files remain outside the operations folder: scheduled trips and tap counts are not delivered litres or shortage labels.

## Daily CSV columns

One row represents one completed day for one village and one scope. Use a namespaced ID such as the verified `LGD:...` or `jjm:...`; these ID systems require a reviewed crosswalk before merging. Template columns:

| Column | Meaning |
| --- | --- |
| `village_id`, `date` | Reviewed village/service area and local date `YYYY-MM-DD`; 2021 onward. |
| `scope` | `whole_village` by default. `household` requires `--scope household`; the two scopes are not mixed in one model. |
| `available_at` | Actual time the daily record became available, with timezone, such as `YYYY-MM-DDT00:00:00+05:30`. A complete measured daily total cannot precede that day's end. Do not substitute an observation date for unknown historical publication time. |
| `basis` | Explicit `measured`, `operator_reported`, `assumed` or `modelled`. Not guessed from a numeric value. Formula-derived fields are recomputed from supplied operands. |
| `evidence_source`, `measurement_method` | Operator log/meter reference and method. `measured` requires a method; flags must be backed by evidence. |
| `complete_day`, `coverage_verified` | `true` only when the record covers the entire day and the named service scope. Blank means unverified. |
| `demand_independent_of_supply_verified` | `true` only if measured demand is independent of delivery restrictions; required for calculated observed-shortage labels. |
| `net_inflow_litres` | Measured/estimated usable incoming water at the defined village boundary; no overlapping streams counted twice. |
| `delivered_litres` | Water delivered to users in that scope; inlet flow is not automatically user delivery. |
| `closing_storage_litres` | Usable storage at the end of the same day. Previous closing storage supplies the next day's opening feature. |
| `demand_litres` | Independently measured demand, or explicitly labelled demand estimate. Constrained consumption alone is not unconstrained demand. |
| `unmet_litres` | Independently measured shortage volume. Leave blank if unknown. Norm-based/assumed shortage is not ground truth. |
| `notes` | Optional operator notes; not a model feature. |

Numeric blanks stay missing. Zero means an explicitly evidenced zero. Do not use one row-level `basis=measured` for quantities that include assumptions. Override metadata per quantity with columns such as `demand_litres_basis`, `demand_litres_source`, `demand_litres_method`, `demand_litres_available_at`.

Additional fields listed in `services/worker/supply_features.py:UNITS` may be supplied with their exact units/metadata, including actual runtime, flow, tank capacity/fill/reserve, population, crop/weather inputs and loss assumptions. Population/household operands additionally require their `<field>_observed_on` column. Supported formulas retain lineage. An input carrying `basis=derived` must include supported operands, otherwise training stops; fabricated derived labels are never accepted.

Pump operation, outages, tanker volumes and shortage-location logs remain useful supporting evidence. Convert actual flow/runtime or tanker receipts into properly scoped daily quantities with explicit methods and uncertainty before using them; the trainer does not infer litres from pump state, tanker count or geometry.

## Targets, features and validation

In default `--target urgency` mode, two six-class XGBoost candidates learn reviewed 0-5 supply-urgency outcomes for the 7- and 15-day assessment views. See [the annotation template, level definitions and critical-event checks](SUPPLY_URGENCY_SCALE.md). Labels require complete follow-up, source/reviewer/rationale and verified assessed tanker timing for level 5.

In `--target sufficiency` mode, two binary XGBoost classifiers learn shortage on **any day** of the next 7 days, and shortage on **any day** of the next 15 days. Their negative class means no shortage on every day of that horizon. No groundwater-depth target is used. Neither mode is a trained demand/inflow forecaster or volume regressor.

**Climate drought intensity is not included.** The requested operational 0-5 score is supply urgency. Reports distinguish these capabilities explicitly. [Drought intensity requirements](DROUGHT_INTENSITY_REQUIREMENT.md) distinguish drought-index conditions, shortage magnitude and supply urgency.

In binary sufficiency mode, each target requires complete measured shortage outcomes for every future day. An observed deficit calculated as `max(0, demand_litres - delivered_litres)` is also accepted when **both operands are measured**, scope/day coverage is verified and demand independence is explicitly verified. Estimated demand or estimated delivery cannot manufacture an observed target. Features may include estimates, whose provenance/counts remain explicit. Urgency mode instead uses separately reviewed, fully followed-up operational class outcomes; it does not require missing shortage volumes to be fabricated.

Features use information available by 00:00 India time on issue day: 1/7/15-day lags, complete preceding 7/15-day averages and variability, measured/estimated counts, usable storage, storage coverage, inflow/demand ratio, delivery trend and seasonality. Unknown values remain missing; XGBoost handles them. Features constant or entirely missing in the training partition are removed using training data alone. Village IDs and future outcomes are not model features.

All input records are read and audited. Incomplete/unlabelled examples cannot train a supervised model. By default, the latest **20% of eligible issue dates** are reserved for chronological validation. Training label windows must finish at least **15 calendar days before** validation starts, and those labels must already have been available at that cutoff. Validation records are not used for fitting, feature selection or parameter tuning. Overlapping windows within a partition remain correlated; reported row count is not an independent sample count.

To preserve an explicit 2026 holdout when suitable older operations exist:

```powershell
.\train_offline.cmd --validation-from 2026-01-01
```

This trainer's automatic split differs from the older `build_supply_training.py` exporter, which fixes 2026 as holdout. The automatic split also permits new 2026-only logs to create future research candidates when sufficient observations accumulate. It is not a claim that any previously inspected 2026 data is an untouched final test set.

Default candidate gates per horizon: **100 training rows, 30 validation rows and 5 examples of each class in both partitions** (all six levels for urgency, both classes for binary sufficiency). These are mechanical minimum checks, not a statistical guarantee. A single village can support a research fit; independent village/season checks, probability calibration and prospective validation remain outstanding. No automatic model approval or publishing occurs.

## Outputs and exit codes

Every run gets a new directory under **artifacts/supply-offline/**. Old runs are preserved. **latest-run.json** identifies the latest report, including blocked runs.

- `training-report.json`: status, input hashes, inclusion/exclusion counts, split dates, assumptions, validation metrics and release limitations.
- `engineered-operations.jsonl`: normalized inputs and formula lineage.
- `examples.jsonl`: candidate features and labels; incomplete rows are retained for auditing but excluded from fitting.
- `urgency-7d.json`, `urgency-15d.json` in default urgency mode, or `supply-7d.json`, `supply-15d.json` in binary mode: model files only after data gates pass and fitting succeeds. Feature order/class mapping are recorded in the report. Both saved models are reloaded and checked against validation output.

Urgency validation reports level error, within-one-level accuracy, level-5 recall/missed cases and a six-class confusion matrix. Binary validation reports shortage recall/precision, accuracy and confusion counts. Both include Brier score against training prevalence. Evaluation predictions are internal checks, not published village forecasts. All models remain `approved=false`, including candidates that beat the baseline.

Exit **0**: training completed, or check-only passed. Exit **2**: missing/invalid data or missing installed dependency. Exit **1**: training execution failed. Inspect the report before using any artifact; a failed run may contain partial files and is not a complete model package. No deployment, app integration or prediction generation is performed.

XGBoost uses local CPU threads (default up to four) and JSON model serialization. References: [classifier API](https://xgboost.readthedocs.io/en/stable/python/python_api.html#xgboost.XGBClassifier), [model serialization](https://xgboost.readthedocs.io/en/stable/tutorials/saving_model.html). See [all data/formula assumptions](SUPPLY_DATA_FEATURES_AND_ASSUMPTIONS.md).
