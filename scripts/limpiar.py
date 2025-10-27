# limpiar.py
from __future__ import annotations
import pandas as pd
from pathlib import Path

SRC = Path("Vista - Movs. productos.xlsx")
SHEET = "Sheet1"
HEADER_ROW = 2
OUT_FULL_XLSX = Path("Movimientos_Almacen_Limpio.xlsx")
OUT_FULL_CSV  = Path("Movimientos_Almacen_Limpio.csv")
OUT_SALES_XLSX = Path("Movimientos_Ventas_Albaran.xlsx")
OUT_SALES_CSV  = Path("Movimientos_Ventas_Albaran.csv")

# columnas objetivo (se conservan si existen)
KEEP_COLS = [
    "Fecha registro","Tipo movimiento","Tipo documento","Nº documento","Nº producto","PN GECI",
    "Descripción","Fecha Fabricación","Fecha caducidad","Nº lote","Nº lote proveedor","Corrección",
    "Cód. almacén","Cantidad","Cantidad facturada","Cantidad pendiente",
    "Importe ventas (Real)","Importe coste (Esperado)","Importe coste (Real)","Source Currency Code",
    "Importe ventas (Esperado) (Div)","Importe ventas (Real)(Div)","Importe coste (Esperado) (Div)",
    "Importe coste (Real) (Div)","Reservado a cliente","Pendiente","Nº mov.","Especificación transacción",
    "Fecha pedido","Fecha ACK","Fecha Compromiso Proveedor","Fecha Envio Pedido","Fecha seguimiento",
    "Fecha Llegada Material","Observaciones","Cód. procedencia mov.","Nombre cliente"
]

def main():
    # Leer hoja y fijar cabecera real
    df = pd.read_excel(SRC, sheet_name=SHEET, header=HEADER_ROW)

    # Normalizar encabezados
    df.columns = [str(c).strip() for c in df.columns]

    # Eliminar columnas totalmente vacías
    df = df.dropna(axis=1, how="all")

    # Mantener solo columnas relevantes que existan
    keep = [c for c in KEEP_COLS if c in df.columns]
    if not keep:
        raise ValueError("No se encontraron columnas esperadas en la hoja 'Sheet1' con header=2.")
    df = df[keep]

    # Eliminar filas completamente vacías
    df = df.dropna(how="all")

    # Tipificar fechas principales si existen
    date_cols = [c for c in ["Fecha registro","Fecha Fabricación","Fecha caducidad",
                             "Fecha pedido","Fecha ACK","Fecha Compromiso Proveedor",
                             "Fecha Envio Pedido","Fecha seguimiento","Fecha Llegada Material"]
                 if c in df.columns]
    for c in date_cols:
        df[c] = pd.to_datetime(df[c], errors="coerce")

    # Guardar versión completa
    df.to_excel(OUT_FULL_XLSX, index=False)
    df.to_csv(OUT_FULL_CSV, index=False, encoding="utf-8-sig")

    # Filtrar solo movimientos de venta / albarán venta
    sales = df.copy()
    if "Tipo documento" in sales.columns:
        mask = sales["Tipo documento"].astype(str).str.contains("Albarán venta", case=False, na=False)
        sales = sales[mask]
    sales.to_excel(OUT_SALES_XLSX, index=False)
    sales.to_csv(OUT_SALES_CSV, index=False, encoding="utf-8-sig")

    # Resumen
    print(f"OK -> {OUT_FULL_XLSX} ({len(df)} filas)")
    print(f"OK -> {OUT_SALES_XLSX} ({len(sales)} filas) [solo Albarán venta]")

if __name__ == "__main__":
    main()
