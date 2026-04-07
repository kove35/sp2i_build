"""
Page Streamlit de lecture de la base ERP/DQE locale.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.api_client import erp_fetch_dashboard, erp_fetch_filters, erp_fetch_status
from frontend.ui import (
    apply_dashboard_style,
    format_currency,
    render_proportional_bars,
    render_kpi_cards,
    show_api_error,
)


st.set_page_config(page_title="ERP DQE", layout="wide")
apply_dashboard_style("ERP DQE - Base locale structuree")

status_payload, status_error = erp_fetch_status()
if status_error:
    show_api_error(status_error)
    st.stop()

if not status_payload or not status_payload.get("available"):
    st.warning("La base locale `sp2i_erp.db` est absente. Lance d'abord `python scripts/migrate_sqlite_to_local_dqe_db.py`.")
    st.stop()

filters_payload, filters_error = erp_fetch_filters()
if filters_error:
    show_api_error(filters_error)
    st.stop()

filters_payload = filters_payload or {"batiments": [], "niveaux": [], "lots": []}

selected_filters = st.columns(3)

with selected_filters[0]:
    batiment_options = [{"value": None, "label": "Tous les batiments"}] + filters_payload.get("batiments", [])
    selected_batiment = st.selectbox(
        "Batiment",
        options=batiment_options,
        format_func=lambda option: option["label"],
    )["value"]

with selected_filters[1]:
    niveau_options = [{"value": None, "label": "Tous les niveaux"}] + filters_payload.get("niveaux", [])
    selected_niveau = st.selectbox(
        "Niveau",
        options=niveau_options,
        format_func=lambda option: option["label"],
    )["value"]

with selected_filters[2]:
    lot_options = [{"value": None, "label": "Tous les lots"}] + filters_payload.get("lots", [])
    selected_lot = st.selectbox(
        "Lot",
        options=lot_options,
        format_func=lambda option: option["label"],
    )["value"]

active_filters = {
    "batiment": selected_batiment,
    "niveau": selected_niveau,
    "lot": selected_lot,
}

st.info(
    "Filtres actifs : "
    f"batiment={selected_batiment or 'Tous'} | "
    f"niveau={selected_niveau or 'Tous'} | "
    f"lot={selected_lot or 'Tous'}"
)

dashboard_payload, dashboard_error = erp_fetch_dashboard(active_filters)
if dashboard_error:
    show_api_error(dashboard_error)
    st.stop()

dashboard_payload = dashboard_payload or {"kpis": {}, "charts": {}, "items": []}
kpis = dashboard_payload.get("kpis", {})
charts = dashboard_payload.get("charts", {})
items = dashboard_payload.get("items", [])

render_kpi_cards(
    [
        {
            "label": "Montant Total HT",
            "value": format_currency(kpis.get("montant_total_ht", 0.0)),
            "caption": "Base ERP/DQE locale",
        },
        {
            "label": "Prestations",
            "value": f"{kpis.get('nb_prestations', 0):,}".replace(",", " "),
            "caption": "Lignes de prestations",
        },
        {
            "label": "Batiments",
            "value": str(kpis.get("nb_batiments", 0)),
            "caption": "Perimetre bati",
        },
        {
            "label": "Niveaux",
            "value": str(kpis.get("nb_niveaux", 0)),
            "caption": "Granularite exploitee",
        },
    ]
)

st.markdown("## Analyse par batiment")
batiment_df = pd.DataFrame(charts.get("budget_par_batiment", []))
if not batiment_df.empty:
    render_proportional_bars(
        batiment_df,
        label_column="batiment_label",
        value_column="montant_total_ht",
        title="Budget par batiment",
        unit_suffix="FCFA",
    )

st.markdown("## Analyse par niveau")
niveau_df = pd.DataFrame(charts.get("budget_par_niveau", []))
if not niveau_df.empty:
    render_proportional_bars(
        niveau_df,
        label_column="niveau_label",
        value_column="montant_total_ht",
        title="Budget par niveau",
        unit_suffix="FCFA",
    )

st.markdown("## Analyse par lot")
lot_df = pd.DataFrame(charts.get("budget_par_lot", []))
if not lot_df.empty:
    render_proportional_bars(
        lot_df,
        label_column="lot_label",
        value_column="montant_total_ht",
        title="Budget par lot",
        unit_suffix="FCFA",
    )

st.markdown("## Detail hiérarchique")
items_df = pd.DataFrame(items)
if items_df.empty:
    st.warning("Aucune ligne ERP disponible pour ce filtre.")
else:
    items_df = items_df.rename(
        columns={
            "batiment_label": "Batiment",
            "niveau_label": "Niveau",
            "lot_label": "Lot",
            "sous_lot_label": "Sous-lot",
            "designation": "Designation",
            "unite": "Unite",
            "quantite": "Quantite",
            "prix_unitaire": "Prix unitaire",
            "montant_local": "Montant HT",
        }
    )
    st.dataframe(
        items_df,
        use_container_width=True,
        height=500,
    )
