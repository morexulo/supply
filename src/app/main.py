from __future__ import annotations
import argparse
import yaml
from pathlib import Path
from src.io.readers import read_airsupply_csv, read_mapping_csv
from src.io.writers import write_excel
from src.core.transform import select_minimal_columns, apply_mapping, build_navision_frame

def load_config(cfg_path: str | Path) -> dict:
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run(input_csv: str, mapping_csv: str, out_path: str, cfg_path: str) -> None:
    cfg = load_config(cfg_path)
    fixed = {
        "cliente": cfg["cliente"],
        "id_contrato": cfg["id_contrato"],
        "tipo_documento": cfg["tipo_documento"],
        "codigo_almacen": cfg["codigo_almacen"],
    }
    salida_cols = cfg["salida"]["columnas"]

    as_df = read_airsupply_csv(input_csv)
    min_df = select_minimal_columns(as_df)
    map_df = read_mapping_csv(mapping_csv)
    merged = apply_mapping(min_df, map_df)
    out_df = build_navision_frame(merged, fixed, salida_cols)
    write_excel(out_df, out_path)
    print(f"OK -> {out_path}")

def parse_args():
    p = argparse.ArgumentParser(description="AirSupply → Navision (Sales Order) demo")
    p.add_argument("--in", dest="input_csv", required=True, help="CSV AirSupply")
    p.add_argument("--map", dest="mapping_csv", required=True, help="CSV referencias SAP→Navision")
    p.add_argument("--out", dest="out_path", required=True, help="Ruta Excel de salida")
    p.add_argument("--cfg", dest="cfg_path", default="config/config.yaml", help="Ruta config.yaml")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    run(args.input_csv, args.mapping_csv, args.out_path, args.cfg_path)
