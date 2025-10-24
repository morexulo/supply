from __future__ import annotations
import io, os, sys
from pathlib import Path
import pandas as pd
import streamlit as st
import yaml

# Asegurar import de src/ aunque se ejecute desde distintos cwd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.core.transform import select_minimal_columns, apply_mapping, build_navision_frame

st.set_page_config(page_title="AirSupply → Navision | Demo", layout="wide")

# --- Utilidades ---
def load_config(cfg_path: str | Path) -> dict:
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def read_airsupply_like(file) -> pd.DataFrame:
    return pd.read_csv(file, sep=";", quotechar='"', dtype=str).fillna("")

def read_mapping_like(file) -> pd.DataFrame:
    df = pd.read_csv(file, dtype=str).fillna("")
    needed = {"Codigo_SAP_ItemNumber", "Codigo_Navision", "Descripcion"}
    miss = needed - set(df.columns)
    if miss:
        raise ValueError(f"Faltan columnas en mapping: {miss}")
    return df

# --- Sidebar: Config ---
st.sidebar.header("Configuración")
cfg_path = "config/config.yaml"
cfg = load_config(cfg_path)
with st.sidebar.expander("Valores fijos (solo lectura)", expanded=True):
    st.write(f"**Cliente:** {cfg.get('cliente','')}")
    st.write(f"**ID Contrato:** {cfg.get('id_contrato','')}")
    st.write(f"**Tipo:** {cfg.get('tipo_documento','')}")
    st.write(f"**Almacén:** {cfg.get('codigo_almacen','')}")

salida_cols = cfg["salida"]["columnas"]

# --- Inputs ---
st.title("AirSupply → Navision (Orden de venta) · Demo")

col1, col2 = st.columns(2)
with col1:
    up_po = st.file_uploader("Sube CSV de AirSupply", type=["csv"])
with col2:
    up_map = st.file_uploader("Sube CSV de referencias (opcional)", type=["csv"])

st.caption("Si no subes mapping, se usará `data/mappings/referencias_cruzadas_fake_actualizada.csv` o `data/mappings/referencias_cruzadas_fake.csv` si existen.")

# Mapping por defecto
default_map = None
for c in [
    Path("data/mappings/referencias_cruzadas_fake_actualizada.csv"),
    Path("data/mappings/referencias_cruzadas_fake.csv"),
]:
    if c.exists():
        default_map = c
        break

if st.button("Generar orden de venta"):
    if not up_po:
        st.error("Falta el CSV de AirSupply.")
        st.stop()

    try:
        df_as = read_airsupply_like(up_po)
        st.success(f"AirSupply leído: {len(df_as)} filas, {len(df_as.columns)} columnas.")
        st.dataframe(df_as.head(10), use_container_width=True)

        if up_map:
            df_map = read_mapping_like(up_map)
        else:
            if not default_map:
                st.error("No hay mapping. Sube un CSV de referencias o coloca uno en data/mappings/.")
                st.stop()
            df_map = read_mapping_like(default_map)

        df_min = select_minimal_columns(df_as)
        merged = apply_mapping(df_min, df_map)

        fixed = {
            "cliente": cfg.get("cliente"),
            "id_contrato": cfg.get("id_contrato"),
            "tipo_documento": cfg.get("tipo_documento"),
            "codigo_almacen": cfg.get("codigo_almacen"),
        }

        # DEBUG para comprobar que llegan los fijos
        st.write("DEBUG fixed =", fixed)

        df_out = build_navision_frame(merged, fixed, salida_cols)

        st.subheader("Vista previa salida")
        st.dataframe(df_out.head(20), use_container_width=True)

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_out.to_excel(writer, index=False)
        buf.seek(0)

        st.download_button(
            label="Descargar Excel (OrdenVenta_Simulada.xlsx)",
            data=buf,
            file_name="OrdenVenta_Simulada.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        vac_nav = int(df_out["Código Navision"].eq("").sum())
        st.info(f"Líneas sin correspondencia (Código Navision vacío): {vac_nav}")

    except Exception as e:
        st.error(f"Error: {e}")

