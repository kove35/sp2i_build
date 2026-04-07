"""
Page d'accueil Streamlit.
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
try:
    from streamlit_plotly_events import plotly_events
except ImportError:  # pragma: no cover - handled visually in Streamlit
    plotly_events = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.api_client import (
    API_BASE_URL,
    analytics_reseed,
    fetch_dashboard_data,
    fetch_filter_options,
)
from frontend.ui import (
    apply_dashboard_style,
    format_currency,
    format_percentage,
    render_active_filters,
    render_decision_split,
    render_proportional_bars,
    render_kpi_cards,
    render_sidebar_filters,
    show_api_error,
)


def _option_lookup(options: list[dict]) -> dict[str, object]:
    return {str(option["label"]): option["value"] for option in options}


def _apply_chart_filter(filter_key: str, label: str | None, options: list[dict]) -> bool:
    if not label:
        return False

    selected_value = _option_lookup(options).get(str(label))
    if selected_value is None:
        return False

    current_filters = st.session_state.get("shared_filters", {})
    if current_filters.get(filter_key) == selected_value:
        return False

    updated_filters = current_filters.copy()
    updated_filters[filter_key] = selected_value
    st.session_state.shared_filters = updated_filters
    return True


st.set_page_config(
    page_title="SP2I_Build",
    page_icon="SP2I",
    layout="wide",
)

apply_dashboard_style("SP2I_Build")

st.markdown(
    """
    Hub executif de pilotage immobilier :

    - vision CAPEX pour la direction
    - lecture chantier par lot, batiment et niveau
    - audit du sourcing import Chine
    """
)

header_left, header_right = st.columns([3, 1])

with header_left:
    st.caption(f"Backend cible : {API_BASE_URL}")

with header_right:
    if st.button("Reseed Analytics", use_container_width=True):
        with st.spinner("Rechargement du schema analytique depuis les sources..."):
            reseed_result, reseed_error = analytics_reseed()

        if reseed_error:
            st.error(f"Reseed impossible : {reseed_error}")
        else:
            st.success(
                "Reseed termine : "
                f"{reseed_result['fact_rows']} lignes de faits rechargees."
            )
            st.rerun()

filter_options, filter_error = fetch_filter_options()
if filter_error:
    show_api_error(filter_error)
    st.stop()

active_filters = render_sidebar_filters(filter_options)
render_active_filters(active_filters, filter_options)

direction_data, direction_error = fetch_dashboard_data("kpi_direction", active_filters)
chantier_data, chantier_error = fetch_dashboard_data("kpi_chantier", active_filters)
import_data, import_error = fetch_dashboard_data("kpi_import", active_filters)

if direction_error or chantier_error or import_error:
    show_api_error(direction_error or chantier_error or import_error)
    st.stop()

direction_kpis = direction_data["kpis"]
import_kpis = import_data["kpis"]

render_kpi_cards(
    [
        {
            "label": "CAPEX Brut",
            "value": format_currency(direction_kpis["capex_brut"]),
            "caption": "Source DQE d'origine",
        },
        {
            "label": "CAPEX Optimise",
            "value": format_currency(direction_kpis["capex_optimise"]),
            "caption": "Projection IMPORT / LOCAL",
        },
        {
            "label": "Economie Globale",
            "value": format_currency(direction_kpis["economie"]),
            "caption": f"Taux : {format_percentage(direction_kpis['taux_optimisation'])}",
        },
        {
            "label": "Couverture Sourcing",
            "value": format_percentage(import_kpis["taux_couverture_sourcing"]),
            "caption": f"Articles sans prix Chine : {import_kpis['articles_sans_prix_chine']}",
        },
    ]
)

top_left, top_right = st.columns(2)

with top_left:
    decision_df = pd.DataFrame(direction_data["charts"]["repartition_local_import"])
    if not decision_df.empty:
        render_decision_split(
            decision_df,
            label_column="decision",
            value_column="value",
            title="Structure de decision sur CAPEX brut source",
        )

with top_right:
    lot_df = pd.DataFrame(direction_data["charts"]["capex_par_lot"])
    if not lot_df.empty:
        render_proportional_bars(
            lot_df.head(10),
            label_column="lot",
            value_column="capex",
            title="Top lots par CAPEX brut source",
            unit_suffix="FCFA",
        )

middle_left, middle_right = st.columns(2)

with middle_left:
    family_df = pd.DataFrame(direction_data["charts"]["capex_brut_par_famille"])
    if not family_df.empty:
        render_proportional_bars(
            family_df.head(10),
            label_column="famille",
            value_column="capex",
            title="CAPEX brut par famille",
            unit_suffix="FCFA",
        )

with middle_right:
    import_rate_df = pd.DataFrame(import_data["charts"]["taux_import_par_famille"])
    if not import_rate_df.empty:
        render_proportional_bars(
            import_rate_df.head(10),
            label_column="famille_label",
            value_column="taux_import",
            title="Taux import par famille",
            percentage_mode=True,
        )

st.subheader("Vue rapide de la source")
top_articles_df = pd.DataFrame(direction_data["charts"]["top_articles_source"])
if not top_articles_df.empty:
    st.dataframe(top_articles_df.head(10), use_container_width=True, hide_index=True)

st.info(
    "Les filtres choisis dans la barre laterale sont partages entre l'accueil et les 3 dashboards. "
    "Sur l'accueil, le pilotage par clic reste desactive tant que le rendu des graphiques n'est pas stabilise."
)
