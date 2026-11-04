[CmdletBinding(SupportsShouldProcess=$true,ConfirmImpact='Low')]
param([switch]$Build,[int]$ApiPort=8000,[int]$AdminPort=5173,[int]$OfficialsPort=5174,[int]$FarmerPort=8081)

$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$processFile=Join-Path $PSScriptRoot 'local-processes.json'
$pythonPath=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$verifiedTargets=@()
if(Test-Path -LiteralPath $processFile){
    $entries=Get-Content -LiteralPath $processFile -Raw | ConvertFrom-Json
    foreach($entry in $entries){
        if($entry.name -notin @('api','worker')){continue}
        $ownedProcess=Get-Process -Id ([int]$entry.id) -ErrorAction SilentlyContinue
        if(-not $ownedProcess){continue}
        # Validate every target before stopping any process. Saved PID alone
        # cannot prove ownership because Windows reuses process IDs.
        if(-not $entry.started_at -or $ownedProcess.StartTime.ToUniversalTime().ToString('o') -ne $entry.started_at -or $ownedProcess.Path -ne $pythonPath){
            throw ('Cannot verify ownership of saved '+$entry.name+' process. No processes were stopped.')
        }
        $verifiedTargets+=@{name=$entry.name;id=$ownedProcess.Id}
    }
}

foreach($target in $verifiedTargets){
    if($PSCmdlet.ShouldProcess(($target.name+' PID '+$target.id),'Stop owned JalSathi backend process tree')){
        # Windows virtual-environment Python starts a child interpreter. Stop
        # that owned tree as well, so the old server cannot retain its .env.
        & (Join-Path $env:SystemRoot 'System32\taskkill.exe') /PID $target.id /T /F
        if($LASTEXITCODE -ne 0){throw ('Could not stop '+$target.name+'. Startup was not attempted.')}
    }
}
if($PSCmdlet.ShouldProcess($PSScriptRoot,'Migrate and start local services using the current .env')){
    & (Join-Path $PSScriptRoot 'run-local.ps1') -Build:$Build -ApiPort $ApiPort -AdminPort $AdminPort -OfficialsPort $OfficialsPort -FarmerPort $FarmerPort
    if($LASTEXITCODE -ne 0){throw 'Local startup failed. Check the displayed migration or service error.'}
}
