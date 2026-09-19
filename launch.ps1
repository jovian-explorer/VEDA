# VEDA — Visualization, Exploration, and Data Analysis — launch script
# Usage:
#   .\launch.ps1             # starts VEDA and opens browser
#   .\launch.ps1 --no-window # server only
#   .\launch.ps1 -port 8765  # specific port

param(
    [switch]$browser,
    [switch]$nowindow,
    [int]$port = 0
)

$BackendDir = Join-Path $PSScriptRoot "backend"
$AppPy = Join-Path $BackendDir "app.py"

if (-not (Test-Path $AppPy)) {
    Write-Error "app.py not found at $AppPy"
    exit 1
}

# Build the argument list
$args = @()
if ($browser) { $args += "--browser" }
if ($nowindow) { $args += "--no-window" }
if ($port -ne 0) { $args += "--port", $port }

Write-Host "Starting VEDA — Planetary Science Data Laboratory..." -ForegroundColor Cyan
Write-Host "Backend: $BackendDir"

# Change to backend dir and launch
Set-Location $BackendDir
python app.py @args
