#!/usr/bin/env bash
set -euo pipefail

# Instalador simple y compatible con Git Bash.
# Uso:
#   cd scripts
#   chmod +x install_da_stack.sh
#   ./install_da_stack.sh           # mínimo
#   ./install_da_stack.sh --full    # packing + CLI
#   ./install_da_stack.sh --labels  # añade placeholders de etiquetas

ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$ROOT_DIR"

FULL=0
LABELS=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --full) FULL=1; shift;;
    --labels) LABELS=1; FULL=1; shift;;
    *) echo "Flag desconocida: $1"; exit 1;;
  esac
done

echo "Root: $ROOT_DIR"
mkdir -p src/core src/io scripts data/output/da data/output/labels

# 1) src/core/counters.py
cat > "src/core/counters.py" <<'PY'
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any

DEFAULT_STATE: Dict[str, Any] = {"arp_id": "", "year_prefix": "26", "UX": 0, "UE": 0}

def _ensure_state(path: Path) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_STATE, ensure_ascii=False, indent=2), encoding="utf-8")
        return DEFAULT_STATE.copy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {}
    for k, v in DEFAULT_STATE.items():
        data.setdefault(k, v)
    return data

def load_state(path: str | Path) -> Dict[str, Any]:
    return _ensure_state(Path(path))

def save_state(state: Dict[str, Any], path: str | Path) -> None:
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

def next_value(kind: str, path: str | Path) -> int:
    if kind not in ("UX", "UE"):
        raise ValueError("kind debe ser 'UX' o 'UE'")
    st = load_state(path)
    st[kind] = int(st.get(kind, 0)) + 1
    save_state(st, path)
    return st[kind]
PY
echo "Escrito: src/core/counters.py"

# 2) src/core/sscc.py
cat > "src/core/sscc.py" <<'PY'
from __future__ import annotations
from pathlib import Path
import yaml
from .counters import next_value

CFG_DEF = "config/config.da.yaml"

def load_cfg(cfg_path: str | Path = CFG_DEF) -> dict:
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def calc_check_digit(base17: str) -> int:
    digits = [int(c) for c in base17 if c.isdigit()]
    if len(digits) != 17:
        raise ValueError("base17 debe tener 17 dígitos")
    total = 0
    for i, d in enumerate(reversed(digits), start=1):
        w = 3 if i % 2 == 1 else 1
        total += d * w
    return (10 - (total % 10)) % 10

def _seq_block(year_prefix: str, seq: int) -> str:
    yp = "".join(ch for ch in str(year_prefix) if ch.isdigit())
    if len(yp) > 10:
        raise ValueError("year_prefix demasiado largo")
    width = 10 - len(yp)
    if seq < 0 or seq >= 10**width:
        raise ValueError("seq fuera de rango para el prefix dado")
    return f"{yp}{seq:0{width}d}"

def make_sscc(arp_id: str, seq: int, year_prefix: str) -> str:
    if not (arp_id and arp_id.isdigit() and len(arp_id) == 6):
        raise ValueError("arp_id debe ser 6 dígitos")
    block = _seq_block(year_prefix, seq)
    base17 = f"0{arp_id}{block}"
    cd = calc_check_digit(base17)
    return base17 + str(cd)

def next_ux(cfg_path: str | Path = CFG_DEF) -> str:
    cfg = load_cfg(cfg_path)
    st_path = cfg["sscc"]["state_path"]
    arp_id = cfg["arp_id"]
    ypref = cfg["sscc"]["year_prefix"]
    seq = next_value("UX", st_path)
    return make_sscc(arp_id, seq, ypref)

def next_ue(cfg_path: str | Path = CFG_DEF) -> str:
    cfg = load_cfg(cfg_path)
    st_path = cfg["sscc"]["state_path"]
    arp_id = cfg["arp_id"]
    ypref = cfg["sscc"]["year_prefix"]
    seq = next_value("UE", st_path)
    return make_sscc(arp_id, seq, ypref)

if __name__ == "__main__":
    print("UX:", next_ux())
    print("UE:", next_ue())
PY
echo "Escrito: src/core/sscc.py"

# 3) src/io/readers_warehouse.py
cat > "src/io/readers_warehouse.py" <<'PY'
from __future__ import annotations
from pathlib import Path
import pandas as pd

def read_po_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", quotechar='"', dtype=str).fillna("")

def read_mapping_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str).fillna("")
    needed = {"Codigo_SAP_ItemNumber", "Codigo_Navision"}
    miss = needed - set(df.columns)
    if miss:
        raise ValueError(f"Faltan columnas en mapping: {miss}")
    return df

def read_warehouse_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")
PY
echo "Escrito: src/io/readers_warehouse.py"

# 4) src/io/writers_da.py
cat > "src/io/writers_da.py" <<'PY'
from __future__ import annotations
from pathlib import Path
import pandas as pd

def write_da(df: pd.DataFrame, out_path: str | Path) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() in (".xlsx", ".xlsm", ".xltx", ".xltm"):
        with pd.ExcelWriter(out, engine="openpyxl") as wr:
            df.to_excel(wr, index=False)
    else:
        df.to_csv(out, index=False)
PY
echo "Escrito: src/io/writers_da.py"

# 5) src/core/da_build.py
cat > "src/core/da_build.py" <<'PY'
from __future__ import annotations
from pathlib import Path
import pandas as pd
from ..io.readers_warehouse import read_po_csv, read_mapping_csv, read_warehouse_csv
from ..io.writers_da import write_da

def _simple_pack(po_df: pd.DataFrame, wh_df: pd.DataFrame, map_df: pd.DataFrame | None):
    rows = []
    for _, r in po_df.iterrows():
        item = r.get("Item Number", "")
        qty = r.get("Requested quantity", "0")
        lot = fab = cad = alb = ""
        hit = wh_df.loc[wh_df["PN_GECI"] == item] if "PN_GECI" in wh_df.columns else None
        if hit is not None and not hit.empty:
            lot = hit.iloc[0].get("Lote", "")
            fab = hit.iloc[0].get("Fecha_Fabricacion", "")
            cad = hit.iloc[0].get("Fecha_Caducidad", "")
            alb = hit.iloc[0].get("Albaran", "")
        cod_nav = ""
        if map_df is not None and not map_df.empty:
            m = map_df.loc[map_df["Codigo_SAP_ItemNumber"] == item]
            if not m.empty:
                cod_nav = m.iloc[0]["Codigo_Navision"]
        rows.append({
            "PO": r.get("PO",""),
            "Item Number": item,
            "Codigo_Navision": cod_nav,
            "Shipped Quantity": qty,
            "Lot": lot,
            "Manufacture Date": fab,
            "Expiry Date": cad,
            "UE_SSCC": "",
            "UX_SSCC": "",
            "Despatch Advice ID": alb or f"DA-{r.get('PO','')}",
        })
    return pd.DataFrame(rows)

def build_da(po_csv: str | Path, warehouse_csv: str | Path, map_csv: str | None, out_path: str | Path) -> None:
    po = read_po_csv(po_csv)
    wh = read_warehouse_csv(warehouse_csv)
    mp = read_mapping_csv(map_csv) if map_csv else None
    try:
        from .packing import plan_packing
        ues, uxs = plan_packing(po, wh, mp)
        ux_sscc = uxs[0]["sscc"] if uxs else ""
        rows = []
        for ue in ues:
            rows.append({
                "PO": po.iloc[0].get("PO",""),
                "Item Number": ue["item_as"],
                "Codigo_Navision": ue["codigo_navision"],
                "Shipped Quantity": ue["qty"],
                "Lot": ue["lote"],
                "Manufacture Date": ue["mfg_date"],
                "Expiry Date": ue["exp_date"],
                "UE_SSCC": ue["sscc"],
                "UX_SSCC": ux_sscc,
                "Despatch Advice ID": ue["albaran"] or f"DA-{po.iloc[0].get('PO','')}",
            })
        df = pd.DataFrame(rows)
    except Exception:
        df = _simple_pack(po, wh, mp)
    write_da(df, out_path)

def cli():
    import argparse
    p = argparse.ArgumentParser(description="Construir DA (demo Airbus-like)")
    p.add_argument("--po", required=True, help="CSV AirSupply (;)")
    p.add_argument("--warehouse", required=True, help="CSV movimientos almacén")
    p.add_argument("--map", required=False, help="CSV mapping SAP->Navision")
    p.add_argument("--out", required=True, help="Ruta de salida .csv o .xlsx")
    args = p.parse_args()
    build_da(args.po, args.warehouse, args.map, args.out)

if __name__ == "__main__":
    cli()
PY
echo "Escrito: src/core/da_build.py"

# 6) packing opcional (--full)
if [[ "$FULL" -eq 1 ]]; then
  cat > "src/core/packing.py" <<'PY'
from __future__ import annotations
from typing import Any, Dict, List, Tuple
import pandas as pd
from ..io.readers_warehouse import read_po_csv, read_mapping_csv, read_warehouse_csv
from .sscc import next_ue, next_ux

UE = Dict[str, Any]
UX = Dict[str, Any]

def plan_packing(po_df: pd.DataFrame, wh_df: pd.DataFrame, map_df: pd.DataFrame | None = None) -> Tuple[List[UE], List[UX]]:
    ues: List[UE] = []
    ux: UX = {"sscc": next_ux(), "ues": [], "n_ue": 0}
    wh_idx = {}
    if "PN_GECI" in wh_df.columns:
        for _, r in wh_df.iterrows():
            wh_idx.setdefault(r["PN_GECI"], []).append(r.to_dict())

    for _, row in po_df.iterrows():
        item = row.get("Item Number", "")
        qty_str = row.get("Requested quantity", "0")
        try:
            qty_num = int(float(qty_str))
        except Exception:
            qty_num = 0

        cod_nav = ""
        if map_df is not None and not map_df.empty:
            hit = map_df.loc[map_df["Codigo_SAP_ItemNumber"] == item]
            if not hit.empty:
                cod_nav = hit.iloc[0]["Codigo_Navision"]

        wh_rows = wh_idx.get(item, [])
        lote = wh_rows[0]["Lote"] if wh_rows else ""
        fab = wh_rows[0]["Fecha_Fabricacion"] if wh_rows else ""
        cad = wh_rows[0]["Fecha_Caducidad"] if wh_rows else ""
        albaran = wh_rows[0]["Albaran"] if wh_rows else ""

        ue: UE = {
            "sscc": next_ue(),
            "item_as": item,
            "codigo_navision": cod_nav,
            "qty": qty_num,
            "uom": row.get("UOM", ""),
            "lote": lote,
            "mfg_date": fab,
            "exp_date": cad,
            "albaran": albaran,
        }
        ues.append(ue)
        ux["ues"].append(ue["sscc"])

    ux["n_ue"] = len(ux["ues"])
    return ues, [ux]

def cli():
    import argparse, json, sys
    p = argparse.ArgumentParser(description="Packing demo: PO -> UE/UX")
    p.add_argument("--po", required=True)
    p.add_argument("--warehouse", required=True)
    p.add_argument("--map", required=False)
    args = p.parse_args()

    po = read_po_csv(args.po)
    wh = read_warehouse_csv(args.warehouse)
    mp = read_mapping_csv(args.map) if args.map else None
    ues, uxs = plan_packing(po, wh, mp)
    sys.stdout.write(json.dumps({"UX": uxs, "UE": ues}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    cli()
PY
  echo "Escrito: src/core/packing.py"
fi

# 7) labels placeholders si --labels
if [[ "$LABELS" -eq 1 ]]; then
  cat > "src/core/labels.py" <<'PY'
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class UXLabel:
    sscc: str
    despatch_advice_id: str = ""
    number_of_ue: int = 0

@dataclass
class UELabel:
    sscc: str
    quantity: str = ""
    uom: str = ""
    serials: str = ""
PY
  echo "Escrito: src/core/labels.py"

  cat > "src/io/writers_labels.py" <<'PY'
from __future__ import annotations
from pathlib import Path

def export_labels_stub(out_dir: str | Path, ux_labels: list, ue_labels: list) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for i, ux in enumerate(ux_labels, 1):
        (out / f"UX_{i}_{ux.sscc}.txt").write_text(
            f"UX SSCC: {ux.sscc}\nUE count: {ux.number_of_ue}\nDA: {ux.despatch_advice_id}\n",
            encoding="utf-8"
        )
    for i, ue in enumerate(ue_labels, 1):
        (out / f"UE_{i}_{ue.sscc}.txt").write_text(
            f"UE SSCC: {ue.sscc}\nQty: {ue.quantity} {ue.uom}\n",
            encoding="utf-8"
        )
PY
  echo "Escrito: src/io/writers_labels.py"

  # añadir deps opcionales
  if ! grep -qiE 'reportlab|python-barcode' requirements.txt 2>/dev/null; then
    printf "\nreportlab\npython-barcode\n" >> requirements.txt || true
    echo "Añadido reportlab y python-barcode a requirements.txt"
  fi
fi

# 8) Script de demo para generar DA
cat > "scripts/run_da_demo.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$ROOT_DIR"
PO="data/samples/po_sample.csv"
WH="data/warehouse/movimientos_almacen_fake.csv"
OUT="data/output/da/DA_demo.csv"
python -m src.core.da_build --po "$PO" --warehouse "$WH" --out "$OUT"
echo "Generado: $OUT"
SH
chmod +x "scripts/run_da_demo.sh"
echo "Escrito: scripts/run_da_demo.sh"

echo
echo "OK. Pruebas:"
echo "  1) SSCC UX/UE ->  python -m src.core.sscc"
if [[ "$FULL" -eq 1 ]]; then
  echo "  2) Packing JSON -> python -m src.core.packing --po data/samples/po_sample.csv --warehouse data/warehouse/movimientos_almacen_fake.csv"
fi
echo "  3) DA demo -> scripts/run_da_demo.sh"
