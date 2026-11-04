# WhatsApp complaint integration — implementation and demo guide

Latest local preparation, running service ports and verified temporary HTTPS callback: [real-test readiness, 4 November 2026](WHATSAPP_TEST_READINESS.md). This newer report supersedes the earlier environment and startup status below.

Implemented locally on 3 November 2026 in `C:\Users\aniru\.codex\hack-rogue-coders`.
No commits, pushes, production migrations, public deployment or real WhatsApp sends were performed.

## Implemented workflow

1. Meta posts to the existing signed webhook. The API verifies the business phone ID and HMAC signature before storing a provider message and durable intake job.
2. `Hi` starts a Marathi/English conversation. The issue stays in a durable draft, not a premature complaint. Marathi script selects Marathi; `ENGLISH` and `MARATHI` explicitly switch language.
3. Send the issue, then `village, taluka, district`. Location must uniquely match the imported directory, case-insensitively. An explicit `LGD:<official village code>` is also supported. Ambiguous or unknown locations require clarification.
4. A summary asks for `YES`, `EDIT ISSUE <description>`, `EDIT LOCATION <village, taluka, district>`, or `CANCEL`. Consent to store the details is included in the confirmation prompt.
5. `YES` invokes the same validated complaint creation function as the farmer app, using the existing `Complaint`, `Event` and UUID generator. The actual complaint ID is the reference ID. The repository uses UUIDs, so no competing `JAL-` identifier was introduced.
6. Complaint creation, draft reset, inbound deduplication and confirmation outbox insertion commit together. The delivery job runs separately. A failed transaction cannot leave a success reply; a failed send cannot erase the complaint.
7. The complaint appears in the existing scoped admin inbox with `channel=whatsapp`. Admin acceptance and jurisdiction routing publish that same record to the existing officials demo queue. Existing acknowledgement, assignment, progress, resolution and reopening transitions remain in use.
8. `STATUS <reference>` returns the sender's complaint status. `REPLY <reference> <text>` saves clarification and returns a `needs_information` complaint to `submitted`.
9. In the farmer app, open Tickets → **Link WhatsApp complaints**. Send its one-time `LINK <code>` command from the WhatsApp account within ten minutes. This proves possession of both accounts, associates existing and future reports with the app account, and permits normal app reference search. Refresh tickets after linking. Typing a phone number or knowing a reference does not grant access.
10. `SUBSCRIBE` enables optional status updates; `UNSUBSCRIBE` stops them, including notifications already queued. Authorised review/action updates use durable delivery jobs and actual application statuses. Outside the customer-service window, approved template configuration and consent are required.

`HELP`, `NEW`, `CANCEL`, language commands, status requests and consent commands do not discard the active draft. `NEW` asks the sender to finish or cancel an existing draft. Multiple completed complaints are supported. Restarting the worker does not lose progress. Sender ordering is checked and PostgreSQL intake uses transaction advisory locks. Version uniqueness and the job retry mechanism protect concurrent draft updates.

Optional GPS coordinates are validated and retained. Up to three JPEG/PNG photos can be attached before confirmation. After registration, separate jobs retrieve them from Meta, check trusted HTTPS hosts, size, hash and image decoding, strip metadata by re-encoding, and store them through the existing private attachment pipeline. Officials still need the existing per-photo admin approval. Failed media jobs do not undo a registered complaint.

## Existing functionality reused

- FastAPI, SQLAlchemy, the selected SQLite/PostgreSQL database and existing migrations.
- `ComplaintInput` validation; `Complaint`, `Event`, `ProviderMessage`, versioned `Record` and `Job` tables; `uid()` IDs.
- Existing authenticated farmer tracking, ownership enforcement, admin scope and review rules, officials publication and service lifecycle.
- Existing worker leases, retries, backoff, dead letters, blocked-job inspection and system-admin retry endpoint.
- Meta Cloud API transport, webhook verification, service-window/template checks and private image inspection/storage.
- Existing app and staff interfaces; no separate complaint dashboard or complaint database.

The complaint creation code was extracted into `services/api/complaints.py` and is called by both app submission and WhatsApp intake.

## Files

New:

- `services/api/complaints.py` — shared creation service.
- `services/worker/whatsapp.py` — durable conversation and verified account linking.
- `services/worker/whatsapp_media.py` — private media import.
- `tests/test_whatsapp.py` — mocked integration, delivery, security and recovery tests.
- `docs/WHATSAPP_INTEGRATION.md` — this guide.

Modified:

- `.env.example` and `services/api/config.py` — approved test-recipient setting.
- `services/api/main.py` — shared app creation, linking code endpoint, readable location/GPS details, status snapshots, receipt handling and input validation.
- `services/worker/main.py` — intake dispatch, media jobs, notification consent checks, approved-recipient enforcement and Meta acknowledgement validation.
- `apps/farmer-mobile/App.tsx` — account-link command, reference search and readable location.
- `packages/api-types/index.ts` — optional location/GPS response types.
- `packages/web-ui/Portal.tsx` — full reference, submission channel, readable location and GPS in staff details.
- `tests/test_workflow.py` — confirmation-before-creation expectations.
- `tests/browser/workflow.spec.ts` — farmer linking-command and reference-search assertions.
- `docs/openapi.json` — regenerated API contract.
- `README.md` — link to this guide and updated WhatsApp overview.

## Database changes and migration

No new table, column, complaint status or ID format is required. Conversation state, consent versions, processed-message markers, linking codes, verified associations and delivery receipts use the existing versioned records table. Complaints remain in `complaints`; attachments and delivery jobs reuse existing storage.

On a fresh or older installation, run the existing migrations against the intended database:

```powershell
Set-Location 'C:\Users\aniru\.codex\hack-rogue-coders'
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Fresh SQLite migration to `0002` was verified using a separate temporary database at `C:\Users\aniru\.codex\tmp\whatsapp-migration-check.db`. No application database was migrated or modified during this work. PostgreSQL migrations and concurrent-worker behavior require testing on your database branch.

Historical, pre-integration WhatsApp complaints retain their records and statuses. The new conversational draft behavior applies to new messages. Already completed historical provider jobs are not replayed. An old `awaiting_location` complaint needs the existing review/message workflow; it is not silently converted into a new draft.

## Environment variables

Keep secrets only in the existing ignored root `.env`; preserve its values. The farmer app receives only its public API URL.

Local configuration inspection found all six WhatsApp values missing: `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_API_VERSION` and `WHATSAPP_APPROVED_RECIPIENTS`. External sending was confirmed disabled. Template configuration is additionally required for outside-window delivery.

| Variable | Required value or source |
|---|---|
| `DATABASE_URL` | Existing shared database. Local default: `sqlite:///./jalsathi.db` |
| `ENVIRONMENT` | `development` for local demo |
| `AUTH_MODE` | `local` for local demo; retain configured Neon settings if already used |
| `LOCAL_SIGNING_KEY` | Locally generated random key, at least 32 characters, for local auth |
| `WHATSAPP_APP_SECRET` | Meta app → Settings → Basic → App secret |
| `WHATSAPP_VERIFY_TOKEN` | Generate a private random string locally and enter the same value in Meta webhook setup |
| `WHATSAPP_ACCESS_TOKEN` | Access token for the selected test business phone from the app's WhatsApp API setup/testing screen; replace expired temporary tokens |
| `WHATSAPP_PHONE_NUMBER_ID` | Phone number ID shown for Meta's test sender, not its displayed telephone number or business account ID |
| `WHATSAPP_API_VERSION` | Supported Graph API version shown for your app, including `v`; no version is fabricated or hard-coded |
| `ALLOW_EXTERNAL_SEND` | Keep `false`. Set `true` only for an explicitly authorised real-message test |
| `WHATSAPP_APPROVED_RECIPIENTS` | Comma-separated recipient numbers approved in Meta test setup, digits with country code, matching webhook sender IDs |
| `WHATSAPP_STATUS_TEMPLATE` | Actual approved template name for outside-window status updates; body must accept one positional text parameter |
| `WHATSAPP_TEMPLATE_LANGUAGE` | Exact language approved for that template, default `en_US` |
| `WHATSAPP_TEMPLATE_APPROVED` | Keep `false` until actual Meta approval; then `true` |
| `STORAGE_MODE` | `local` in development; use the existing `s3` configuration in production |
| `PRIVATE_STORAGE_ROOT` | Local private image storage, default `./.private` |
| `EXPO_PUBLIC_API_URL` | In `apps/farmer-mobile/.env`: `http://127.0.0.1:8000` for local web; a reachable trusted address for a physical phone |

For S3 storage retain `STORAGE_ENDPOINT`, `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY` and `STORAGE_SECRET_KEY`. Neon auth and production configuration remain as documented in `LIVE_SETUP.md` and `NEON_SETUP.md`. Gemini is not required for complaint registration; issue classification is deterministic.

## Exact Windows PowerShell startup commands

Install Python 3.12+ with `uv` and Node 22. On this workstation the portable Node directory can be added as follows. `npm.cmd` avoids the workstation's PowerShell script execution restriction.

```powershell
Set-Location 'C:\Users\aniru\.codex\hack-rogue-coders'
$env:Path = 'C:\Users\aniru\.codex\jalsathi-tools\node-v22.16.0-win-x64;' + $env:Path
uv sync --frozen
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
if (-not (Test-Path -LiteralPath 'apps\farmer-mobile\.env')) { Copy-Item -LiteralPath 'apps\farmer-mobile\.env.example' -Destination 'apps\farmer-mobile\.env' }
```

Edit the ignored environment files using the table above. Do not overwrite an existing signing key or database connection. Then:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
npm.cmd ci --ignore-scripts
```

Import real geography before the WhatsApp test if the selected database does not already contain it:

```powershell
.\.venv\Scripts\python.exe -m scripts.import_official_directory
```

Alternatively use the documented `scripts.manage import-villages` command with an official versioned CSV. A uniquely matching imported village and its real jurisdiction are necessary for routing. A Git checkout alone does not include the ignored application database.

Run each service in a separate PowerShell terminal, from the repository root. Add the portable Node directory to PATH in each frontend terminal if needed:

```powershell
# Terminal 1
.\.venv\Scripts\python.exe -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000
```

```powershell
# Terminal 2
.\.venv\Scripts\python.exe -m services.worker.main
```

```powershell
# Terminal 3
npm.cmd run admin
```

```powershell
# Terminal 4
npm.cmd run officials
```

```powershell
# Terminal 5: farmer web preview
npm.cmd run web -w @jalsathi/mobile -- --port 8081
```

Farmer web: `http://localhost:8081`; admin: `http://localhost:5173`; officials demo: `http://localhost:5174`; API docs: `http://127.0.0.1:8000/docs`. Restart API and worker after environment changes. The existing `run-local.ps1 -Build` is also available.

Provision staff using the actual imported village jurisdiction, replacing `YOUR_IMPORTED_JURISDICTION` before running; passwords are prompted:

```powershell
.\.venv\Scripts\python.exe -m scripts.manage create-user --email reviewer@example.org --role admin --jurisdictions YOUR_IMPORTED_JURISDICTION
.\.venv\Scripts\python.exe -m scripts.manage create-user --email official@example.org --role official --jurisdictions YOUR_IMPORTED_JURISDICTION
.\.venv\Scripts\python.exe -m scripts.manage create-user --email operator@example.org --role system_admin
```

## Meta Developer Dashboard configuration and authorised real test

These are manual account steps, not actions performed by this implementation. Meta's current setup page requires login and could not be inspected anonymously; wording such as **API Setup** versus **API Testing** may differ by app. Official references: [Meta WhatsApp get started](https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started) and [Meta's webhook setup reference](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/receivingMessages/). The latter is archived; this application uses direct Cloud API requests, not that archived SDK.

1. Sign in at Meta for Developers, open/create the intended business app and add the WhatsApp use case/product. Select Meta's test phone number in its API setup/testing screen.
2. Add your approved demo recipient under the test recipient selector and complete the verification challenge. Copy the test phone's **Phone number ID**, access token and supported API version to the corresponding server environment variables. Obtain the app secret from app Settings → Basic. Do not paste these values into chat or frontend configuration.
3. Generate a random webhook verification token locally and set `WHATSAPP_VERIFY_TOKEN`. Restart API and worker. Use an HTTPS reverse proxy/tunnel to the local API only when you are ready to configure the account; no tunnel was started here. If using an already installed and configured ngrok client, `ngrok http 8000` provides a development URL. Do not expose the app's development auth as a production service.
4. In the app's WhatsApp configuration/webhook screen, enter callback `https://YOUR_HTTPS_HOST/api/v1/webhooks/whatsapp` and the same verification token. Choose Verify and Save. The GET challenge handler returns Meta's challenge only for the matching token and subscribe mode.
5. Subscribe the WhatsApp Business Account webhook to the `messages` field. Ensure the intended app is subscribed to the selected WhatsApp Business Account, not merely that a sample webhook test works. This field delivers both inbound messages and delivery statuses to the existing callback.
6. Confirm `WHATSAPP_PHONE_NUMBER_ID` matches the callback metadata for the selected test sender. Set `WHATSAPP_APPROVED_RECIPIENTS` to only the approved demo recipient IDs. Leave `ALLOW_EXTERNAL_SEND=false` until the owner authorises the live test.
7. For outside-window status messages, create the intended template in WhatsApp Manager → Message templates. Its body must accept one positional text parameter containing the complaint update. Obtain real approval and configure its exact name and language. Set `WHATSAPP_TEMPLATE_APPROVED=true` only then. With no approved template, conduct the demo within the customer-initiated service window.
8. After explicit live-test authorisation, set `ALLOW_EXTERNAL_SEND=true`, restart the worker, and send `Hi` from the approved recipient's WhatsApp to the Meta test number. Observe the actual reply on that phone; a successful HTTP call alone is not delivery proof.
9. Send an issue such as `My soybean crop is drying due to insufficient irrigation water`, then a real imported `village, taluka, district`, inspect the summary, optionally send photo/GPS evidence, and send `YES`. Record the actual returned UUID reference. Do not invent a village, reference or successful delivery.
10. In the farmer app create/sign in to your account, open Tickets and generate a linking command. Send that command from the same WhatsApp, refresh Tickets and use **Find by reference ID**. Verify the same issue and UUID. A different farmer account or WhatsApp sender must be unable to retrieve it.
11. In Admin → Complaint inbox, filter `whatsapp`, open that reference, check location/evidence, enter a sanitised public description and reason, verify the matching jurisdiction, and accept it. Acceptance is the existing forwarding/publication mechanism; there is no separate invented Forwarded status.
12. In the officials demo, sign in with that jurisdiction and open Accepted complaints. Verify the same reference and details. Acknowledge, assign, progress and resolve using the existing action controls. Assignment records a lifecycle transition/note; the existing app does not implement a new priority or named-assignee system.
13. Send `SUBSCRIBE` before changing statuses to enable notifications. Verify actual WhatsApp updates on the phone, and refresh farmer/admin/official views to verify the shared database status and history. `UNSUBSCRIBE` must stop optional updates. Without opt-in, `STATUS <reference>` remains available on demand.
14. For photo evidence, verify a private attachment appears after its import job completes. Approve it through the existing admin evidence flow before expecting officials to see it.
15. Inspect Jobs & audit for blocked/dead jobs. A system administrator may retry one after fixing credentials, recipient approval, consent/window or storage configuration using the existing `POST /api/v1/admin/jobs/{job_id}/retry`. Never bypass the checks to make the demo look successful.
16. After the authorised test, restore `ALLOW_EXTERNAL_SEND=false` and restart the worker. Keep screenshots/reference IDs as manual test evidence; do not publish phone numbers, access tokens or message bodies.

## Tests and validation

Automated tests use isolated fixture databases and mocked Meta HTTP responses; no real messages were sent.

- Targeted final regression: **26 passed** across `test_whatsapp.py`, `test_workflow.py`, `test_security.py` and `test_completion.py`.
- Earlier full Python suite: **101 passed, 11 failed**. All 11 failures are in `tests/test_model.py` because ignored `artifacts/nwic-{research,residual,multiyear,seasonal}/evaluation.json` and associated model artifacts are absent in this checkout. They were not changed, fabricated or skipped. Four additional WhatsApp tests were added afterward and are included in the final targeted result.
- TypeScript typecheck: passed.
- Admin and officials Vite builds: passed.
- Expo farmer web export: passed.
- Existing browser workflow suite: **7 passed**, using isolated API fixtures and headless Chrome.
- Updated farmer complaint browser flow: **1 passed** after adding explicit linking-command and reference-search assertions.
- Fresh SQLite migration through `0002`: passed on a separate temporary database.
- `git diff --check`: passed.

The WhatsApp tests cover greeting/language, incomplete drafts, confirmed shared creation, genuine references, app and admin visibility, verified linking and ownership, reference tracking, admin acceptance/forwarding, official actions, status notifications, unsubscribe at dispatch, duplicate webhooks/worker retries, cancellation and multiple complaints, edits, natural location ambiguity, GPS validation, private image import, consent/window/templates/allowlist, transport retry without complaint loss, database rollback without success, transient failed receipts, expired linking codes and sender ordering.

Commands to reproduce:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_whatsapp.py tests/test_workflow.py tests/test_security.py tests/test_completion.py -q
.\.venv\Scripts\python.exe -m pytest -q
npm.cmd run typecheck
npm.cmd run build
npm.cmd run export -w @jalsathi/mobile
npx.cmd playwright test tests/browser/workflow.spec.ts
git diff --check
```

## Pending, blocked and limited behavior

- Real Meta account setup, secrets, test-recipient verification, public HTTPS callback, template approval and explicitly authorised delivery testing remain manual. No real delivery claim is made.
- Live PostgreSQL/Neon migration, worker concurrency and S3 storage have not been verified. Automated integration tests use SQLite and mocked Meta.
- Marathi responses work; directory matching uses the stored spelling. There is no transliteration, fuzzy geographic inference or external language-model extraction. Crop and growth stage are retained in the issue description rather than introducing a separate crop schema. Classification uses existing categories and simple keywords, not a diagnostic model.
- Long descriptions are retained in the database; summaries and outbound text are bounded to Meta's text length. The farmer can correct details before confirmation.
- Existing app/dashboard refresh loads the shared record; this work does not add real-time browser push.
- Retry is bounded to five job attempts. Transport errors retry through existing backoff. Explicit transient failed delivery receipts requeue eligible jobs; permanent receipt failures are stored for operator review. A crash after Meta accepts a message but before the worker commits its result can repeat an outbound message; inbound complaint creation remains deduplicated.
- Unknown media types are rejected conversationally. Images are limited to three JPEG/PNG files and 5 MiB each; voice transcription and arbitrary documents are not implemented. Draft photo IDs may expire at Meta before a delayed confirmation; failed imports require operator review or a fresh photo through the existing app.
- The officials portal remains the repository's government-workflow demonstration. No actual government system integration, new priority mechanism or named-official assignment service was created.
- Historical forecast artifact failures remain unrelated blockers for a fully green repository test suite. Installing locked Node dependencies reported 25 dependency vulnerabilities (1 low, 22 moderate, 2 high); dependency upgrades were outside this integration and were not applied.
