# Builds the self-contained Windows folder in dist\PS4ThemeTools.
#
#   powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1 -Clean -SkipTests
#
param(
    [switch]$Clean,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "No virtual environment found. Create it first:`n  python -m venv .venv`n  .venv\Scripts\python.exe -m pip install -r requirements-dev.txt"
}

Write-Host "Installing build requirements..." -ForegroundColor Cyan
& $Python -m pip install --disable-pip-version-check -q -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "pip failed" }

if (-not $SkipTests) {
    Write-Host "Running the test-suite..." -ForegroundColor Cyan
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Tests failed; fix them before building." }
}

if ($Clean) {
    Write-Host "Removing build\ and dist\..." -ForegroundColor Cyan
    Remove-Item -Recurse -Force "$Root\build", "$Root\dist" -ErrorAction SilentlyContinue
}

Write-Host "Running PyInstaller..." -ForegroundColor Cyan
& $Python -m PyInstaller --noconfirm --clean PS4ThemeTools.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$Exe = Join-Path $Root "dist\PS4ThemeTools\PS4ThemeTools.exe"
if (-not (Test-Path $Exe)) { throw "Build finished but $Exe is missing." }

Write-Host "Checking the packaged executable..." -ForegroundColor Cyan
$VersionRun = Start-Process -FilePath $Exe -ArgumentList "--version" -Wait -PassThru
if ($VersionRun.ExitCode -ne 0) { throw "The packaged exe cannot start (exit $($VersionRun.ExitCode))." }

$env:PS4THEME_SELFTEST_QUIET = "1"
$TestRun = Start-Process -FilePath $Exe -ArgumentList "--self-test", "--no-dialog" -Wait -PassThru
if ($TestRun.ExitCode -ne 0) { throw "The packaged exe failed its self test (exit $($TestRun.ExitCode))." }

$Size = [math]::Round(((Get-ChildItem "dist\PS4ThemeTools" -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
Write-Host ""
Write-Host "Build complete: $Exe ($Size MB folder)" -ForegroundColor Green
Write-Host "Run the exe, or zip the whole dist\PS4ThemeTools folder for distribution."
