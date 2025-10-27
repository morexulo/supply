# scripts/format_da_official.py
from __future__ import annotations
import sys, glob
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

try:
    import yaml
except Exception:
    yaml = None

# Raíz del repo: /.../airsupply_navision_demo
BASE = Path(__file__).resolve().parents[1]
CFG_FILE = BASE / "config" / "config.da.yaml"
OUT_FILE = BASE / "data" / "output" / "da" / "DA_audit_official.csv"

OFFICIAL_COLUMNS = [
    "Supplier Number","Dispatch Advice ID","Despatch Date","Estimated Delivery Date",
    "Forwarder","Road","PO Number","PO Line","Customer","Material Number","Quantity",
    "Customs","Country of Origin","UX Number","UE Number","Lot","Manufacture Date","Expiry Date",
]

def _find_latest_da() -> Path:
    pattern = str(BASE / "data" / "output" / "da" / "*.csv")
    candidates = sorted(glob.glob(pattern))
    if not candidates:
        raise FileNotFoundError(f"No se encontró ningún CSV en {BASE/'data/output/da'}")
    return Path(candidates[-1])

def _load_config() -> dict:
    if CFG_FILE.exists() and yaml is not None:
        try:
            with CFG_FILE.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}
    return {}

def _fmt_date(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")

def main():
    in_file = _find_latest_da()
    print(f"Usando DA de entrada: {in_file.relative_to(BASE)}")

    df = pd.read_csv(in_file, dtype=str).fillna("")

    cfg = _load_config()
    supplier_number = (
        cfg.get("supplier_number")
        or cfg.get("supplier", {}).get("number")
        or "GECI-ESPAÑOLA"
    )
    country_origin = (
        cfg.get("country_of_origin")
        or cfg.get("supplier", {}).get("country")
        or "ES"
    )

    today = datetime.now()
    despatch_date = _fmt_date(today + timedelta(days=1))
    estimated_delivery = _fmt_date(today + timedelta(days=2))

    def get_col(name: str) -> pd.Series:
        return df[name] if name in df.columns else pd.Series([""] * len(df))

    df_out = pd.DataFrame()
    df_out["Supplier Number"] = supplier_number
    df_out["Dispatch Advice ID"] = get_col("Despatch Advice ID")
    df_out["Despatch Date"] = despatch_date
    df_out["Estimated Delivery Date"] = estimated_delivery
    df_out["Forwarder"] = ""
    df_out["Road"] = ""

    po_col = "PO" if "PO" in df.columns else ("PO Number" if "PO Number" in df.columns else "")
    df_out["PO Number"] = get_col(po_col)
    df_out["PO Line"] = "10"

    df_out["Customer"] = get_col("Customer")

    mat_series = get_col("Codigo_Navision") if "Codigo_Navision" in df.columns else get_col("Material Number")
    df_out["Material Number"] = mat_series
    qty_series = get_col("Shipped Quantity") if "Shipped Quantity" in df.columns else get_col("Quantity")
    df_out["Quantity"] = qty_series

    df_out["Customs"] = "No"
    df_out["Country of Origin"] = country_origin

    df_out["UX Number"] = get_col("UX_SSCC") if "UX_SSCC" in df.columns else get_col("UX Number")
    df_out["UE Number"] = get_col("UE_SSCC") if "UE_SSCC" in df.columns else get_col("UE Number")
    df_out["Lot"] = get_col("Lot")
    df_out["Manufacture Date"] = get_col("Manufacture Date")
    df_out["Expiry Date"] = get_col("Expiry Date")

    df_out = df_out.reindex(columns=OFFICIAL_COLUMNS)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(OUT_FILE, index=False, encoding="utf-8-sig")

    print(f"OK -> {OUT_FILE} ({len(df_out)} filas)")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
