$ErrorActionPreference = "Stop"

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    python -m pip install -r requirements.txt
}

pyinstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "PS4 Theme Tools" `
    --add-data "README.md;." `
    ps4_theme_tools.py

Write-Host "Built dist\PS4 Theme Tools\PS4 Theme Tools.exe"
