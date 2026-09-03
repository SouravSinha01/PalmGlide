$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

py -m pip install -r requirements.txt -r requirements-build.txt

if (-not (Test-Path "models/hand_landmarker.task")) {
    New-Item -ItemType Directory -Force "models" | Out-Null
    Invoke-WebRequest `
        -Uri "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task" `
        -OutFile "models/hand_landmarker.task"
}

py -m PyInstaller --clean --noconfirm PalmGlide.spec
Write-Host "PalmGlide is ready at dist/PalmGlide/PalmGlide.exe"
