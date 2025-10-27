#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------
# Bootstrap entorno para pruebas DA + UX/UE
# Uso:
#   cd scripts
#   chmod +x bootstrap_da_env.sh
#   ./bootstrap_da_env.sh
#
# Variables opcionales:
#   ARP_ID=154965 YEAR_PREFIX=26 ./bootstrap_da_env.sh
# ------------------------------------------------------------

ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$ROOT_DIR"

ARP_ID="${ARP_ID:-154965}"
YEAR_PREFIX="${YEAR_PREFIX:-26}"

echo "Root: $ROOT_DIR"
echo "ARP_ID=$ARP_ID  YEAR_PREFIX=$YEAR_PREFIX"

# Carpetas necesarias
mkdir -p data/{warehouse,state,output/da,output/labels,output/tmp,samples,audit}
mkdir -p data/mappings
mkdir -p config
mkdir -p src/{core,io}

# PO de ejemplo (AirSupply CSV ; separado por ;)
PO_PATH="data/samples/po_sample.csv"
if [ ! -f "$PO_PATH" ]; then
  cat > "$PO_PATH" <<'CSV'
"PO";"Item Number";"Requested quantity";"Price Unit";"Currency";"Requested date";"Customer Material Number"
"PO-0001";"NYCOTE7-11DARKBL_1PT";"10";"12.50";"EUR";"2025-11-03";"N/A"
"PO-0001";"ABC-123";"200";"0.15";"EUR";"2025-11-03";"N/A"
CSV
  echo "Creado: $PO_PATH"
else
  echo "Existe: $PO_PATH"
fi

# Mapping por defecto (coma)
MAP1="data/mappings/referencias_cruzadas_fake_actualizada.csv"
MAP2="data/mappings/referencias_cruzadas_fake.csv"
if [ ! -f "$MAP1" ] && [ ! -f "$MAP2" ]; then
  cat > "$MAP1" <<'CSV'
Codigo_SAP_ItemNumber,Codigo_Navision,Descripcion
NYCOTE7-11DARKBL_1PT,GE-001,Recubrimiento protector 1PT
ABC-123,GE-002,Tornillo M6x20 zincado
CSV
  echo "Creado: $MAP1"
else
  echo "Mapping ya presente en data/mappings/"
fi

# Movimientos de almacén de ejemplo
WH_PATH="data/warehouse/movimientos_almacen_fake.csv"
if [ ! -f "$WH_PATH" ]; then
  cat > "$WH_PATH" <<'CSV'
Albaran,PN_GECI,Lote,Fecha_Fabricacion,Fecha_Caducidad,Cantidad,Cliente
25-05973,NYCOTE7-11DARKBL_1PT,LOT-20251001,2025-10-01,2027-10-01,10,Airbus
25-05974,ABC-123,LOT-20250920,2025-09-20,2029-09-20,1000,Airbus
CSV
  echo "Creado: $WH_PATH"
else
  echo "Existe: $WH_PATH"
fi

# Estado de contadores UX/UE
COUNTERS="data/state/counters.json"
if [ ! -f "$COUNTERS" ]; then
  cat > "$COUNTERS" <<JSON
{
  "arp_id": "$ARP_ID",
  "year_prefix": "$YEAR_PREFIX",
  "UX": 0,
  "UE": 0
}
JSON
  echo "Creado: $COUNTERS"
else
  echo "Existe: $COUNTERS"
fi

# Config adicional para DA/SSCC (no toca tu config.yaml actual)
DA_CFG="config/config.da.yaml"
if [ ! -f "$DA_CFG" ]; then
  cat > "$DA_CFG" <<YAML
arp_id: "$ARP_ID"
sscc:
  year_prefix: "$YEAR_PREFIX"
  backend: "json"
  state_path: "data/state/counters.json"
label:
  symbology: "GS1-128"
  page: "A6"
  dpi: 300
da:
  template: "csv_airbus_like"
warehouse:
  default_path: "data/warehouse/movimientos_almacen_fake.csv"
YAML
  echo "Creado: $DA_CFG"
else
  echo "Existe: $DA_CFG"
fi

# Stubs de módulos a implementar (sin lógica, solo marcadores)
stub_py () {
  local path="$1"
  if [ ! -f "$path" ]; then
    mkdir -p "$(dirname "$path")"
    cat > "$path" <<'PY'
"""
Stub. Implementar:
- sscc.py: SSCC-18 (UX/UE), dígito control, validación.
- counters.py: persistencia contadores (JSON/SQLite).
- packing.py: PO -> UEs -> UX.
- da_build.py: dataset DA desde packing.
- labels.py: modelo etiquetas UX/UE.
- readers_warehouse.py: lectura movimientos almacén.
- writers_da.py: export CSV/XLSX Airbus-like.
- writers_labels.py: export etiquetas (PDF/PNG, GS1-128).
"""
PY
    echo "Creado: $path"
  else
    echo "Existe: $path"
  fi
}

stub_py "src/core/sscc.py"
stub_py "src/core/counters.py"
stub_py "src/core/packing.py"
stub_py "src/core/da_build.py"
stub_py "src/core/labels.py"
stub_py "src/io/readers_warehouse.py"
stub_py "src/io/writers_da.py"
stub_py "src/io/writers_labels.py"

echo "Listo. Revisa:"
echo " - data/samples/po_sample.csv"
echo " - data/mappings/*"
echo " - data/warehouse/movimientos_almacen_fake.csv"
echo " - data/state/counters.json  (ARP_ID=$ARP_ID, YEAR_PREFIX=$YEAR_PREFIX)"
echo " - config/config.da.yaml"
echo " - stubs en src/core y src/io"
