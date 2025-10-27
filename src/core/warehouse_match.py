# src/core/warehouse_match.py
from __future__ import annotations
from pathlib import Path
from typing import Iterable, Optional
import json
import pandas as pd

LOG_PATH = Path("data/state/da_log.json")

# --------- utilidades ---------
def _first_col(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None

def _ensure_datetime(s: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(s, dayfirst=True, errors="coerce")
    except Exception:
        return pd.to_datetime(pd.Series([], dtype="datetime64[ns]"))

def _log_event(event: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOG_PATH.exists():
        try:
            data = json.loads(LOG_PATH.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                data = []
        except json.JSONDecodeError:
            data = []
    else:
        data = []
    data.append(event)
    LOG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# --------- normalización ---------
def _normalize_po(po_df: pd.DataFrame) -> pd.DataFrame:
    po_df = po_df.copy()
    c_po = _first_col(po_df, ["PO", "PO Number", "PO_PoNumber"])
    c_item = _first_col(po_df, ["Item Number", "Customer Material Number", "Material Number"])
    c_qty = _first_col(po_df, ["Requested quantity", "Ordered Quantity", "Quantity"])
    if not all([c_po, c_item, c_qty]):
        _log_event({"level": "error", "where": "po", "msg": "Faltan columnas PO", "have": list(po_df.columns)})
        raise ValueError("PO: columnas requeridas no encontradas")
    out = pd.DataFrame({
        "po_number": po_df[c_po].astype(str).str.strip(),
        "item_as": po_df[c_item].astype(str).str.strip(),
        "qty_as": pd.to_numeric(po_df[c_qty], errors="coerce").fillna(0).astype(float)
    })
    return out

def _normalize_map(map_df: pd.DataFrame) -> pd.DataFrame:
    map_df = map_df.copy()
    c_item_as = _first_col(map_df, ["Codigo_SAP_ItemNumber", "Item_AS", "ItemNumber_AS"])
    c_item_nav = _first_col(map_df, ["Codigo_Navision", "Item_Nav", "ItemNumber_Nav"])
    c_desc = _first_col(map_df, ["Descripcion", "Description"])
    if not all([c_item_as, c_item_nav]):
        _log_event({"level": "warn", "where": "map", "msg": "Faltan columnas mapping mínimas", "have": list(map_df.columns)})
        raise ValueError("Mapping: columnas requeridas no encontradas")
    out = pd.DataFrame({
        "item_as": map_df[c_item_as].astype(str).str.strip(),
        "item_nav": map_df[c_item_nav].astype(str).str.strip(),
        "desc_nav": map_df[c_desc].astype(str).str.strip() if c_desc else ""
    })
    return out

def _normalize_wh(wh_df: pd.DataFrame) -> pd.DataFrame:
    wh_df = wh_df.copy()

    # nombres posibles vistos en tu Excel
    c_doc_type = _first_col(wh_df, ["Tipo documento", "Tipo documento ", "Tipo movimiento", "Tipo"])
    c_doc_no = _first_col(wh_df, ["Nº documento", "No documento", "Nº doc.", "Albarán"])
    c_item_nav = _first_col(wh_df, ["PN GECI", "Nº producto", "Producto", "Item"])
    c_lot = _first_col(wh_df, ["Nº lote", "Lote"])
    c_mfg = _first_col(wh_df, ["Fecha Fabricación", "Fecha fabricacion", "Fecha_Fabricacion"])
    c_exp = _first_col(wh_df, ["Fecha caducidad", "Fecha Caducidad", "Fecha_Caducidad"])
    c_qty = _first_col(wh_df, ["Cantidad", "Qty"])
    c_customer = _first_col(wh_df, ["Nombre cliente", "Cliente"])
    c_date = _first_col(wh_df, ["Fecha registro", "Fecha", "Posting Date"])

    required = [c_doc_type, c_doc_no, c_item_nav, c_lot, c_qty, c_date]
    if not all(required):
        _log_event({"level": "error", "where": "warehouse", "msg": "Faltan columnas warehouse", "have": list(wh_df.columns)})
        raise ValueError("Warehouse: columnas requeridas no encontradas")

    out = pd.DataFrame({
        "doc_type": wh_df[c_doc_type].astype(str).str.strip(),
        "albaran": wh_df[c_doc_no].astype(str).str.strip(),
        "item_nav": wh_df[c_item_nav].astype(str).str.strip(),
        "lot": wh_df[c_lot].astype(str).str.strip() if c_lot else "",
        "mfg_date": wh_df[c_mfg] if c_mfg else "",
        "exp_date": wh_df[c_exp] if c_exp else "",
        "qty_wh": pd.to_numeric(wh_df[c_qty], errors="coerce"),
        "customer": wh_df[c_customer].astype(str).str.strip() if c_customer else "",
        "move_date": _ensure_datetime(wh_df[c_date]),
    })

    # filtrar salidas de venta / albarán
    mask_sale = out["doc_type"].str.contains("Albarán venta", case=False, na=False) | out["doc_type"].str.contains("Venta", case=False, na=False)
    out = out.loc[mask_sale].reset_index(drop=True)

    return out

# --------- matching principal ---------
def match_po_to_warehouse(po_df: pd.DataFrame, map_df: pd.DataFrame, wh_df: pd.DataFrame) -> pd.DataFrame:
    """
    Devuelve filas listas para DA:
    PO, Item Number, Codigo_Navision, Shipped Quantity, Lot, Manufacture Date, Expiry Date, Albaran, Customer
    """
    po = _normalize_po(po_df)
    mp = _normalize_map(map_df)
    wh = _normalize_wh(wh_df)

    # PO + mapping
    merged = po.merge(mp, on="item_as", how="left", indicator=True)
    # log mapeos faltantes
    misses = merged.loc[merged["_merge"] == "left_only", ["po_number", "item_as"]]
    for _, r in misses.iterrows():
        _log_event({"level": "warn", "where": "mapping", "po": r["po_number"], "item_as": r["item_as"], "msg": "Código sin mapping"})
    merged = merged.drop(columns=["_merge"])

    # buscar en almacén por item_nav
    rows = []
    for _, r in merged.iterrows():
        po_num = r["po_number"]
        item_as = r["item_as"]
        qty_as = float(r["qty_as"])
        item_nav = str(r.get("item_nav", "")).strip()

        if not item_nav:
            rows.append({
                "PO": po_num, "Item Number": item_as, "Codigo_Navision": "",
                "Shipped Quantity": qty_as, "Lot": "", "Manufacture Date": "",
                "Expiry Date": "", "Albaran": "", "Customer": "", "match_status": "no_mapping"
            })
            continue

        hits = wh.loc[wh["item_nav"] == item_nav].copy()
        if hits.empty:
            _log_event({"level": "warn", "where": "warehouse", "po": po_num, "item_nav": item_nav, "msg": "Sin movimientos de venta"})
            rows.append({
                "PO": po_num, "Item Number": item_as, "Codigo_Navision": item_nav,
                "Shipped Quantity": qty_as, "Lot": "", "Manufacture Date": "",
                "Expiry Date": "", "Albaran": "", "Customer": "", "match_status": "no_match"
            })
            continue

        # elegir el movimiento más reciente
        hits = hits.sort_values(by=["move_date"], ascending=[False])
        best = hits.iloc[0]

        status = "ok"
        if pd.notna(best.get("qty_wh")) and abs(float(best["qty_wh"])) < qty_as:
            status = "qty_warning"

        rows.append({
            "PO": po_num,
            "Item Number": item_as,
            "Codigo_Navision": item_nav,
            "Shipped Quantity": qty_as,
            "Lot": best.get("lot", ""),
            "Manufacture Date": "" if pd.isna(best.get("mfg_date")) else str(best.get("mfg_date")),
            "Expiry Date": "" if pd.isna(best.get("exp_date")) else str(best.get("exp_date")),
            "Albaran": best.get("albaran", ""),
            "Customer": best.get("customer", ""),
            "match_status": status,
        })

        # log trazabilidad básica
        _log_event({
            "level": "info",
            "where": "match",
            "po": po_num,
            "item_as": item_as,
            "item_nav": item_nav,
            "picked_albaran": best.get("albaran", ""),
            "picked_lot": best.get("lot", ""),
            "move_date": str(best.get("move_date")),
            "qty_po": qty_as,
            "qty_wh": None if pd.isna(best.get("qty_wh")) else float(best.get("qty_wh")),
            "status": status
        })

    out_cols = [
        "PO", "Item Number", "Codigo_Navision", "Shipped Quantity",
        "Lot", "Manufacture Date", "Expiry Date", "Albaran", "Customer", "match_status"
    ]
    return pd.DataFrame(rows, columns=out_cols)



if __name__ == "__main__":
    import sys
    print("Running quick check...")
    try:
        po = pd.read_csv("data/input/PO_AirSupply.csv", sep=";", dtype=str)
        map_df = pd.read_csv("data/mappings/referencias_cruzadas_fake.csv", dtype=str)
        wh = pd.read_excel("data/warehouse/Movimientos_Ventas_Albaran.xlsx")
        res = match_po_to_warehouse(po, map_df, wh)
        print(res.head(10))
        print(f"\nTotal coincidencias: {len(res)}")
    except Exception as e:
        print("Error:", e)
        sys.exit(1)
