param(
    [string]$Project = "$env:TEMP\ps4theme-ui-demo",
    [string[]]$Pages = @("theme", "icons", "appearance", "build", "guide", "tools"),
    [string]$OutDir = "$env:TEMP\ps4theme-pages"
)

Add-Type -AssemblyName System.Drawing
if (-not ("Win32PageCap" -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class Win32PageCap {
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
'@
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$pythonw = Join-Path $PSScriptRoot "..\.venv\Scripts\pythonw.exe"
$app = Join-Path $PSScriptRoot "..\app.py"
$env:PS4THEME_CONFIG_DIR = "$env:TEMP\ps4theme-pages-config"

foreach ($page in $Pages) {
    $started = Get-Date
    $launcher = Start-Process -FilePath $pythonw -ArgumentList @($app, $Project, "--page", $page) -PassThru

    $deadline = (Get-Date).AddSeconds(25)
    $owner = $null
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 300
        $owner = Get-Process pythonw -ErrorAction SilentlyContinue |
            Where-Object { $_.MainWindowTitle -like "PS4 Theme Tools*" -and $_.StartTime -ge $started } |
            Select-Object -First 1
        if ($owner) { break }
    }

    if (-not $owner) {
        Write-Host "page=$page NO WINDOW"
        if (-not $launcher.HasExited) { $launcher.Kill() }
        continue
    }

    Start-Sleep -Milliseconds 1200
    $h = $owner.MainWindowHandle
    $r = New-Object Win32PageCap+RECT
    [Win32PageCap]::GetWindowRect($h, [ref]$r) | Out-Null
    $w = $r.Right - $r.Left; $ht = $r.Bottom - $r.Top
    $bmp = New-Object System.Drawing.Bitmap $w, $ht
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $hdc = $g.GetHdc()
    $ok = [Win32PageCap]::PrintWindow($h, $hdc, 2)
    $g.ReleaseHdc($hdc); $g.Dispose()
    $file = Join-Path $OutDir "$page.png"
    $bmp.Save($file, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Host "page=$page size=${w}x${ht} ok=$ok -> $file"

    if (-not $owner.HasExited) { $owner.Kill(); $owner.WaitForExit(5000) | Out-Null }
    if (-not $launcher.HasExited) { $launcher.Kill(); $launcher.WaitForExit(5000) | Out-Null }
}
