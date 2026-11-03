param([switch]$Install,[switch]$Build)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if(-not (Get-Command node -ErrorAction SilentlyContinue)) {
    $portableNode=Join-Path $env:USERPROFILE '.codex\jalsathi-tools\node-v22.16.0-win-x64'
    if(Test-Path -LiteralPath (Join-Path $portableNode 'node.exe')){$env:PATH=$portableNode+';'+$env:PATH}
}
if(-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    $portableUv=Join-Path $env:USERPROFILE '.local\bin'
    if(Test-Path -LiteralPath (Join-Path $portableUv 'uv.exe')){$env:PATH=$portableUv+';'+$env:PATH}
}
if($Install){
    uv sync
    if($LASTEXITCODE -ne 0){throw 'Python installation failed'}
    npm.cmd ci
    if($LASTEXITCODE -ne 0){throw 'Node installation failed'}
}
$pythonPath=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if(-not (Test-Path -LiteralPath $pythonPath)){throw 'Run .\run-local.ps1 -Install first.'}
if(-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.env'))){throw 'Create .env from .env.example and configure a local signing key or Neon Auth.'}
if(-not (Get-Command node -ErrorAction SilentlyContinue)){throw 'Install Node 22 LTS or put it on PATH.'}
$nodePath=(Get-Command node).Source
$vitePath=Join-Path $PSScriptRoot 'node_modules\vite\bin\vite.js'
if(-not (Test-Path -LiteralPath $vitePath)){throw 'Run .\run-local.ps1 -Install to install frontend dependencies.'}
if($Build -or -not (Test-Path -LiteralPath 'apps\admin-web\dist\index.html') -or -not (Test-Path -LiteralPath 'apps\officials-demo-web\dist\index.html')){
    npm.cmd run build
    if($LASTEXITCODE -ne 0){throw 'Portal build failed'}
}
if($Build -or -not (Test-Path -LiteralPath 'apps\farmer-mobile\dist\index.html')){
    npm.cmd run export -w '@jalsathi/mobile'
    if($LASTEXITCODE -ne 0){throw 'Farmer web export failed'}
}
& $pythonPath -m alembic upgrade head
if($LASTEXITCODE -ne 0){throw 'Database migration failed'}

function Test-LocalUrl([string]$Url) {
    try{$response=Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2;return $response.StatusCode -eq 200}catch{return $false}
}
$processFile=Join-Path $PSScriptRoot 'local-processes.json'
$startedProcesses=@()
if(Test-Path -LiteralPath $processFile){
    $previousEntries=Get-Content -LiteralPath $processFile -Raw | ConvertFrom-Json
    foreach($entry in $previousEntries){
        if(-not $entry.name -or -not $entry.started_at){continue}
        try{
            $ownedProcess=Get-Process -Id $entry.id -ErrorAction Stop
            if($ownedProcess.StartTime.ToUniversalTime().ToString('o') -eq $entry.started_at){$startedProcesses+=@{name=$entry.name;id=$entry.id;started_at=$entry.started_at;url=$entry.url}}
        }catch{}
    }
}
function Start-JalService([string]$Name,[string]$Executable,[string[]]$ServiceArguments,[string]$WorkingDirectory,[string]$ReadyUrl) {
    if($ReadyUrl -and (Test-LocalUrl $ReadyUrl)){Write-Output "$Name already responding: $ReadyUrl";return}
    if(@($script:startedProcesses | Where-Object {$_.name -eq $Name}).Count){Write-Output "$Name process already running";return}
    $serviceProcess=Start-Process -FilePath $Executable -ArgumentList $ServiceArguments -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $PSScriptRoot ($Name+'.log')) -RedirectStandardError (Join-Path $PSScriptRoot ($Name+'-error.log'))
    $script:startedProcesses+=@{name=$Name;id=$serviceProcess.Id;started_at=$serviceProcess.StartTime.ToUniversalTime().ToString('o');url=$ReadyUrl}
    $script:startedProcesses | ConvertTo-Json | Set-Content -LiteralPath $processFile -Encoding UTF8
}
Start-JalService 'api' $pythonPath @('-m','uvicorn','services.api.main:app','--host','127.0.0.1','--port','8000') $PSScriptRoot 'http://127.0.0.1:8000/health'
Start-JalService 'worker' $pythonPath @('-m','services.worker.main') $PSScriptRoot ''
Start-JalService 'admin' $nodePath @(('"'+$vitePath+'"'),'preview','--host','127.0.0.1','--port','5173','--strictPort') (Join-Path $PSScriptRoot 'apps\admin-web') 'http://127.0.0.1:5173'
Start-JalService 'officials' $nodePath @(('"'+$vitePath+'"'),'preview','--host','127.0.0.1','--port','5174','--strictPort') (Join-Path $PSScriptRoot 'apps\officials-demo-web') 'http://127.0.0.1:5174'
$farmerDirectory=Join-Path $PSScriptRoot 'apps\farmer-mobile\dist'
Start-JalService 'farmer' $pythonPath @('-m','http.server','8081','--bind','127.0.0.1','--directory',('"'+$farmerDirectory+'"')) $PSScriptRoot 'http://127.0.0.1:8081'
$localUrls=@('http://127.0.0.1:8000/health','http://127.0.0.1:5173','http://127.0.0.1:5174','http://127.0.0.1:8081')
$deadline=(Get-Date).AddSeconds(30)
do {
    $pendingUrls=@($localUrls | Where-Object {-not (Test-LocalUrl $_)})
    if($pendingUrls.Count -eq 0){break}
    Start-Sleep -Milliseconds 500
}while((Get-Date) -lt $deadline)
if($pendingUrls.Count){throw ('Services did not become ready: '+($pendingUrls -join ', ')+'. Check the corresponding *-error.log files.')}
Write-Output 'Farmer app: http://127.0.0.1:8081'
Write-Output 'Admin: http://127.0.0.1:5173'
Write-Output 'Officials demo: http://127.0.0.1:5174'
Write-Output 'API documentation: http://127.0.0.1:8000/docs'
Write-Output 'Services keep running after this command exits. Their owned process IDs are in local-processes.json.'
