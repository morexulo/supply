#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$ROOT_DIR"
PO="data/samples/po_sample.csv"
WH="data/warehouse/movimientos_almacen_fake.csv"
OUT="data/output/da/DA_demo.csv"
python -m src.core.da_build --po "$PO" --warehouse "$WH" --out "$OUT"
echo "Generado: $OUT"
