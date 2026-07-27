param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot ".runtime"
$python = @(
    (Join-Path $runtimeRoot "venv\Scripts\python.exe"),
    (Join-Path $projectRoot ".venv\Scripts\python.exe")
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$frontendRoot = Join-Path $projectRoot "frontend"
$stateFile = Join-Path $runtimeRoot "visiondesk-processes.json"
$logRoot = Join-Path $runtimeRoot "logs"

if ($null -eq $python) {
    throw "VisionDesk runtime is missing. Install the project dependencies first."
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot "node_modules"))) {
    throw "VisionDesk frontend dependencies are missing. Run npm install in frontend."
}

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$env:YOLO_CONFIG_DIR = Join-Path $runtimeRoot "ultralytics"
$env:MPLCONFIGDIR = Join-Path $runtimeRoot "matplotlib"

$backend = Start-Process `
    -FilePath $python `
    -ArgumentList "-m", "object_detection.web" `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logRoot "backend.stdout.log") `
    -RedirectStandardError (Join-Path $logRoot "backend.stderr.log") `
    -PassThru

$frontend = Start-Process `
    -FilePath "npm.cmd" `
    -ArgumentList "run", "dev:local" `
    -WorkingDirectory $frontendRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logRoot "frontend.stdout.log") `
    -RedirectStandardError (Join-Path $logRoot "frontend.stderr.log") `
    -PassThru

@{
    backend = @{
        id = $backend.Id
        started = $backend.StartTime.ToUniversalTime().Ticks
    }
    frontend = @{
        id = $frontend.Id
        started = $frontend.StartTime.ToUniversalTime().Ticks
    }
} | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $stateFile

function Wait-ForEndpoint {
    param(
        [string]$Uri,
        [int]$TimeoutSeconds = 120
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 750
        }
    }
    throw "VisionDesk did not become ready at $Uri."
}

try {
    Wait-ForEndpoint -Uri "http://127.0.0.1:8765/api/health"
    Wait-ForEndpoint -Uri "http://127.0.0.1:3000"
}
catch {
    & (Join-Path $projectRoot "stop_visiondesk.ps1") -Quiet
    throw
}

if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:3000"
}

Write-Output "VisionDesk is running at http://127.0.0.1:3000"
