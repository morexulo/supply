from __future__ import annotations
import math
import pandas as pd
from pathlib import Path
from .sscc import next_ue, next_ux


def plan_packing(po_df: pd.DataFrame, wh_df: pd.DataFrame, map_df: pd.DataFrame):
    """
    Genera estructura de empaquetado (UEs y UXs) a partir del pedido (PO) y del mapping.
    Usa UnitsPerBox y BoxesPerPallet del mapping para definir cajas (UE) y palets (UX).

    Retorna:
        ues: lista de dicts con info por caja (UE)
        uxs: lista de dicts con info por palet (UX)
    """

    ues = []
    uxs = []

    if po_df.empty:
        return ues, uxs

    for _, row in po_df.iterrows():
        item_as = row.get("Item Number", "") or row.get("Customer Material Number", "")
        qty = float(row.get("Requested quantity", 0) or row.get("Ordered Quantity", 0) or 0)

        # Buscar correspondencia en el mapping
        match = map_df.loc[map_df["Codigo_SAP_ItemNumber"] == item_as] if "Codigo_SAP_ItemNumber" in map_df.columns else pd.DataFrame()
        if match.empty:
            # intentar coincidencia por descripción parcial
            desc = str(row.get("PO Line Desc.", "")).strip().lower()
            match = map_df[map_df["Descripcion"].str.lower().str.contains(desc, na=False)] if "Descripcion" in map_df.columns else pd.DataFrame()

        # valores por defecto
        units_per_box = 1
        boxes_per_pallet = 1
        codigo_navision = ""
        desc_navision = ""

        if not match.empty:
            m = match.iloc[0]
            codigo_navision = m.get("Codigo_Navision", "")
            desc_navision = m.get("Descripcion", "")
            try:
                units_per_box = int(float(m.get("UnitsPerBox", 1)))
                boxes_per_pallet = int(float(m.get("BoxesPerPallet", 1)))
            except Exception:
                pass

        if qty <= 0:
            continue

        total_boxes = math.ceil(qty / units_per_box)
        total_pallets = math.ceil(total_boxes / boxes_per_pallet)

        # Crear UX (palets)
        for ux_idx in range(total_pallets):
            ux_sscc = next_ux()
            ux_entry = {
                "sscc": ux_sscc,
                "item_as": item_as,
                "codigo_navision": codigo_navision,
                "desc_navision": desc_navision,
                "boxes": [],
            }
            uxs.append(ux_entry)

        # Crear UE (cajas)
        box_counter = 0
        pallet_idx = 0
        for b in range(total_boxes):
            ue_sscc = next_ue()
            pallet_sscc = uxs[pallet_idx]["sscc"] if uxs else ""
            qty_this_box = min(units_per_box, qty - (b * units_per_box))
            ue_entry = {
                "item_as": item_as,
                "codigo_navision": codigo_navision,
                "desc_navision": desc_navision,
                "qty": qty_this_box,
                "lote": "",
                "mfg_date": "",
                "exp_date": "",
                "albaran": "",
                "sscc": ue_sscc,
                "ux_sscc": pallet_sscc,
            }
            ues.append(ue_entry)
            uxs[pallet_idx]["boxes"].append(ue_entry)
            box_counter += 1
            if box_counter >= boxes_per_pallet:
                box_counter = 0
                pallet_idx = min(pallet_idx + 1, len(uxs) - 1)

    return ues, uxs
