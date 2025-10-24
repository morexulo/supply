#!/usr/bin/env bash
# setup_streamlit.sh
# Crea la app Streamlit para la demo AirSupply → Navision

set -euo pipefail

# 1) Comprobaciones mínimas
test -d src/app || { echo "No existe src/app. Ejecuta antes el init del proyecto."; exit 1; }
test -f config/config.yaml || { echo "Falta config/config.yaml"; exit 1; }

# 2) Añadir Streamlit a requirements si no está
grep -qi '^streamlit' requirements.txt || echo "streamlit==1.39.0" >> requirements.txt

# 3) Config Streamlit opcional (tema claro)
mkdir -p .streamlit
cat > .streamlit/config.toml <<'EOF'
[theme]
base="light"
EOF

# 4) App Streamlit
cat > src/app/streamlit_app.py <<'EOF'
from __future__ import annotations
import io
from pathlib import Path
import pandas as pd
import streamlit as st
import yaml

from src.core.transform import select_minimal_columns, apply_mapping, build_navision_frame

st.set_page_config(page_title="AirSupply → Navision | Demo", layout="wide")

# --- Utilidades ---
def load_config(cfg_path: str | Path) -> dict:
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def read_airsupply_like(file) -> pd.DataFrame:
    # CSV AirSupply: separador ';', comillas dobles, todo string
    return pd.read_csv(file, sep=";", quotechar='"', dtype=str).fillna("")

def read_mapping_like(file) -> pd.DataFrame:
    df = pd.read_csv(file, dtype=str).fillna("")
    needed = {"Codigo_SAP_ItemNumber","Codigo_Navision","Descripcion"}
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

st.caption("Si no subes mapping, se intentará usar `data/mappings/referencias_cruzadas_fake_actualizada.csv` o `data/mappings/referencias_cruzadas_fake.csv` del proyecto.")

# Resolver mapping por defecto si no hay upload
default_map = None
cand = [
    Path("data/mappings/referencias_cruzadas_fake_actualizada.csv"),
    Path("data/mappings/referencias_cruzadas_fake.csv"),
]
for c in cand:
    if c.exists():
        default_map = c
        break

gen = st.button("Generar orden de venta")

if gen:
    if not up_po:
        st.error("Falta el CSV de AirSupply.")
        st.stop()

    try:
        # Leer AirSupply
        df_as = read_airsupply_like(up_po)
        st.success(f"AirSupply leído: {len(df_as)} filas, {len(df_as.columns)} columnas.")
        st.dataframe(df_as.head(10), use_container_width=True)

        # Leer mapping
        if up_map:
            df_map = read_mapping_like(up_map)
        else:
            if not default_map:
                st.error("No hay mapping. Sube un CSV de referencias o coloca uno en data/mappings/.")
                st.stop()
            df_map = read_mapping_like(default_map)

        # Transformación mínima
        df_min = select_minimal_columns(df_as)
        merged = apply_mapping(df_min, df_map)

        fixed = {
            "cliente": cfg["cliente"],
            "id_contrato": cfg["id_contrato"],
            "tipo_documento": cfg["tipo_documento"],
            "codigo_almacen": cfg["codigo_almacen"],
        }
        df_out = build_navision_frame(merged, fixed, salida_cols)

        # Vista previa
        st.subheader("Vista previa salida")
        st.dataframe(df_out.head(20), use_container_width=True)

        # Generar Excel en memoria
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

        # Métricas simples
        vac_nav = int(df_out["Código Navision"].eq("").sum())
        st.info(f"Líneas sin correspondencia (Código Navision vacío): {vac_nav}")

    except Exception as e:
        st.error(f"Error: {e}")
EOF

# 5) Script lanzador
mkdir -p scripts
cat > scripts/run_streamlit.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
# Activa venv si existe
if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
streamlit run src/app/streamlit_app.py
EOF
chmod +x scripts/run_streamlit.sh

echo "Listo. Instala dependencias y ejecuta:"
echo "  source .venv/bin/activate && pip install -r requirements.txt"
echo "  ./scripts/run_streamlit.sh"
