# private-ride one-click launcher for Windows (local testing)
# Usage: right-click -> Run with PowerShell. Then open http://127.0.0.1:8000
$ErrorActionPreference = "Stop"

try { python --version | Out-Null } catch {
    Write-Host "Python not found. Install from https://www.python.org/downloads/ (check Add to PATH)"
    exit 1
}
try { git --version | Out-Null } catch {
    Write-Host "git not found. Install from https://git-scm.com/download/win"
    exit 1
}

$dir = "$env:USERPROFILE\private-ride"
if (Test-Path "$dir\.git") {
    Write-Host "[1/3] Updating code..."
    git -C $dir pull --quiet
} else {
    Write-Host "[1/3] Cloning code..."
    git clone --quiet https://github.com/hahahahahahahahah6/private-ride.git $dir
}

Write-Host "[2/3] Installing dependencies..."
if (-not (Test-Path "$dir\.venv")) { python -m venv "$dir\.venv" }
& "$dir\.venv\Scripts\python.exe" -m pip install -q -r "$dir\backend\requirements.txt"

Write-Host "[3/3] Starting server (dev mode: code shows on the web page)..."
$env:DEV_MODE = "1"
Write-Host ""
Write-Host "  Open http://127.0.0.1:8000 in your browser (passenger + driver pages)"
Write-Host "  Press Ctrl+C to stop"
& "$dir\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir "$dir\backend" --host 127.0.0.1 --port 8000
