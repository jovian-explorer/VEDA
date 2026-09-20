# Update desktop shortcut for VEDA with explicit icon reference and proper paths
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
$ShortcutPath = Join-Path $DesktopPath "VEDA - Shortcut.lnk"

$VedaExe = "C:\Users\kesha\Desktop\VEDA\dist\VEDA.exe"
$VedaDistDir = "C:\Users\kesha\Desktop\VEDA\dist"
$VedaIco = "C:\Users\kesha\Desktop\VEDA\dist\veda.ico"

# Ensure dist\veda.ico exists
$BuildIco = "C:\Users\kesha\Desktop\VEDA\build\veda.ico"
if (-not (Test-Path $VedaIco) -and (Test-Path $BuildIco)) {
    Copy-Item $BuildIco $VedaIco -Force
    Write-Host "Copied $BuildIco to $VedaIco"
}

$Shortcuts = @(
    (Join-Path $DesktopPath "VEDA - Shortcut.lnk"),
    (Join-Path $VedaDistDir "VEDA - Shortcut.lnk")
)

foreach ($scPath in $Shortcuts) {
    if (Test-Path $scPath) {
        $Shortcut = $WshShell.CreateShortcut($scPath)
        $Shortcut.TargetPath = $VedaExe
        $Shortcut.WorkingDirectory = $VedaDistDir
        $Shortcut.IconLocation = "$VedaIco,0"
        $Shortcut.Description = "VEDA - Planetary Science Laboratory"
        $Shortcut.Save()
        Write-Host "Updated shortcut at $scPath -> $VedaIco" -ForegroundColor Green
    }
}

