$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python was not found. Install Python 3.12 from https://www.python.org/downloads/ and enable the Python launcher."
}

Write-Host "Creating the PalmGlide environment..."
py -3.12 -m venv .venv
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Write-Host "Installing dependencies..."
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt

if (-not (Test-Path "models/hand_landmarker.task")) {
    Write-Host "Downloading the hand-tracking model..."
    New-Item -ItemType Directory -Force "models" | Out-Null
    Invoke-WebRequest `
        -Uri "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task" `
        -OutFile "models/hand_landmarker.task"
}

Write-Host ""
Write-Host "PalmGlide is ready. Start it with:"
Write-Host ".\.venv\Scripts\python.exe .\palmglide.py"
