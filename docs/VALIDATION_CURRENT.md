# Actual validation — 30 October 2026, Asia/Kolkata

- **39 backend tests pass** (18.29 seconds in the latest run): existing ownership/workflow/integration and directory/model tests, plus invalid signup rejection, email normalization, password preservation/hashing, duplicate accounts, validation-error redaction and signup availability. Submitted passwords/input/context are omitted from validation responses.
- **7 Chrome E2E tests pass** (34.6 seconds in the latest run): signup field validation, successful creation/logout/sign-in, existing-account handling, retry after a connection failure; farmer→admin→official→farmer timeline; owned farm editing/economics; duplicate review/reopening; system-admin integration setup/district refresh. Some workflows share a test. Accounts/geography are isolated fixtures in a temporary database.
- TypeScript and both React Vite builds pass. Expo web export passes. Android Hermes export is available; native physical-device runtime/offline restart are not verified.
- Farmer login/signup contain only account fields; API URL and provider-token controls have been removed. The public backend address comes from the mobile app's `.env` at build time. Browser tests forward requests to an isolated API fixture without adding developer controls to the product UI. Updated web and Android exports pass.
- Alembic passes against local SQLite. Neon/PostgreSQL/PostGIS remain credential-blocked. OpenAPI is exported from the actual routes.

Real-source work:

1. Downloaded official NWIC 2026 Maharashtra CSV: **145,829,662 bytes**, SHA-256 `ce6e4f31f351ffd9c149659eaea6f84781add0a0d013ea950a03deae630884ec`, download **60.347 seconds**. Raw data and source metadata are retained under `data/raw/`.
2. Trained/evaluated a real 15-horizon XGBoost research candidate: **1,088,842 observations**, **1,450 derived station identities**, **128,716 complete examples**, **37,953 training examples**. Purged chronological/calibration/district partitions. Last feature preparation **29.56 seconds**, fitting **2.90 seconds**.
3. **Candidate failed release gates**. Day-15 geographic MAE was approximately **4.934 source metres**, versus persistence **1.734**. These are original signed-source units, not validated village depth predictions. Source sign, historical publication availability and geographic mappings also remain unresolved. No operational forecast was released.
4. Real research inference/write benchmark: **1,000 historical feature rows ≈0.440 seconds**, **50,000 ≈3.691 seconds**, including cache/model loading and writes. The 50,000-row inference took **0.390 seconds**, writes **3.020 seconds**. This is not distinct-village coverage or a production SLA.
5. Repaired the timing-out directory import using the documented official HTTPS API. Imported **44,929 unique official villages across all 36 districts**, matching the current catalogue. The 44,931 snapshot rows include two duplicate IDs. The database count is 44,929. Checkpoints retain hashes/retrieval dates, retries and per-district commits. No source coordinates were invented.
6. A live weather request returned **16 days** at the provider grid position, without village assignment. Two official document pages were retrieved. The checked MSAMB commodity response yielded no usable dated quotes; no quote was fabricated.
7. Available local configuration had no Neon database/auth/storage, Gemini or WhatsApp credentials. Their live operation is not claimed. External messages sent: **0**.
8. Downloaded the official historical resource: **529,251,877 bytes**, SHA-256 `b4bf746c09eae07b7998328a5699ddc22989f7ec829509919b60421e7a366822`, **133.808 seconds**. Combined preparation read **5,017,465 observations**, rejecting 15 invalid records; **1,492 derived identities**, **730,287 complete examples**.
9. The revised persistence-anchored model trains through 2023, tunes in 2024, calibrates on available 2025 sequences and evaluates 2026, with 15-day purges and unseen districts. **All 15 existing numerical gates pass in both evaluation groups.** Day-15 chronological MAE **1.426 vs persistence 1.475**, coverage **0.887**; geographic MAE **1.790 vs 1.835**, coverage **0.870**. Units remain original signed-source metres. `SEASONAL_MODEL_EVALUATION.json` discloses prior test-period exposure and the earlier undercoverage that motivated recalibration. **Not an operationally validated or approved village model.**
10. Revised-model research benchmark: 1,000 real historical feature rows **0.957 seconds**, 50,000 rows **5.757 seconds** including cache/model load and temporary writes. The latter inference took **0.805 seconds**, writes **4.199 seconds**. Not distinct-village coverage or an operational SLA; no forecast was published.
11. One-command local launcher starts API, worker and all three web apps, checks readiness and records owned processes. The local links respond on ports 8000, 8081, 5173 and 5174 while those processes run. The new setup panel lists missing variable names, with a read-only provider diagnostic CLI.

Limits:

- Earlier synthetic registry test: 1,000 unavailable snapshots in **9.218 seconds**, 50,000 in **56.866 seconds**. This is separate from numerical inference.
- Dependency audit: **8 findings (3 high, 5 low)** inherited through Expo CLI/config (`zod` 3 and `deepmerge`). Automatic remediation proposed an incompatible SDK 51 downgrade and was not applied. Production dependency/security review remains open. Development servers were not published.
- One installed Starlette/httpx test-transport deprecation warning; tests pass.
- Human Marathi usability, provider session/recovery, live storage compatibility, real WhatsApp/template delivery, PostgreSQL concurrency and statewide prediction release remain unverified.

Machine-readable evidence is in the JSON reports listed in `REQUIREMENTS.md`. Browser screenshots contain labelled test fixtures only.

The latest public-source recheck retrieved weather and both official document pages. Earlier failed receipts remain in the database. The document adapter now preserves successful pages when another request fails. Market quotes in the checked response remain unavailable. See `LIVE_INTEGRATIONS.json` and `READINESS.json`.
