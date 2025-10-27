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
