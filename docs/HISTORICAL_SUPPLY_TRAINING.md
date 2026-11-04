# Archive-conditioned offline supply training

The earlier simulation dataset used public household-count templates and a short weather waveform. This separate bundle adds actual environmental inputs from the full 98-resource Maharashtra NWIC historical collection. **The inputs are real archived measurements after screening; the 7/15-day supply outcomes remain simulated.** There are zero independently observed village supply targets in this collection. No operational forecast is enabled.

## Run offline

From this project folder, PowerShell:

```powershell
.\train_history_offline.cmd
```

In CMD use `train_history_offline.cmd`. Add `--check-only` to validate the bundle without fitting. Both modes use the local `.venv` and make no API, Neon or network calls. The command defaults to the 0–5 urgency target and the same 200-tree XGBoost configuration for each horizon. Add `--target sufficiency` for binary enough/shortage output.

Models and the run report are saved in timestamped directories under `artifacts/supply-history-models/`. Model filenames identify simulated targets: `simulated-urgency-7d.json` and `simulated-urgency-15d.json`. `latest-run.json` points to the latest run. This command has a distinct dataset and output path from the earlier short-weather simulation and the measured-data trainer.

## What the 39 million records become

| Stage | Count |
|---|---:|
| Historical resources examined | 98 |
| 2021–2025 source rows scanned | 39,240,902 |
| Rows with at least one retained numeric observation | 37,219,643 |
| Rows excluded for district, station or timestamp | 309 |
| Rows without a retained value after screening and duplicate checks | 2,020,950 |
| Resource-level district/day/metric summaries | 1,018,653 |
| Archive-conditioned scenario episodes | 59,543 |
| Labelled examples across both horizons | 119,086 |
| Training / validation examples per horizon | 47,249 / 12,294 |
| Actual observed village supply outcome labels | 0 |

The remaining rows are **not** one-to-one with forecast examples. A district/day can have thousands of sensor readings, multiple parameters, or repeated records. The model gets district/day summaries and lagged features, alongside a simulated water balance. These are not 39 million independent cases of village shortages.

Screening verifies file and row counts; checks dates, recognized district names and nonempty station IDs; rejects recognized sentinel values and clearly out-of-range weather values; and removes equal repeats and conflicting readings within the same resource/station/parameter/timestamp. Duplicate/conflict counters count observations per parameter, so they are not added directly to the row counts. The original archives and exports remain unchanged. A later pass recovered the older “Ahmadnagar” spelling using the [official divisional commissioner district description](https://divcomnashik.maharashtra.gov.in/en/ahmednagar-district/). This is a district alias, not a village or scheme crosswalk.

## Feature and outcome assumptions

- Actual observations are grouped by agency/station/coordinate text and day, then summarized to the publisher's district. District features use medians of resource-level summaries for compatible measurements. Cross-resource copies may still influence those medians; they are not claimed as independent sensors. Quality parameters with different names/units stay separate. Broad range screening is not instrument calibration.
- Rainfall reported as daily is kept separate from hourly rainfall samples. Hourly rainfall is not summed into daily totals without a reviewed accumulation convention. River/canal/reservoir flow is represented as sample context in m³/s; cusecs are converted where explicitly declared. Gates are not summed and flow is never converted into village litres. Water-level features use the magnitude of within-station change, to avoid treating incomparable gauge datums as village supply. Wind direction is represented by circular components.
- The archive feature cutoff is the reference issue date minus two days. This is an assumed availability lag, not evidence that the publisher actually released each reading then. Features include lag-2 values and preceding 7/30-day means and coverage counts. Missing predictor values remain missing.
- Each eligible district/day produces a hypothetical episode with a seeded household-size template from that district. Published daily rainfall and air temperature drive the water-balance scenario where available. Missing driver days use an explicitly identified illustrative PoCRA waveform from a later snapshot. That fallback is part of the simulator, not a filled historical measurement. Other archived measures enter as environmental predictors; no physical source allocation or gauge-to-tap relationship is inferred.
- The target uses the same [simulated supply assumptions and urgency thresholds](SIMULATED_SUPPLY_TRAINING.md). Level 5 means the simulated household threshold is breached in the first seven days under the assumed tanker fallback. It is not a verified tanker request or official drought intensity.
- Reference dates through 2024 are eligible for training, with a gap of at least 15 days after the final training outcome window. Later reference dates form validation; the last archive observations can anchor a case two days into 2026. This is a chronological comparison against simulated outcomes. It is neither a real historical backtest nor a held-out village validation.

## Rebuild and inspect

The full audit and per-resource summaries are under `data/raw/supply/history-context-v2/`. Preparation uses Python with pandas (the local bundled Codex Python was used); training itself does not require pandas. Rebuild without network access:

```powershell
& 'C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m scripts.aggregate_supply_history
.venv/Scripts/python.exe -m scripts.prepare_history_simulation
```

The archive pass resumes from verified local outputs. The dataset builder writes `data/raw/supply/history-simulation/latest.json` and a versioned folder containing compressed episodes, examples, source and file hashes, district coverage, weather fallback counts and a copy of the archive audit. It does not write to the real operations or urgency-label folders.

The trainer checks the audit and file hashes, recomputes the simulated daily balances, features and outcome labels, checks the feature date boundary, and verifies that both saved models reload with the same validation output. Its report gives archive predictor counts and how many were actually used by trees. Those counts show that archived data entered the fitted model; they do not demonstrate an accuracy benefit or real-world reliability.

The completed offline run took **167.7 seconds** from the prepared bundle, including checks and both fits. The fits, validation and save/reload took **20.1 seconds** for 7 days and **20.4 seconds** for 15 days. One-time preparation took about 6m 52s for the first archive scan, 36s for the alias recovery pass, and 3m for the final bundle. These timings are specific to this workspace and machine.

| Horizon | Archive predictors used by tree splits | Accuracy on simulated labels | Simulated level-5 recall |
|---|---:|---:|---:|
| 7 days | 239 | 85.7% | 82.3% |
| 15 days | 244 | 82.1% | 82.2% |

Both models and checksums are saved. Neither model is approved for operational use; even on simulated outcomes both missed about 18% of level-5 cases. The compact machine-readable result is `data/water/history-training-summary.json`. No predictions were published.

## Dashboard scenario estimates

Generate the dashboard snapshot after a model or input update.

```powershell
.venv/Scripts/python.exe -m scripts.score_village_supply
```

The command reads the village registry, checks the saved model hashes, and replaces the local `artifacts/village-supply-predictions.json` snapshot atomically. Overview and Water estimates display it with district, horizon and scenario filters. The list endpoint respects staff jurisdictions. Reviewed projected shortages use the current versioned demand and supply records, separately from the snapshot.

The initial snapshot scored 44,843 of 44,929 registered villages. It used public household profiles matched by unique district and village names for 26,769 villages and district median household estimates for 18,074. The remaining 86 lacked a household template. Both scenarios use district history referenced to 2 January 2026 and assumed village supply. All scored villages received level 3 under Tight supply and level 4 under Lower supply. Current reviewed records are needed to identify which villages have a projected shortage under actual local conditions.
