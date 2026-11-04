$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$python=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$cloudflared=Join-Path $PSScriptRoot 'work\tools\cloudflared.exe'
if(-not (Test-Path -LiteralPath $cloudflared)){throw 'Portable cloudflared is missing; see docs/WHATSAPP_TEST_READINESS.md.'}
$processFile=Join-Path $PSScriptRoot 'work\whatsapp-tunnel-processes.json'
if(Test-Path -LiteralPath $processFile){
    $previous=Get-Content -LiteralPath $processFile -Raw | ConvertFrom-Json
    foreach($entry in $previous){
        $owned=Get-Process -Id $entry.id -ErrorAction SilentlyContinue
        if($owned -and $owned.StartTime.ToUniversalTime().ToString('o') -eq $entry.started_at){
            throw 'A recorded gateway or tunnel is already running. Its callback is recorded in work/whatsapp-public.json.'
        }
    }
}
$gateway=Start-Process -FilePath $python -ArgumentList @('-m','scripts.whatsapp_gateway') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput 'work\whatsapp-gateway.log' -RedirectStandardError 'work\whatsapp-gateway-error.log'
$entries=@(@{name='webhook-gateway';id=$gateway.Id;started_at=$gateway.StartTime.ToUniversalTime().ToString('o')})
$entries | ConvertTo-Json | Set-Content -LiteralPath $processFile -Encoding UTF8
$tunnel=Start-Process -FilePath $cloudflared -ArgumentList @('tunnel','--url','http://127.0.0.1:8003','--no-autoupdate','--protocol','http2') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput 'work\whatsapp-tunnel.log' -RedirectStandardError 'work\whatsapp-tunnel-error.log'
$entries+=@{name='cloudflared';id=$tunnel.Id;started_at=$tunnel.StartTime.ToUniversalTime().ToString('o')}
$entries | ConvertTo-Json | Set-Content -LiteralPath $processFile -Encoding UTF8
Write-Output 'Webhook gateway and tunnel started. Run python -m scripts.verify_whatsapp_public after the tunnel connects.'
