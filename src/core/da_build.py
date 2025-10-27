# src/core/da_build.py
from __future__ import annotations
from pathlib import Path
import pandas as pd
from ..io.readers_warehouse import read_po_csv, read_mapping_csv
from ..io.writers_da import write_da
from .warehouse_match import match_po_to_warehouse

# --- compat: leer warehouse en .xlsx o .csv ---
def _read_warehouse_any(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(p)
    # CSV por defecto
    return pd.read_csv(p, dtype=str)

def _rows_from_matches(matches: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for _, r in matches.iterrows():
        rows.append({
            "PO": r.get("PO", ""),
            "Item Number": r.get("Item Number", ""),
            "Codigo_Navision": r.get("Codigo_Navision", ""),
            "Shipped Quantity": r.get("Shipped Quantity", ""),
            "Lot": r.get("Lot", ""),
            "Manufacture Date": r.get("Manufacture Date", ""),
            "Expiry Date": r.get("Expiry Date", ""),
            "UE_SSCC": "",  # se rellenará cuando packing esté listo
            "UX_SSCC": "",  # se rellenará cuando packing esté listo
            "Despatch Advice ID": r.get("Albaran", "") or f"DA-{r.get('PO','')}",
        })
    return rows

def _simple_pack(po_df: pd.DataFrame, wh_df: pd.DataFrame, map_df: pd.DataFrame | None) -> pd.DataFrame:
    """
    Fallback realista cuando no hay matching:
    - Si hay mapping: usa Codigo_Navision y deja SSCC vacíos.
    - Si NO hay mapping: genera Codigo_Navision sintético y SSCC reales (UE/UX).
    """
    # import local para evitar dependencias circulares
    from .sscc import next_ue, next_ux

    rows = []
    for _, r in po_df.iterrows():
        item = r.get("Item Number", "") or r.get("Customer Material Number", "") or ""
        # cantidad como float pero preservando salida amigable
        qty_raw = r.get("Requested quantity", "") or r.get("Ordered Quantity", "") or r.get("Quantity", "") or "0"
        try:
            qty_f = float(str(qty_raw).replace(",", "."))
        except Exception:
            qty_f = 0.0
        qty_out = qty_f if qty_f.is_integer() else qty_f  # se deja tal cual; Excel lo renderiza bien

        # datos del warehouse si existieran
        lot = fab = cad = alb = ""
        hit = wh_df.loc[wh_df["PN_GECI"] == item] if "PN_GECI" in wh_df.columns else None
        if hit is not None and not hit.empty:
            lot = hit.iloc[0].get("Lote", "")
            fab = hit.iloc[0].get("Fecha_Fabricacion", "")
            cad = hit.iloc[0].get("Fecha_Caducidad", "")
            alb = hit.iloc[0].get("Albaran", "")

        # mapping normal
        cod_nav = ""
        if map_df is not None and not map_df.empty and "Codigo_SAP_ItemNumber" in map_df.columns:
            m = map_df.loc[map_df["Codigo_SAP_ItemNumber"] == item]
            if not m.empty and "Codigo_Navision" in m.columns:
                cod_nav = str(m.iloc[0].get("Codigo_Navision", "")).strip()

        # si no existe mapping → generar uno ficticio y SSCC reales
        if not cod_nav:
            cod_nav = f"FAKE-{item}".strip("-")
            ue_sscc = next_ue()
            ux_sscc = next_ux()
        else:
            ue_sscc = ""
            ux_sscc = ""

        rows.append({
            "PO": r.get("PO", "") or r.get("PO Number", ""),
            "Item Number": item,
            "Codigo_Navision": cod_nav,
            "Shipped Quantity": qty_out,
            "Lot": lot,
            "Manufacture Date": fab,
            "Expiry Date": cad,
            "UE_SSCC": ue_sscc,
            "UX_SSCC": ux_sscc,
            "Despatch Advice ID": alb or f"DA-{(r.get('PO','') or r.get('PO Number',''))}",
        })

    return pd.DataFrame(rows)

def build_da(po_csv: str | Path, warehouse_path: str | Path, map_csv: str | None, out_path: str | Path) -> None:
    # Entradas
    po = read_po_csv(po_csv)
    wh = _read_warehouse_any(warehouse_path)

    # --- Soporte para mapping en Excel o CSV ---
    if map_csv:
        map_path = Path(map_csv)
        if map_path.suffix.lower() in [".xlsx", ".xls"]:
            mp = pd.read_excel(map_path, dtype=str).fillna("")
        else:
            mp = read_mapping_csv(map_path)
    else:
        mp = None
    # -------------------------------------------

    # Intentar matching real
    try:
        matches = match_po_to_warehouse(po, mp, wh)
        rows = _rows_from_matches(matches)
        df = pd.DataFrame(rows)
        # Si por cualquier motivo no hay filas útiles, usar fallback
        if df.empty:
            df = _simple_pack(po, wh, mp)
    except Exception:
        # Si falla matching, usar fallback
        df = _simple_pack(po, wh, mp)

    # Salida
    write_da(df, out_path)

def cli():
    import argparse
    p = argparse.ArgumentParser(description="Construir DA (demo Airbus-like)")
    p.add_argument("--po", required=True, help="CSV AirSupply (;)")
    p.add_argument("--warehouse", required=True, help="Ruta movimientos almacén (.xlsx o .csv)")
    p.add_argument("--map", required=False, help="CSV/XLSX mapping SAP->Navision")
    p.add_argument("--out", required=True, help="Ruta de salida .csv o .xlsx")
    args = p.parse_args()
    build_da(args.po, args.warehouse, args.map, args.out)

if __name__ == "__main__":
    cli()
