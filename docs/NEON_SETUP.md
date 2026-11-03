# Connect the JalSathi database to Neon

This configures PostgreSQL storage for the local application. Managed Neon Auth is a separate setup. A Neon management API key is not used by the current application.

Use a database dedicated to JalSathi. Switching `DATABASE_URL` does not copy accounts, farms, reports or village records from the existing SQLite database. The local `jalsathi.db` remains available. Sign out of the farmer app before switching databases.

1. Sign in at https://console.neon.tech and create a project named `jalsathi`, or open your existing dedicated JalSathi project. Choose a region close to your users.

2. Click **Connect**. Select the desired branch, database and database-owner role. Turn **Connection pooling off** to obtain a direct URL for the initial migrations. Copy only the PostgreSQL connection string, not a `psql` command. See [Neon's connection guide](https://neon.com/docs/get-started/connect-neon) and [pooling guidance](https://neon.com/docs/connect/connection-pooling).

3. Open `C:\Jalsathi\.env`. Replace the existing `DATABASE_URL` with the copied URL. Change its prefix from `postgresql://` to `postgresql+psycopg://`; preserve the username, password, hostname, database and all query parameters. For example, using placeholders only:

   ```dotenv
   DATABASE_URL="postgresql+psycopg://ROLE:PASSWORD@HOST/DATABASE?sslmode=require"
   ENVIRONMENT=development
   AUTH_MODE=local
   ```

   Preserve your existing `LOCAL_SIGNING_KEY` and other settings. Do not copy real credentials to `.env.example` or into chat. Keep `AUTH_MODE=local` for the existing development email/password flow while configuring database access.

4. Save `.env`, open PowerShell and prepare the schema:

   ```powershell
   Set-Location C:\Jalsathi
   .\.venv\Scripts\python.exe -m alembic upgrade head
   ```

   The project migration creates application tables and enables PostGIS. Use an owner role with extension/schema creation permission. [Neon PostGIS documentation](https://neon.com/docs/extensions/postgis)

5. Check the connection:

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.check_readiness --live
   ```

   In `docs/READINESS.json`, the `neon_database` provider's `probe.status` should be `database_and_postgis_verified`. Other unconfigured providers may still show missing settings; this does not mean the database check failed.

6. For a fresh database, import the official village directory:

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.import_official_directory
   ```

   Existing source checkpoints are reused after validation. This imports geography only; it does not transfer local accounts or reports. Retain SQLite until any desired data transfer has been separately reviewed.

7. Restart API and worker processes to load the new `.env`:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\restart-local.ps1
   ```

   The helper verifies saved process IDs, creation times and executable paths before stopping the owned API/worker trees. It starts services using the current environment. `-WhatIf` previews the process operations without stopping services or connecting to the database.

8. Open http://127.0.0.1:8081 and refresh with **Ctrl+F5**. A fresh database needs a new farmer account or a reviewed account transfer. Staff access must be provisioned separately. Changing the database URL does not enable managed Neon Auth, Gemini, storage or WhatsApp.
