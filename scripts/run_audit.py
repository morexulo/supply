# scripts/run_da_audit.py
"""
Ejecuta la generación completa del Dispatch Advice (DA)
usando las rutas reales del entorno actual de Jaime.
"""

from __future__ import annotations
from pathlib import Path
from src.core.da_build import build_da

# --- rutas base ---
BASE = Path("data")

PO_FILE = BASE / "input" / "pos" / "PO_AirSupply.csv"
WAREHOUSE_FILE = BASE / "warehouse" / "Movimientos_Ventas_Albaran.xlsx"
MAP_FILE = BASE / "mappings" / "referencias_cruzadas_fake.csv"
OUT_DA = BASE / "output" / "da" / "DA_audit_demo.csv"

# --- ejecución ---
def main():
    print("=== Generación de Dispatch Advice (DA) ===")
    print(f"PO ..............: {PO_FILE}")
    print(f"Warehouse ........: {WAREHOUSE_FILE}")
    print(f"Mapping ..........: {MAP_FILE}")
    print(f"Salida ...........: {OUT_DA}")
    print("------------------------------------------")

    try:
        build_da(PO_FILE, WAREHOUSE_FILE, MAP_FILE, OUT_DA)
        print("\n✅ Proceso completado correctamente.")
        print(f"Archivo generado en: {OUT_DA.resolve()}")
    except Exception as e:
        print("\n❌ Error durante la ejecución del proceso:")
        print(e)
        raise

if __name__ == "__main__":
    main()
