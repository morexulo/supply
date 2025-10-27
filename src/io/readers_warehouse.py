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
