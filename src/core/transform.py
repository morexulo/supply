from __future__ import annotations
import pandas as pd
from typing import Dict, List, Optional

# Columnas candidatas AirSupply → claves internas
AS_COLS: Dict[str, List[str]] = {
    "po_number": ["PO", "PO_PoNumber"],
    "item_number": ["Item Number", "Customer Material Number", "Material Number", "PO Line Desc."],
    "qty": ["Requested quantity", "Ordered Quantity"],
    "price_unit": ["Price Unit", "Net Price"],
    "currency": ["Currency"],
    "delivery_date": ["Promised date", "Requested date", "Delivery Date"],
}

def _first_existing(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None

def select_minimal_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols_map: Dict[str, Optional[str]] = {k: _first_existing(df, v) for k, v in AS_COLS.items()}
    missing = [k for k, v in cols_map.items() if v is None and k in ("po_number", "item_number", "qty", "price_unit", "currency")]
    if missing:
        raise ValueError(f"Faltan columnas clave en AirSupply: {missing}")

    out = pd.DataFrame()
    for key, col in cols_map.items():
        out[key] = df[col] if col else ""
    return out

def apply_mapping(min_df: pd.DataFrame, map_df: pd.DataFrame) -> pd.DataFrame:
    return min_df.merge(
        map_df,
        left_on="item_number",
        right_on="Codigo_SAP_ItemNumber",
        how="left",
    )

def build_navision_frame(merged: pd.DataFrame, fixed: dict, salida_cols: List[str]) -> pd.DataFrame:
    df = pd.DataFrame()

    # Fijos: forzar valor por fila
    df["Cliente"]      = pd.Series(fixed.get("cliente") or "",        index=merged.index)
    df["ID Contrato"]  = pd.Series(fixed.get("id_contrato") or "",    index=merged.index)
    df["Tipo"]         = pd.Series(fixed.get("tipo_documento") or "", index=merged.index)
    df["Cod. Almacén"] = pd.Series(fixed.get("codigo_almacen") or "", index=merged.index)

    # Variables
    df["Nº Ref. Cruzada"] = merged["item_number"]
    df["Código Navision"]  = merged["Codigo_Navision"].fillna("")
    df["Descripción"]      = merged["Descripcion"].fillna("")
    df["Cantidad"]         = merged["qty"]
    df["Precio Unitario"]  = merged["price_unit"]
    df["Divisa"]           = merged["currency"]
    df["Fecha Entrega"]    = merged["delivery_date"]

    return df.reindex(columns=salida_cols)

