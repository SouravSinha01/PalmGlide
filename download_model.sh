#!/usr/bin/env bash
set -euo pipefail

mkdir -p models
curl -L \
  --output models/hand_landmarker.task \
  https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
