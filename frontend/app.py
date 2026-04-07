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
    build_bar_chart,
    build_donut_chart,
    format_currency,
    format_percentage,
    render_active_filters,
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
            "caption": "Reference 100% locale",
        },
        {
            "label": "CAPEX Optimise",
            "value": format_currency(direction_kpis["capex_optimise"]),
            "caption": "Scenario arbitre",
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
        decision_figure = build_donut_chart(
            decision_df,
            names="decision",
            values="value",
            title="Structure de decision",
        )
        if plotly_events is None:
            st.plotly_chart(decision_figure, use_container_width=True)
        else:
            plotly_events(
                decision_figure,
                click_event=False,
                hover_event=False,
                select_event=False,
                override_height=420,
                key="home_decision_chart",
            )

with top_right:
    lot_df = pd.DataFrame(direction_data["charts"]["capex_par_lot"])
    if not lot_df.empty:
        lot_figure = build_bar_chart(
            lot_df.head(10),
            x="lot",
            y="capex",
            title="Top lots par CAPEX optimise",
        )
        if plotly_events is None:
            st.plotly_chart(lot_figure, use_container_width=True)
        else:
            selected_lot_points = plotly_events(
                lot_figure,
                click_event=True,
                hover_event=False,
                select_event=False,
                override_height=420,
                key="home_lot_chart",
            )
            if selected_lot_points and _apply_chart_filter(
                "lot_id",
                selected_lot_points[0].get("x"),
                filter_options.get("lots", []),
            ):
                st.rerun()

middle_left, middle_right = st.columns(2)

with middle_left:
    family_df = pd.DataFrame(direction_data["charts"]["economie_par_famille"])
    if not family_df.empty:
        family_figure = build_bar_chart(
            family_df.head(10),
            x="famille",
            y="economie",
            title="Economies par famille",
            horizontal=True,
        )
        if plotly_events is None:
            st.plotly_chart(family_figure, use_container_width=True)
        else:
            selected_family_points = plotly_events(
                family_figure,
                click_event=True,
                hover_event=False,
                select_event=False,
                override_height=420,
                key="home_family_chart",
            )
            clicked_family = None
            if selected_family_points:
                clicked_family = selected_family_points[0].get("y")
                if clicked_family is None and selected_family_points[0].get("customdata"):
                    clicked_family = selected_family_points[0]["customdata"][0]

            if selected_family_points and _apply_chart_filter(
                "fam_article_id",
                clicked_family,
                filter_options.get("familles", []),
            ):
                st.rerun()

with middle_right:
    import_rate_df = pd.DataFrame(import_data["charts"]["taux_import_par_famille"])
    if not import_rate_df.empty:
        st.plotly_chart(
            build_bar_chart(
                import_rate_df.head(10),
                x="famille_label",
                y="taux_import",
                title="Taux import par famille",
            ),
            use_container_width=True,
        )

st.subheader("Vue rapide des opportunites")
top_articles_df = pd.DataFrame(direction_data["charts"]["top_articles_rentables"])
if not top_articles_df.empty:
    st.dataframe(top_articles_df.head(10), use_container_width=True, hide_index=True)

st.info(
    "Les filtres choisis dans la barre laterale sont partages entre l'accueil et les 3 dashboards. "
    "Vous pouvez aussi cliquer sur les graphiques Lot et Economies par famille pour alimenter ces filtres."
)
