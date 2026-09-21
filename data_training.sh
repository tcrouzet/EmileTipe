#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON_BIN=".venv/bin/python"
DATA_WORKERS="${DATA_WORKERS:-4}"
STEP="${1:-all}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Environnement Python absent. Lance d'abord : python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

build_manifest() {
  "$PYTHON_BIN" -m script.dataset.build --profile training manifest
}

download_curves() {
  "$PYTHON_BIN" -m script.dataset.build --profile training download \
    --fallback \
    --workers "$DATA_WORKERS"
}

case "$STEP" in
  all)
    build_manifest
    download_curves
    ;;
  manifest)
    build_manifest
    ;;
  download)
    download_curves
    ;;
  *)
    echo "Usage : ./data_training.sh [all|manifest|download]" >&2
    exit 2
    ;;
esac
