# Repair status — 30 October 2026, Asia/Kolkata

| Reported issue | Result |
|---|---|
| Only 9,752 villages | Fixed: **44,929 unique villages**, all **36 districts**, independently reconciled against the official catalogue. The importer uses the documented HTTPS API, validates identities, retries, saves checkpoints and commits each district. |
| Model loses to persistence | Fixed for the existing numerical checks: persistence-anchored robust XGBoost with multi-year history, separate 2024 tuning and 2025 calibration. **All 15 horizons pass in both chronological and geographic evaluations.** |
| Missing live credentials | Diagnosed and made actionable: admin setup panel and `python -m scripts.check_readiness --live` show exact missing variables without secrets. Actual Neon, Gemini, storage and WhatsApp credentials are still absent from the existing local configuration. |
| Local working links stop | Added `run-local.ps1` to start API, worker and all three apps and check readiness. It records owned processes and can reuse them. |

The newest model's day-15 geographic MAE is **1.7899**, compared with persistence **1.8346**, in original signed-source metres. Coverage is **0.8704**. Chronological MAE is **1.4256**, compared with **1.4748**, coverage **0.8870**. Full scores, training/tuning/calibration dates and prior holdout exposure are in `SEASONAL_MODEL_EVALUATION.json`. Earlier failed experiments are preserved.

**Operational forecasts remain unapproved.** Authoritative sign/publication-availability evidence, stable station identities, reviewed village/aquifer mappings, a fresh prospective evaluation and human review are still required. Passing the existing numerical gates does not establish those facts or convert groundwater depth to litres. No forecast was published to bypass these requirements.

Validation: **39 backend tests**, **7 Chrome tests**, TypeScript, both web production builds, Expo web export and Android export pass. Signup now has a separate form, confirmation, field validation and readable errors. The revised research benchmark processes 50,000 real historical feature rows, including temporary writes, in **5.757 seconds**; these are not 50,000 distinct villages. Physical-device/offline/provider QA and the documented dependency findings remain open.

Both official scheme pages and 16 weather days were retrieved in the public-source checks. The checked market response has no usable dated quotes. No external messages were sent.

For the remaining account configuration, follow [LIVE_SETUP.md](LIVE_SETUP.md). Machine-readable evidence: `LIVE_DIRECTORY_IMPORT.json`, `READINESS.json`, `LIVE_INTEGRATIONS.json`, `SEASONAL_MODEL_EVALUATION.json`, `SEASONAL_INFERENCE_BENCHMARK.json`.
