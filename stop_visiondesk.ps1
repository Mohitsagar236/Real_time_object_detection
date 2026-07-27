param(
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
$stateFile = Join-Path $PSScriptRoot ".runtime\visiondesk-processes.json"
if (-not (Test-Path -LiteralPath $stateFile)) {
    if (-not $Quiet) {
        Write-Output "VisionDesk is not running."
    }
    exit 0
}

$state = Get-Content -Raw -LiteralPath $stateFile | ConvertFrom-Json
foreach ($record in @($state.frontend, $state.backend)) {
    $process = Get-Process -Id $record.id -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        continue
    }

    $actualStarted = $process.StartTime.ToUniversalTime().Ticks
    if ($actualStarted -ne [long]$record.started) {
        continue
    }

    taskkill.exe /PID $process.Id /T /F | Out-Null
}

Remove-Item -LiteralPath $stateFile -Force
if (-not $Quiet) {
    Write-Output "VisionDesk stopped."
}
