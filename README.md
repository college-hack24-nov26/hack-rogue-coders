# JalSathi

WhatsApp complaint registration, verified farmer-account linking, shared tracking and setup instructions: [implementation and demo guide](docs/WHATSAPP_INTEGRATION.md).

Local monorepo implementing the shared water-complaint workflow and evidence-aware farmer tools from the supplied PRD. Officials' actions are **demonstration only**, with no government integration. No production readings, village IDs, prices or model scores are fabricated.

## Run on Windows

Install Node 22 LTS and Python 3.12+ with `uv`. From `C:\Jalsathi`:

```powershell
uv sync
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Set a random local signing key in `.env` (32+ characters), or configure Neon authentication. Never paste credentials into chat. The old prototype `.env` is deliberately not copied.

```powershell
uv run alembic upgrade head
npm install
uv run uvicorn services.api.main:app --host 127.0.0.1 --port 8000
```

Separate terminals:

```powershell
uv run python -m services.worker.main
npm run admin
npm run officials
npm run mobile
```

API documentation: http://127.0.0.1:8000/docs. Admin: http://localhost:5173. Officials: http://localhost:5174. Expo prints its device/preview address. Use a trusted-network LAN API address in `apps/farmer-mobile/.env` for a physical phone; localhost refers to the phone itself. If using the preinstalled portable Node, prepend `C:\Users\aniru\.codex\jalsathi-tools\node-v22.16.0-win-x64` to PATH.

For one-command local web startup, run `powershell -ExecutionPolicy Bypass -File .\run-local.ps1`. This starts the API, worker, farmer web app (8081), admin (5173) and officials demo (5174), then checks that they respond. Use `-Build` to rebuild after source changes, or `-Install` on a fresh checkout. Keep the services running while using the links; process ownership is recorded in `local-processes.json`. Provider setup and the remaining release requirements are described in [LIVE_SETUP.md](docs/LIVE_SETUP.md).

## Import real geography and provision staff

No test village data is seeded into the application. Provide an official versioned directory CSV with columns `id,name,district,taluka,jurisdiction,latitude,longitude` and import:

```powershell
uv run python -m scripts.manage import-villages path\to\directory.csv --source "official source URL" --version "directory-release-date"
uv run python -m scripts.manage create-user --email reviewer@example.org --role admin --jurisdictions district-code
uv run python -m scripts.manage create-user --email official@example.org --role official --jurisdictions district-code
uv run python -m scripts.manage create-user --email operator@example.org --role system_admin
```

Passwords are prompted securely. For Neon identities add `--auth-subject` matching the verified JWT subject; never accept a role from registration. Farmers register in local development and select imported villages. The same email/password clients use the Neon proxy when `AUTH_MODE=neon`; token entry remains available for operator troubleshooting. Full managed mobile/session/recovery behavior still needs a real project check. Staff invitations, scope changes and revocation are available in Admin → Access & invitations.

Set `DATABASE_URL=postgresql+psycopg://...` with TLS parameters for Neon, run Alembic against the selected branch, and set `AUTH_MODE=neon`, `ENVIRONMENT=production`, JWKS URL, issuer and audience. Also configure `NEON_AUTH_URL`, the provider-allowed `NEON_AUTH_ORIGIN`, and a random 32+ character `SESSION_ENCRYPTION_KEY`. Refresh sessions are encrypted server-side. The migration creates PostGIS and a boundary index; database role permission is required. Development login is disabled outside development. For production photos set `STORAGE_MODE=s3` and configure the S3-style endpoint/private bucket. Region availability and signed PUT compatibility need live verification. Local development photos use private `.private/` storage and authenticated API access.

## Walkthrough

1. Open the farmer app and choose **Create farmer account**. Enter an email, a password with at least 10 characters and its confirmation, then choose **Create account**. Successful signup signs you in. Existing accounts use **Sign in**. The backend address comes from `EXPO_PUBLIC_API_URL` in `apps/farmer-mobile/.env`; rebuild after changing it. Login/signup have no API URL or token-entry controls. Select an imported village, save a farm and submit a report. A local draft is not a server submission.
2. Sign in to the separate admin portal, review original content, enter a sanitized public report, choose the matching jurisdiction and accept with a reason.
3. Sign in to officials demo using a provisioned account in that jurisdiction. Acknowledge, assign, progress and resolve. Rejected/pending/other-scope records return 404 even through direct API calls.
4. Farmer tracking shows the same event timeline. Admin withdrawal removes publication while preserving history.
5. Create baseline versions with explicit sectors, dates and assumptions. Seven- and fifteen-day summaries overlap. Supply/shortage stays unavailable without verified supply.

## Integrations and data

Webhook callback: `/api/v1/webhooks/whatsapp`. Configure Meta verification token, app secret, business phone ID and API version server-side. Signed messages enter a durable conversation that collects the issue and an imported village, shows a summary, and creates a shared complaint only after `YES`. Location accepts `village, taluka, district` or `LGD:<imported id>`. The real complaint UUID is its reference. Farmer app Tickets can generate a one-time `LINK` command for verified account linking and reference tracking. `HELP`, `NEW`, `CANCEL`, `STATUS <reference>` and `REPLY <reference> <text>` are supported. `SUBSCRIBE`/`UNSUBSCRIBE` control optional notifications, rechecked at dispatch. Images use the existing private inspection pipeline. `ALLOW_EXTERNAL_SEND=false` prevents real messages; enabled test sending also requires `WHATSAPP_APPROVED_RECIPIENTS`. Outside the service window, delivery requires opt-in and an actually approved status template. Blocked/dead jobs can be retried by a system administrator after their cause is fixed. Real Meta delivery remains untested; see the linked guide for commands, setup and limitations.

Use `python -m scripts.manage import-evidence file.json --kind market|document|source_fetch` for reviewed real-source imports. Market objects require `source,source_date,units,market,variety,price`; documents require source/date. Admin → Sources & data flow queues weather, bounded MSAMB commodity, optional AGMARKNET, official document and directory refresh jobs. Enable `ENABLE_DAILY_INGESTION=true` only when source access and village coordinates have been reviewed. Weather retains provider-grid provenance; schemes retain actual passages and separate publication/retrieval dates. Village/source/aquifer mapping still requires reviewed evidence.

The complete official directory has been imported: **44,929 unique villages across all 36 source districts**, reconciled against the source catalogue (see `docs/LIVE_DIRECTORY_IMPORT.json`). `uv run python -m scripts.import_official_directory` resumes validated district checkpoints with bounded retries using the documented official HTTPS API. It rejects changed identities and count mismatches. Directory coverage does not imply forecast coverage: source coordinates and reviewed station/aquifer mappings remain absent. Supply-source registration and village allocation are in Admin → Water estimates; notices are in Markets & schemes; geography/crosswalk edits are in Village registry.

For dated farm planning, queue a shared-grid refresh with `python -m scripts.manage queue-weather --village <id>` and run the worker. Import an agronomy JSON list with `import-evidence file.json --kind agronomy`; each entry requires `crop,source,source_date,reviewed:true,reviewer,effective_rain_factor,efficiencies` (by irrigation method), and `stages` containing `name,start_day,end_day,kc`. These must be real reviewed agronomy definitions, not invented defaults. Plans fail closed for stale weather, incompatible units or unsupported stages. Official document imports may include `passage` and `publication_date`; the assistant retains their source/date citations alongside canonical numerical evidence.

Gemini keys/models stay server-side. Without configured credentials or user consent the assistant returns an explicitly labelled evidence-only Marathi/English response. There is no released model artifact in this repository; forecasting remains unavailable. See [requirements and honest completion report](docs/REQUIREMENTS.md) for implemented, verified, credential-blocked, data-blocked and incomplete items.

## Checks

```powershell
uv run pytest -q
npm run typecheck
npm run build
npm run export -w @jalsathi/mobile
uv run python -m scripts.benchmark
npx playwright test
```

Tests use isolated, clearly labelled fixtures only. `scripts.benchmark` measures synthetic registry/unavailable snapshots. `scripts.benchmark_real_model` separately measures the trained research artifact on actual historical feature rows using temporary storage. Neither proves statewide village coverage. See [validation results](docs/VALIDATION.md). No public deployment or messages to real users are authorized or performed.

The browser test uses an installed Chrome executable (`CHROME_PATH` overrides its default Windows location) and starts temporary API/preview servers. It requires prior web builds and the Expo web export. `start.ps1 -Install` installs dependencies, migrates and starts hidden API/worker processes with local log files; it prints their IDs for stopping them.

Operators may register a validated model using `python -m scripts.manage register-model manifest.json` and import dated location feature records using `import-features file.json`. Place the hashed artifact under `MODEL_ARTIFACT_ROOT`. The manifest must pass all 15-horizon gates, verify source sign/availability, contain calibrated uncertainty and independent chronological/geographic scores. Feature records retain station/grid identity, reviewed mappings, observation/issue times and ordered values.

A **real, failed research candidate** and evaluation now exist under `artifacts/nwic-research/`; it is visible as withheld research metadata in Model Lab and is not operational. Reproduce with `uv run python -m scripts.train_groundwater data/raw/nwic-maharashtra-2026.csv`. Actual scores are in `docs/REAL_MODEL_EVALUATION.json`, and inference timings in `docs/REAL_INFERENCE_BENCHMARK.json`. Do not approve the candidate to hide a failed persistence comparison. Public integration verification can be repeated with `uv run python -m scripts.verify_live_integrations`. Production credentials and a valid model remain external release requirements.

The persistence-anchored follow-up predicts changes using relative historical lags and robust loss. Its tuning, interval calibration and final evaluations are separate, with 15-day purges and held-out districts. Reproduce the 2026-only experiment with `python -m scripts.repair_forecast data/raw/nwic-maharashtra-2026.csv`; see `docs/RESIDUAL_MODEL_EVALUATION.json`. Download the real historical archive with `python -m scripts.download_groundwater`, then use `--history data/raw/nwic-maharashtra-2021-2025.csv --year-holdout 2026 --output artifacts/nwic-multiyear --report docs/MULTIYEAR_MODEL_EVALUATION.json` for the multi-year experiment. Previous test-period exposure is disclosed. Neither command approves a model or publishes a forecast.

The final experiment adds `--full-year-calibration --cache artifacts/nwic-multiyear/training_cache.npz --output artifacts/nwic-seasonal --report docs/SEASONAL_MODEL_EVALUATION.json` to the same historical-data command. It trains through 2023, tunes in 2024 and calibrates using available 2025 sequences before evaluating 2026. **All 15 existing numerical gates pass in both test groups**, with no changes to their thresholds. It remains unapproved pending source/mapping/prospective review. See [repair status](docs/FIX_STATUS.md). Benchmark this artifact with `python -m scripts.benchmark_real_model --model-root artifacts/nwic-seasonal --features artifacts/nwic-multiyear/training_cache.npz --report docs/SEASONAL_INFERENCE_BENCHMARK.json`.

`uv run python -m scripts.retention` previews expired transient records; `--execute` explicitly removes only eligible auth sessions, AI traces and source-fetch logs. It never deletes original complaints, audit history, models or published forecast lineage. The development retention policy and deletion requests need production review.
