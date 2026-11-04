# Water-supply urgency: levels 0-5

Requested and added 4 November 2026. The offline launcher now defaults to `--target urgency`, training six-class candidates for the 7- and 15-day assessment views. This is the project's operational water-supply urgency scale. It does not require SPI/SPEI to define its targets and is not an official climate-drought classification.

| Level | Name | Outcome definition |
| --- | --- | --- |
| 0 | Normal | Supply meets the reviewed service scope through the assessment period. |
| 1 | Watch | Early stress or declining reserves; routine service is maintained. |
| 2 | Moderate | Manageable intermittent deficits; routine adjustments needed. |
| 3 | High | Significant recurring deficits; planned mitigation required. |
| 4 | Severe | Severe sustained deficits; urgent contingency planning required, without verified tanker need during the first seven days. |
| 5 | Critical | Reviewed outcome confirms tanker water is required within days 1-7, including day one. |

Machine-readable definitions and policy version `supply-urgency-v1` are in `services/worker/supply_urgency.py`. Levels 1-4 are descriptive project labels: numeric deficit thresholds have not been established and are not invented by the code. Operators must apply a consistent rubric with supporting evidence; quantitative local thresholds can be added through a new version after evidence review. Model evaluation cannot make inconsistent labels reliable.

The score is ordered: 5 is higher urgency than 4, but not five times level 1. A class is not a probability. Multiclass XGBoost learns six class probabilities; the validation class is their maximum-probability class. Training currently uses the ordinary multiclass objective, with ordering checked by evaluation metrics; it does not claim a custom ordinal loss or calibrated probabilities.

## Level 5 means need, not a dispatch

The label requires an evidence-backed `tanker_required_on` date between `issued_on` and `issued_on + 6 days`. A tanker sent somewhere does not itself prove necessity. Tanker availability, vehicle capacity, route or delivery scheduling is not predicted by this model. Other emergency-water options are not automatically relabelled as tanker need.

For an ongoing need, record the issue date as the effective required-on date after review and explain the original event in the rationale. Missing tanker assessment is unknown, not level 0 or evidence that no tanker was needed.

The first-seven-day definition is identical in both assessment views. If reviewed 7- and 15-day labels are both supplied for one village/issue, they must agree about level 5. The maximum urgency over fifteen days must not be below the maximum over its first seven days. A later prediction implementation will need to reconcile independently fitted model outputs; that consistency layer is not implemented here.

## Input files

1. Daily history remains under `data/raw/supply/operations/`: actual/explicitly estimated supply, delivery and storage with source and availability metadata.
2. Outcome annotations go in **data/raw/supply/urgency-labels.csv**, outside the operations folder. A blank template is `templates/supply_urgency_labels.csv`. JSONL and repeated `--urgency-labels PATH` options are also supported.

Required outcome columns:

| Column | Meaning |
| --- | --- |
| `village_id`, `scope`, `issued_on` | Same reviewed service identity/scope as daily operations; issue date in India time. |
| `horizon_days`, `level` | 7 or 15; integer from 0 to 5. |
| `policy_version` | `supply-urgency-v1`. |
| `basis` | `observed_outcome`. Scenarios and assumed classes cannot train the model. |
| `reviewed`, `followup_complete`, `tanker_need_assessed` | Explicit `true`, backed by evidence. All three are required. |
| `tanker_required_on` | Mandatory date in days 1-7 for level 5. A confirmed first-week need cannot be labelled 0-4. For later need, retain its observed date and apply the reviewed noncritical rubric. |
| `available_at` | Timezone-aware timestamp after complete horizon follow-up, never after the audit time. Historical labels must already be available at the training cutoff to enter training. |
| `source`, `reviewer`, `rationale` | Evidence reference, accountable reviewer and reason for this classification. |

These are outcome labels for historical issue dates, not a current operator guess about the future. Review flags are declarations checked for completeness, not automatic government verification. Annotators should use observed delivery, shortages, reserves and assessed need, not the app's own earlier predictions, to avoid circular labels. Emergency deliveries can maintain observed supply even when tankers were needed, so need and supplied volume are separate facts.

The trainer joins outcomes by village/scope/issue/horizon and keeps labels, tanker dates, reviewer and rationale out of input features. It requires seven preceding delivery records and previous closing storage as the candidate history gate. Existing measured/estimated feature counts and lineage are retained. Weather/source context remains excluded until valid connections and historical availability are established.

## Run offline

```powershell
.\train_offline.cmd
# Explicit equivalent:
.\train_offline.cmd --target urgency
# Check without fitting:
.\train_offline.cmd --target urgency --check-only
# Preserve earlier binary enough/shortage training:
.\train_offline.cmd --target sufficiency
```

By default each horizon needs 100 eligible training rows, 30 validation rows and at least five reviewed examples of **every level 0-5 in each partition**. Missing classes stop training instead of creating fabricated samples or unsupported six-class output. Class gates are minimum software checks, not proof of adequate coverage for 44,929 villages. Temporal purging and local-only execution are unchanged.

New candidates are `urgency-7d.json` and `urgency-15d.json`, with the policy, class mapping and feature order in `training-report.json`. Metrics include mean absolute level error, within-one-level accuracy, level-5 recall, missed critical cases, severe critical underestimates, six-by-six confusion counts, and multiclass Brier score versus training prevalence. These remain unapproved research candidates even when metrics pass. Independent geographic/prospective checks, class calibration, false-negative review and later prediction integration remain outstanding.

Current real inputs have zero reviewed urgency annotations and no eligible village history. The launcher therefore reports missing data. No model was trained on real village records, no level assigned to a real village and no tanker request or prediction published. Tests use isolated fixtures only.
