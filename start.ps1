param([switch]$Install)
$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
if(-not (Get-Command node -ErrorAction SilentlyContinue)) {
    $portableNode='C:\Users\aniru\.codex\jalsathi-tools\node-v22.16.0-win-x64'
    if(Test-Path -LiteralPath "$portableNode\node.exe"){$env:PATH="$portableNode;"+$env:PATH}
}
if($Install){uv sync; if($LASTEXITCODE -ne 0){throw 'Python install failed'}; npm.cmd ci; if($LASTEXITCODE -ne 0){throw 'Node install failed'}}
if(-not (Test-Path -LiteralPath '.env')){throw 'Copy .env.example to .env and set a 32+ character LOCAL_SIGNING_KEY or configure Neon Auth first.'}
uv run alembic upgrade head
if($LASTEXITCODE -ne 0){throw 'Database migration failed'}
$api=Start-Process -FilePath 'uv' -ArgumentList @('run','uvicorn','services.api.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput 'api.log' -RedirectStandardError 'api-error.log'
$worker=Start-Process -FilePath 'uv' -ArgumentList @('run','python','-m','services.worker.main') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput 'worker.log' -RedirectStandardError 'worker-error.log'
Write-Output "API process: $($api.Id), worker process: $($worker.Id). API docs: http://127.0.0.1:8000/docs"
Write-Output 'Run npm run admin, npm run officials and npm run mobile in separate terminals.'
Write-Output 'To stop owned processes: Stop-Process -Id <reported process IDs> (include child Python processes if necessary).'
