# Builds the NetVanta Windows app (dist\NetVanta\NetVanta.exe) and, if Inno Setup is installed,
# the installer (installer\Output\NetVanta-Setup-<version>.exe).
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) { python -m venv .venv }
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install -q -r requirements-dev.txt

Write-Host "== Running tests ==" -ForegroundColor Cyan
& $py -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed - build stopped." }

Write-Host "== Building NetVanta.exe ==" -ForegroundColor Cyan
& $py tools\make_icon.py
& $py -m PyInstaller --noconfirm --clean netvanta.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($iscc) {
    Write-Host "== Building installer ==" -ForegroundColor Cyan
    & $iscc installer\NetVanta.iss
    Write-Host "Installer: installer\Output" -ForegroundColor Green
} else {
    Write-Host "Inno Setup 6 not found - skipped the installer. App folder: dist\NetVanta" -ForegroundColor Yellow
}
