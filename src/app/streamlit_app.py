from __future__ import annotations
import io, os, sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import yaml

# =========================
# Imports locales de tu repo
# =========================
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from src.core.transform import select_minimal_columns, apply_mapping, build_navision_frame
from src.core.da_build import build_da

st.set_page_config(page_title="AirSupply → Navision | Demo", layout="wide")

# =========================
# Constantes fijas DA-123
# =========================
DA_CONSTS = {
    "SUPPLIERNO": "5072826",
    "SUPPLIER NUMBER": "5072826",
    "DAUPLOADCODE": "SEND",
    "CUSTOMERGROUPCODE": "CUST",
    "SHIPFROMNAME1": "GECI INDUS",
    "SHIPFROMCITY": "JEREZ",
    "SHIPFROMCOUNTRYCODE": "ES",
    "SHIPFROMCOUNTRY": "SPAIN",
    "FORWARDERID": "GECI INDUS",
    "FORWARDERNAME1": "GECI INDUS",
    "TRANSPORTMODE": "ROAD",
    "CUSTOMERPLANTCODE": "GER",
    "CUSTOMS": "N",
}

# =========================
# Utilidades comunes
# =========================
def load_config(cfg_path: str | Path) -> dict:
    if not Path(cfg_path).exists():
        return {}
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def ensure_dirs():
    for p in [
        Path("data/output/da"),
        Path("data/input/pos"),
        Path("data/state"),
        Path("data/mappings"),
        Path("data/warehouse"),
        Path("data/templates"),
    ]:
        p.mkdir(parents=True, exist_ok=True)

def _norm(s: str) -> str:
    return str(s).strip().lower().replace(" ", "").replace("_", "")

def _first_present(template_cols: list[str], variants: list[str]) -> str | None:
    if not template_cols:
        return None
    lut = {_norm(c): c for c in template_cols}
    for v in variants:
        hit = lut.get(_norm(v))
        if hit:
            return hit
    return None

def _pick_series(df: pd.DataFrame, candidates: list[str], default_val: str | None = None) -> pd.Series:
    for c in candidates:
        if c in df.columns:
            return df[c].astype(str).fillna("")
        # búsqueda por normalización
        for col in df.columns:
            if _norm(col) == _norm(c):
                return df[col].astype(str).fillna("")
    if default_val is None:
        return pd.Series([""] * len(df))
    return pd.Series([default_val] * len(df))

def smart_read_csv(path: Path, preferred_sep: str | None = None, nrows: int | None = None) -> tuple[pd.DataFrame, str]:
    seps = [preferred_sep] if preferred_sep else []
    seps += [";", ","]
    tried = set()
    for sep in seps:
        if sep in tried or sep is None:
            continue
        tried.add(sep)
        try:
            df = pd.read_csv(path, sep=sep, dtype=str, na_filter=False, nrows=nrows)
            # si hay solo 1 columna con separadores visibles, prueba el otro
            if df.shape[1] == 1:
                continue
            return df.fillna(""), sep
        except Exception:
            continue
    # último intento bruto
    df = pd.read_csv(path, sep=None, engine="python", dtype=str, na_filter=False, nrows=nrows).fillna("")
    used = getattr(df, "columns", None)
    return df, (preferred_sep or ";")

def detect_header_row(csv_path: Path, sep: str, max_scan_rows: int = 15) -> int:
    probes = {
        "ponumber","poline","supplierno","dauploadcode","departuredate",
        "estimateddeliverydate","currency","customs","shipfromname1"
    }
    raw = pd.read_csv(csv_path, header=None, nrows=max_scan_rows, sep=sep, dtype=str, na_filter=False)
    best_row, best_hits = 0, -1
    for i in range(min(max_scan_rows, len(raw))):
        row = [str(x) for x in raw.iloc[i].tolist()]
        if not any(row):
            continue
        hits = len(probes & {_norm(x) for x in row if x})
        if hits > best_hits:
            best_hits = hits
            best_row = i
    return best_row

def detect_template_columns(csv_path: Path) -> tuple[list[str], str, int]:
    # intenta ; primero, luego ,
    for sep in [";", ","]:
        try:
            header_row = detect_header_row(csv_path, sep=sep)
            cols = list(pd.read_csv(csv_path, header=header_row, nrows=0, sep=sep, dtype=str).columns)
            if cols and len(cols) > 1:
                return cols, sep, header_row
        except Exception:
            continue
    # fallback simple
    df0, sep0 = smart_read_csv(csv_path, preferred_sep=";")
    return list(df0.columns), sep0, 0

def read_airsupply_like(file) -> pd.DataFrame:
    return pd.read_csv(file, sep=";", quotechar='"', dtype=str).fillna("")

def read_mapping_like(file) -> pd.DataFrame:
    df = pd.read_csv(file, dtype=str).fillna("")
    needed = {"Codigo_SAP_ItemNumber", "Codigo_Navision", "Descripcion"}
    miss = needed - set(df.columns)
    if miss:
        raise ValueError(f"Faltan columnas en mapping: {miss}")
    return df

# =========================
# DA 123 columnas desde PO + plantilla
# =========================
PO_TO_DA123 = [
    (["PONUMBER","PO NUMBER","PO"],                           ["PO","PO Number"],                                           None),
    (["POLINE","PO LINE","POITEM","PO ITEM"],                 ["PO Line"],                                                  None),
    (["CUSTOMERMATERIALNUMBER"],                              ["Customer Material Number"],                                  None),
    (["SUPPLIERMATERIALNUMBER"],                              ["Supplier Material Number"],                                  None),
    (["MATERIALDESCRIPTION","ITEMDESCRIPTION","PO LINE DESC."],
     ["Supplier Material Description","PO Line Desc.","Item Description","Material Description"],                            None),
    (["SHIPPEDQUANTITY","ORDEREDQUANTITY","QUANTITY"],        ["Requested quantity","Ordered Quantity","Quantity","Shipped Quantity"], None),
    (["CURRENCY"],                                            ["Currency"],                                                 None),
    (["PRICEUNIT"],                                           ["Price Unit"],                                               None),
    (["PROMISEDDATE"],                                       ["Promised date","Promised Date"],                              None),
    (["REQUESTEDDATE"],                                      ["Requested date","Requested Date"],                            None),
    (["BATCHNUMBER","LOT"],                                   ["Batch","Lot","Batch Number","Batch Number Customer","Batch Number Supplier"], None),
    (["DEPARTUREDATE","DESPATCHDATE","DESPATCH DATE"],        [],                                                           "AUTO_DESPATCH"),
    (["ESTIMATEDDELIVERYDATE","ESTIMATED DELIVERY DATE"],     [],                                                           "AUTO_ETA"),
]

CONST_TARGETS = {
    "SUPPLIERNO": ["SUPPLIERNO","SUPPLIER NUMBER","SUPPLIERNUMBER"],
    "DAUPLOADCODE": ["DAUPLOADCODE"],
    "CUSTOMERGROUPCODE": ["CUSTOMERGROUPCODE","CUSTOMER GROUP CODE"],
    "SHIPFROMNAME1": ["SHIPFROMNAME1"],
    "SHIPFROMCITY": ["SHIPFROMCITY"],
    "SHIPFROMCOUNTRYCODE": ["SHIPFROMCOUNTRYCODE"],
    "SHIPFROMCOUNTRY": ["SHIPFROMCOUNTRY"],
    "FORWARDERID": ["FORWARDERID","FORWARDER ID"],
    "FORWARDERNAME1": ["FORWARDERNAME1","FORWARDER NAME1","FORWARDERNAME"],
    "TRANSPORTMODE": ["TRANSPORTMODE","ROAD"],
    "CUSTOMERPLANTCODE": ["CUSTOMERPLANTCODE"],
    "CUSTOMS": ["CUSTOMS","Customs"],
}

def format_da_123_from_po(po_csv_path: Path, template_csv_path: Path) -> pd.DataFrame:
    # PO: leer con ; (AirSupply) y fallback si fuera necesario
    try:
        df_po = pd.read_csv(po_csv_path, sep=";", dtype=str, na_filter=False).fillna("")
        if df_po.shape[1] == 1:
            df_po = pd.read_csv(po_csv_path, sep=",", dtype=str, na_filter=False).fillna("")
    except Exception:
        df_po, _ = smart_read_csv(po_csv_path)

    # Plantilla: auto-detector de separador y fila cabecera
    template_cols, tpl_sep, header_row = detect_template_columns(template_csv_path)
    if not template_cols or len(template_cols) < 5:
        raise ValueError("Plantilla 123 mal leída. Revisa separador o cabecera.")
    df_header = pd.read_csv(template_csv_path, header=header_row, nrows=0, sep=tpl_sep, dtype=str)
    template_cols = list(df_header.columns)

    # Target con mismas columnas y nº filas del PO
    target = pd.DataFrame({col: [""] * len(df_po) for col in template_cols})

    # Copia directa de columnas idénticas
    commons = [c for c in template_cols if c in df_po.columns]
    if commons:
        target[commons] = df_po[commons].astype(str).fillna("")

    # Inyección de constantes cubriendo variantes
    for key, val in DA_CONSTS.items():
        dest_col = _first_present(template_cols, CONST_TARGETS.get(key, [key]))
        if dest_col:
            target[dest_col] = val

    # Fechas auto
    today = datetime.now()
    auto_despatch = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    auto_eta = (today + timedelta(days=2)).strftime("%Y-%m-%d")

    # Asignaciones desde el PO con fallback fechas
    for dest_variants, src_candidates, default_val in PO_TO_DA123:
        dest_col = _first_present(template_cols, dest_variants)
        if not dest_col:
            continue
        if default_val == "AUTO_DESPATCH":
            series = _pick_series(df_po, src_candidates, auto_despatch)
        elif default_val == "AUTO_ETA":
            series = _pick_series(df_po, src_candidates, auto_eta)
        else:
            series = _pick_series(df_po, src_candidates, default_val)
        target[dest_col] = target[dest_col].mask(target[dest_col].eq(""), series.astype(str))

    # === SSCC automáticos para demo en DA-123 ===
    try:
        from src.core.sscc import next_ue, next_ux
        ue_col = _first_present(template_cols, ["UE Number", "UE_NUMBER", "UE", "UE SSCC", "UE_SSCC"])
        ux_col = _first_present(template_cols, ["UX Number", "UX_NUMBER", "UX", "UX SSCC", "UX_SSCC"])
        if ue_col:
            target[ue_col] = [next_ue() for _ in range(len(target))]
        else:
            target["UE Number"] = [next_ue() for _ in range(len(target))]
        if ux_col:
            target[ux_col] = [next_ux() for _ in range(len(target))]
        else:
            target["UX Number"] = [next_ux() for _ in range(len(target))]
    except Exception:
        # si falla generación, no romper
        pass

    return target

# =========================
# Sidebar: Config
# =========================
st.sidebar.header("Configuración")
cfg_path = "config/config.yaml"
cfg = load_config(cfg_path)
with st.sidebar.expander("Valores fijos (solo lectura)", expanded=True):
    st.write(f"**Cliente:** {cfg.get('cliente','')}")
    st.write(f"**ID Contrato:** {cfg.get('id_contrato','')}")
    st.write(f"**Tipo:** {cfg.get('tipo_documento','')}")
    st.write(f"**Almacén:** {cfg.get('codigo_almacen','')}")

salida_cols = cfg.get("salida", {}).get("columnas", [])

# =========================
# UI
# =========================
st.title("AirSupply → Navision (Orden de venta + Despatch Advice) · Demo")

col1, col2 = st.columns(2)
with col1:
    up_po = st.file_uploader("Sube CSV de AirSupply (PO)", type=["csv"])
with col2:
    up_map = st.file_uploader("Sube CSV de referencias (opcional para Orden de Venta)", type=["csv"])

st.caption("Plantilla DA 123 en: data/templates/DA_123_template.csv")

# Mapping por defecto para Orden de Venta
default_map = None
for c in [
    Path("data/mappings/referencias_cruzadas_fake.csv"),
    Path("data/mappings/referencias_cruzadas_real.csv"),
]:
    if c.exists():
        default_map = c
        break

# =========================
# Orden de venta (flujo original)
# =========================
if st.button("Generar orden de venta"):
    if not up_po:
        st.error("Falta el CSV de AirSupply.")
        st.stop()

    ensure_dirs()
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

        df_out = build_navision_frame(merged, fixed, salida_cols)

        st.subheader("Vista previa salida (Orden de venta simulada)")
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

        vac_nav = int(df_out["Código Navision"].eq("").sum()) if "Código Navision" in df_out.columns else 0
        st.info(f"Líneas sin correspondencia (Código Navision vacío): {vac_nav}")

    except Exception as e:
        st.error(f"Error: {e}")


# =========================
# DA 123 columnas desde PO (formato final)
# =========================
st.markdown("---")
st.header("Generar Despatch Advice (DA) · 123 columnas exactas")

if st.button("Crear DA 123 desde PO"):
    if not up_po:
        st.error("Primero sube el CSV de AirSupply (PO).")
        st.stop()

    ensure_dirs()
    try:
        # Guardar PO
        po_path = Path("data/input/pos/PO_Streamlit.csv")
        with open(po_path, "wb") as f:
            f.write(up_po.getbuffer())

        # Plantilla 123 (auto separador + cabecera)
        template_path = Path("data/templates/DA_123_template.csv")
        if not template_path.exists():
            st.error("Falta la plantilla: data/templates/DA_123_template.csv")
            st.stop()

        df_da_123 = format_da_123_from_po(po_path, template_path)

        # Validaciones básicas
        if df_da_123.shape[1] <= 1:
            st.error("La plantilla 123 parece tener 1 columna. Revisa separador y cabecera.")
            st.stop()

        st.success(f"DA 123 generado: {len(df_da_123)} líneas y {len(df_da_123.columns)} columnas.")
        st.dataframe(df_da_123.head(20), use_container_width=True)

        # Descargas
        out_csv_123 = Path("data/output/da/DA_full_123.csv")
        out_xlsx_123 = Path("data/output/da/DA_full_123.xlsx")
        out_csv_123.parent.mkdir(parents=True, exist_ok=True)

        # CSV con ; para coherencia con AirSupply
        df_da_123.to_csv(out_csv_123, index=False, sep=";", encoding="utf-8-sig")

        buf_da_123 = io.BytesIO()
        with pd.ExcelWriter(buf_da_123, engine="openpyxl") as writer:
            df_da_123.to_excel(writer, index=False)
        buf_da_123.seek(0)

        st.download_button(
            label="Descargar DA FULL (CSV 123 columnas)",
            data=out_csv_123.read_bytes(),
            file_name="DA_full_123.csv",
            mime="text/csv",
        )
        st.download_button(
            label="Descargar DA FULL (Excel 123 columnas)",
            data=buf_da_123,
            file_name="DA_full_123.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    except Exception as e:
        st.error(f"Error al crear DA 123: {e}")
