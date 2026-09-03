#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate

mkdir -p .cache/pip
PIP_CACHE_DIR="$PWD/.cache/pip" python -m pip install -r requirements.txt

./download_model.sh
