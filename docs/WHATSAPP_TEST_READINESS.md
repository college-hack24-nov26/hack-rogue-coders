# Real-test preparation — 4 November 2026

The existing integration is running from `C:\Users\aniru\.codex\hack-rogue-coders`.
Actual WhatsApp sending remains disabled. No real message delivery or Meta Dashboard subscription has been verified.
No credentials were printed, committed or pushed.

## Local configuration

Created ignored server configuration: `C:\Users\aniru\.codex\hack-rogue-coders\.env`.
Created ignored farmer public configuration: `apps/farmer-mobile/.env`.
Both were checked with `git check-ignore`; the server `.env` is not tracked.

The root environment template now lists every WhatsApp field with inactive placeholders. Configuration loading resolves the root `.env` by its absolute source location and reads UTF-8, independently of the launch directory. `REPLACE_WITH_` WhatsApp values become empty settings rather than usable credentials.

`scripts.prepare_whatsapp` preserves configured credentials, fills missing fields, generates missing random local signing and webhook verification tokens, and explicitly sets `ALLOW_EXTERNAL_SEND=false`. The generated local secrets are not Meta credentials. The helper does not overwrite an existing database connection. The new local database uses an absolute SQLite path.

## Values still needed

Open the root `.env` locally with an editor. Replace these placeholders; do not paste secret values into chat or a shared terminal:

| Variable | Where to get the actual value |
|---|---|
| `WHATSAPP_APP_SECRET` | Intended Meta developer app → Settings → Basic → App secret |
| `WHATSAPP_ACCESS_TOKEN` | Intended app → WhatsApp → API Setup / API Testing → access token for the selected test business number. Replace temporary tokens when they expire |
| `WHATSAPP_PHONE_NUMBER_ID` | Same WhatsApp setup screen → Phone number ID for Meta's test sender; this is not the displayed telephone number or business account ID |
| `WHATSAPP_API_VERSION` | Supported Graph API version shown by the selected app's sample request, including its `v` prefix |
| `WHATSAPP_APPROVED_RECIPIENTS` | The test recipient numbers added and verified in that WhatsApp setup screen; comma-separated digits with country code, no `+` |
| `WHATSAPP_STATUS_TEMPLATE` | Optional for the initial, customer-initiated demo; obtain an actually approved template name from WhatsApp Manager → Message templates for outside-window updates |

Already prepared locally:

- `WHATSAPP_VERIFY_TOKEN`: randomly generated. Copy its value directly from `.env` into Meta's webhook **Verify token** field. The values must match exactly. Its value is deliberately omitted here.
- `LOCAL_SIGNING_KEY`: randomly generated for existing local development auth.
- `DATABASE_URL`: the shared application database at `C:\Users\aniru\.codex\hack-rogue-coders\jalsathi.db`.
- `ALLOW_EXTERNAL_SEND=false`: must remain false until the owner explicitly approves a real-message test.
- `WHATSAPP_TEMPLATE_LANGUAGE=en_US`: change to the exact approved template language if using a template.
- `WHATSAPP_TEMPLATE_APPROVED=false`: change only after actual Meta approval; this setting is separate from permission to send.
- `ENVIRONMENT=development`, `AUTH_MODE=local`, `STORAGE_MODE=local`, `PRIVATE_STORAGE_ROOT=./.private`, local CORS origins and the farmer API address.

Neon auth, S3 storage and Gemini credentials are not required for this local WhatsApp demo. If those modes are selected later, retain their existing documented `NEON_AUTH_*`, `SESSION_ENCRYPTION_KEY`, `STORAGE_*` and `GEMINI_*` requirements in `.env.example`. There is no `WHATSAPP_WEBHOOK_URL` setting in the application: the callback is configured in Meta, while its route is fixed in the existing API. No app ID or business-account ID environment variable is required by this implementation.

## Services started and checked

The usual ports belonged to a different checkout. Those processes and that installation were left untouched. This checkout uses:

| Service | Address / verification |
|---|---|
| API | `http://127.0.0.1:8002`; `/health` and linking API schema checked |
| Farmer web | `http://127.0.0.1:8082`; HTTP 200 and compiled bundle confirmed to target API port 8002 |
| Admin | `http://127.0.0.1:5175`; HTTP 200. Set its login screen's API address to `http://127.0.0.1:8002` |
| Officials demo | `http://127.0.0.1:5176`; HTTP 200. Set its API address to `http://127.0.0.1:8002` |
| Worker | Running as the existing worker module; completed a durable job; restart tested |
| SQLite | Existing migrations applied successfully through `0002`; connection checked |
| Webhook-only gateway | `http://127.0.0.1:8003/api/v1/webhooks/whatsapp` forwards raw signed messages to the existing API |
| Public HTTPS tunnel | Running via portable Cloudflare Quick Tunnel |

The official directory importer loaded **44,929 villages across all 36 source districts** into this database, with source counts and identities validated. It did not fabricate test villages. The ignored import report is `work/whatsapp-directory-import.json`; source snapshots are under ignored `data/raw/lgd`.

Staff accounts have not been invented or provisioned. Create the intended admin/official accounts locally with the existing management command using real operator emails and the appropriate village jurisdiction before exercising staff workflows.

## Exact public callback

```text
https://efficiently-tours-liked-regulations.trycloudflare.com/api/v1/webhooks/whatsapp
```

Verified from the public HTTPS endpoint:

- Matching local verification token and challenge: HTTP 200 with exact challenge response.
- Unsigned webhook POST: HTTP 403.
- Non-webhook `/docs` route: HTTP 404.

This verifies public reachability and application challenge handling. It does **not** prove that Meta has saved/subscribed the callback, that the missing app credentials are valid, or that real WhatsApp messages have been delivered.

The temporary hostname remains usable while the local gateway/tunnel processes and this computer stay running. Restarting the tunnel changes the hostname; rerun the verifier and update Meta. Cloudflare describes this behavior in its [Quick Tunnels documentation](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

No tunnelling client was initially installed. A portable official `cloudflared` 2026.10.7 binary was downloaded under ignored `work/tools/cloudflared.exe`; its SHA-256 matched the digest published in the official GitHub release metadata. Only the webhook gateway is exposed. API and gateway access logs are disabled to keep GET verification tokens out of request logs. The gateway does not replace signature verification, complaint creation or the existing worker.

## Meta manual steps

1. Fill the missing Meta values in root `.env`, preserving the generated verification token and local signing key. Keep actual sending false.
2. Restart the owned local API and worker using the command below.
3. In the intended Meta app's WhatsApp configuration/webhook settings, enter the exact public callback above. In **Verify token**, enter the exact `WHATSAPP_VERIFY_TOKEN` value from local `.env`, then choose **Verify and Save**.
4. Subscribe to the WhatsApp Business Account `messages` field and ensure this app is subscribed to the intended business account. A sample dashboard webhook alone does not establish real inbound subscriptions.
5. Select Meta's test sender and verify the approved recipient numbers in API Setup / API Testing. Use those same digits for `WHATSAPP_APPROVED_RECIPIENTS`.
6. For an initial demo, the farmer's inbound message opens the customer-service reply window. Outside it, optional notifications also require recorded `SUBSCRIBE` consent and actual approved template configuration.
7. The owner must explicitly approve real sending before changing `ALLOW_EXTERNAL_SEND` to true and restarting the worker. Until then, incoming events may be processed, but real replies remain blocked.

Meta's current [setup documentation](https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started) requires login; exact screen labels may vary by account. No logged-in Meta Dashboard changes were made by the agent.

## Exact PowerShell commands

Services are currently running. Start them again after a machine restart:

```powershell
Set-Location 'C:\Users\aniru\.codex\hack-rogue-coders'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-whatsapp-test.ps1
```

Edit credentials locally, then reload the owned API and worker without stopping the other checkout:

```powershell
notepad.exe .env
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-whatsapp-test.ps1 -Restart
.\.venv\Scripts\python.exe -m scripts.whatsapp_readiness
```

For source or public API URL changes, add `-Build` to the startup command. The farmer export now clears Metro's cache: the earlier cached export ignored its changed `.env` until rebuilt with `--clear`.

If the tunnel processes have stopped, start the prepared gateway and tunnel. Do not launch duplicates while they are still running:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-whatsapp-tunnel.ps1
```

After it connects, run:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_whatsapp_public
```

This prints the callback URL and verification results without printing the token. The latest non-secret report is `work/whatsapp-public.json`. Tunnel process ownership is recorded under ignored `work/whatsapp-tunnel-processes.json`.

Rerun tests without sending real messages:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_whatsapp_setup.py tests/test_whatsapp.py tests/test_workflow.py tests/test_security.py tests/test_completion.py -q
```

Result during preparation: **29 passed**, including configuration preservation, inactive placeholders, raw gateway forwarding, confirmation-before-registration, shared database/dashboard flow, ownership, photos, consent, duplicate events and retries. Admin/official builds and the farmer export succeeded. The earlier missing forecast artifact failures are outside this WhatsApp preparation.

## Real complaint test after explicit sending approval

From an approved recipient's WhatsApp, send to the Meta test number:

```text
Hi
My soybean crop is drying because irrigation water is insufficient.
LGD:944593
YES
```

`944593` is the actual imported Phaltan record in Satara, jurisdiction `district:494`; use it only if it is your intended demo location. Some source taluka fields are codes rather than names, so an exact LGD code avoids spelling/code ambiguity.

Inspect the summary before `YES`. Record the actual returned complaint UUID, then send `STATUS <that UUID>`. Sign in to the farmer app, generate its **Link WhatsApp complaints** command, send that command from the same WhatsApp, refresh tickets and search the reference. In admin, filter `whatsapp`, review that same reference and accept it into the matching jurisdiction. The officials demo then sees the same record and can acknowledge, assign, progress and resolve. `SUBSCRIBE` enables optional status notifications; `UNSUBSCRIBE` stops them.

Provision staff accounts using intended email addresses and the actual jurisdiction. Commands prompt securely for passwords:

```powershell
$adminEmail = Read-Host 'Admin email'
$officialEmail = Read-Host 'Official email'
.\.venv\Scripts\python.exe -m scripts.manage create-user --email $adminEmail --role admin --jurisdictions district:494
.\.venv\Scripts\python.exe -m scripts.manage create-user --email $officialEmail --role official --jurisdictions district:494
```

These commands are for a Satara demo; choose the actual complaint's imported jurisdiction for another location. Government actions remain the existing demonstration workflow. No real government service integration or WhatsApp delivery is claimed.
