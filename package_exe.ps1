# VEDA Standalone Executable Packaging Script (.exe)
# Builds standalone Windows desktop binary VEDA.exe with embedded assets & icon.

param(
    [switch]$clean
)

$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot
Set-Location $ProjectDir

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Building VEDA Standalone Executable (.exe)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$DistDir = Join-Path $ProjectDir "dist"
$BuildDir = Join-Path $ProjectDir "build"
$SpecFile = Join-Path $BuildDir "veda.spec"

if (-not (Test-Path $SpecFile)) {
    Write-Error "Spec file not found at: $SpecFile"
    exit 1
}

# Optional Clean
if ($clean) {
    Write-Host "Cleaning previous build artifacts..." -ForegroundColor Yellow
    if (Test-Path $DistDir) { Remove-Item -Path $DistDir -Recurse -Force }
    $WorkDir = Join-Path $BuildDir "pyinstaller_work"
    if (Test-Path $WorkDir) { Remove-Item -Path $WorkDir -Recurse -Force }
}

# Run PyInstaller
Write-Host "Invoking PyInstaller with $SpecFile..." -ForegroundColor Green
Set-Location $BuildDir
python -m PyInstaller --distpath "$DistDir" --workpath "$BuildDir\pyinstaller_work" --noconfirm veda.spec

Set-Location $ProjectDir
$ExePath = Join-Path $DistDir "VEDA.exe"

if (Test-Path $ExePath) {
    $item = Get-Item $ExePath
    $sizeMb = [math]::Round($item.Length / 1MB, 2)
    Write-Host "========================================================" -ForegroundColor Green
    Write-Host "  SUCCESS: VEDA.exe created successfully!" -ForegroundColor Green
    Write-Host "  Executable : $ExePath" -ForegroundColor White
    Write-Host "  Size       : $sizeMb MB" -ForegroundColor White
    Write-Host "========================================================" -ForegroundColor Green
} else {
    Write-Error "VEDA.exe was not created in $DistDir"
    exit 1
}
