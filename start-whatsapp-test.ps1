param([switch]$Build,[switch]$Restart)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
# The default JalSathi ports belong to another checkout on this workstation.
# Keep this checkout's public farmer API config and CORS settings in sync with these ports.
$launcher=if($Restart){'restart-local.ps1'}else{'run-local.ps1'}
& (Join-Path $PSScriptRoot $launcher) -Build:$Build -ApiPort 8002 -AdminPort 5175 -OfficialsPort 5176 -FarmerPort 8082
