"""
Page d'accueil Streamlit.

Cette page reste volontairement simple :
- aucune logique ETL
- aucune initialisation lourde
- uniquement des appels backend et de l'affichage
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.api_client import (
    API_BASE_URL,
    analytics_reseed,
    fetch_api_health,
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


st.set_page_config(
    page_title="SP2I_Build",
    page_icon="SP2I",
    layout="wide",
)


def render_backend_unavailable(error_message: str) -> None:
    """
    Affiche un ecran propre si le backend n'est pas joignable.
    """
    apply_dashboard_style("SP2I_Build")
    st.markdown(
        """
        Hub executif de pilotage immobilier :

        - vision CAPEX pour la direction
        - lecture chantier par lot, batiment et niveau
        - audit du sourcing import Chine
        """
    )
    st.error(error_message)
    st.warning(
        "Le frontend Streamlit est bien demarre, mais l'API backend n'est pas joignable."
    )
    st.code(
        f"SP2I_API_URL={API_BASE_URL}",
        language="bash",
    )
    st.info(
        "Pour Streamlit Cloud, pointez `SP2I_API_URL` vers une API FastAPI publique. "
        "Pour un usage local, demarrez d'abord `uvicorn backend.main:app --reload`."
    )
    st.stop()


def main() -> None:
    """
    Rend la page d'accueil.
    """
    health_payload, health_error = fetch_api_health()
    if health_error:
        render_backend_unavailable(health_error)

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
        backend_status = health_payload.get("status", "unknown") if health_payload else "unknown"
        st.caption(f"Backend cible : {API_BASE_URL} | Etat API : {backend_status}")

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
            st.plotly_chart(
                build_donut_chart(
                    decision_df,
                    names="decision",
                    values="value",
                    title="Structure de decision",
                ),
                use_container_width=True,
            )

    with top_right:
        lot_df = pd.DataFrame(direction_data["charts"]["capex_par_lot"])
        if not lot_df.empty:
            st.plotly_chart(
                build_bar_chart(
                    lot_df.head(10),
                    x="lot",
                    y="capex",
                    title="Top lots par CAPEX optimise",
                ),
                use_container_width=True,
            )

    middle_left, middle_right = st.columns(2)

    with middle_left:
        family_df = pd.DataFrame(direction_data["charts"]["economie_par_famille"])
        if not family_df.empty:
            st.plotly_chart(
                build_bar_chart(
                    family_df.head(10),
                    x="famille",
                    y="economie",
                    title="Economies par famille",
                    horizontal=True,
                ),
                use_container_width=True,
            )

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
        "Les filtres choisis dans la barre laterale sont partages entre l'accueil et les dashboards."
    )


main()
