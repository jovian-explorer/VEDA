# Flush and rebuild Windows Shell Icon Cache for Desktop and Explorer
Write-Host "Flushing Windows Shell Icon Cache..." -ForegroundColor Cyan

# 1. First ensure Desktop shortcut has explicit icon reference
$DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
$ShortcutPath = Join-Path $DesktopPath "VEDA - Shortcut.lnk"
$VedaIco = "C:\Users\kesha\Desktop\VEDA\dist\veda.ico"

if (-not (Test-Path $VedaIco)) {
    Copy-Item "C:\Users\kesha\Desktop\VEDA\build\veda.ico" $VedaIco -Force
}

$WshShell = New-Object -ComObject WScript.Shell
if (Test-Path $ShortcutPath) {
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = "C:\Users\kesha\Desktop\VEDA\dist\VEDA.exe"
    $Shortcut.WorkingDirectory = "C:\Users\kesha\Desktop\VEDA\dist"
    $Shortcut.IconLocation = "$VedaIco,0"
    $Shortcut.Save()
    Write-Host "Desktop shortcut icon location updated to $VedaIco" -ForegroundColor Green
}

# 2. Stop Windows Explorer
Write-Host "Stopping Explorer to release icon cache file locks..." -ForegroundColor Yellow
Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue

# Wait until all explorer processes have exited
$timeout = 10
while ((Get-Process -Name explorer -ErrorAction SilentlyContinue) -and ($timeout -gt 0)) {
    Start-Sleep -Milliseconds 500
    $timeout--
}

# 3. Purge icon cache files
$LocalAppData = $env:LOCALAPPDATA
$LegacyCache = Join-Path $LocalAppData "IconCache.db"
if (Test-Path $LegacyCache) {
    Remove-Item $LegacyCache -Force -ErrorAction SilentlyContinue
    Write-Host "Removed legacy IconCache.db" -ForegroundColor Green
}

$ExplorerCacheDir = Join-Path $LocalAppData "Microsoft\Windows\Explorer"
if (Test-Path $ExplorerCacheDir) {
    $files = Get-ChildItem -Path $ExplorerCacheDir -Filter "iconcache*.db" -File -ErrorAction SilentlyContinue
    foreach ($f in $files) {
        try {
            Remove-Item $f.FullName -Force -ErrorAction Stop
            Write-Host "Removed $($f.Name)" -ForegroundColor Green
        } catch {
            Write-Host "Could not remove $($f.Name) (still locked)" -ForegroundColor Yellow
        }
    }
}

# 4. Restart Windows Explorer
Write-Host "Starting Windows Explorer..." -ForegroundColor Green
Start-Process explorer.exe
Start-Sleep -Seconds 2

# 5. Notify Shell of icon updates
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public class ShellNotifyRefreshed {
    [DllImport("shell32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    public static extern void SHChangeNotify(uint wEventId, uint uFlags, IntPtr dwItem1, IntPtr dwItem2);
}
"@ -ErrorAction SilentlyContinue

try {
    [ShellNotifyRefreshed]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero) # SHCNE_ASSOCCHANGED
    Write-Host "SHChangeNotify sent." -ForegroundColor Green
} catch {}

Write-Host "Icon cache successfully refreshed!" -ForegroundColor Cyan
