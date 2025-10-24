from __future__ import annotations
import pandas as pd
from pathlib import Path

def read_airsupply_csv(path: str | Path) -> pd.DataFrame:
    """
    Lee CSV AirSupply con separador ';' y comillas dobles.
    """
    return pd.read_csv(path, sep=";", quotechar='"', dtype=str).fillna("")

def read_mapping_csv(path: str | Path) -> pd.DataFrame:
    """
    Lee tabla de referencias SAP→Navision (CSV).
    """
    df = pd.read_csv(path, dtype=str).fillna("")
    expected = {"Codigo_SAP_ItemNumber","Codigo_Navision","Descripcion"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en mapping: {missing}")
    return df
