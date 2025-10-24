from __future__ import annotations
import pandas as pd
from pathlib import Path

def write_excel(df: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)
