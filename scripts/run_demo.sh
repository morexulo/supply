#!/usr/bin/env bash
set -euo pipefail
IN="${1:-data/input/PO_AirSupply.csv}"
MAP="${2:-data/mappings/referencias_cruzadas_fake.csv}"
OUT="${3:-data/output/OrdenVenta_Simulada.xlsx}"
CFG="${4:-config/config.yaml}"

python -m src.app.main --in "$IN" --map "$MAP" --out "$OUT" --cfg "$CFG"
