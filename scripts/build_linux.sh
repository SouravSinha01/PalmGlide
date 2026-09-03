#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

python3 -m pip install -r requirements.txt -r requirements-build.txt
./download_model.sh
python3 -m PyInstaller --clean --noconfirm PalmGlide.spec

echo "PalmGlide is ready at dist/PalmGlide/PalmGlide"
