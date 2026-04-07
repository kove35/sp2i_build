"""
Interface premium SaaS :
- connexion JWT
- gestion multi-projets
- saisie CAPEX
- dashboard premium
- recommandations import
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.api_client import (
    saas_create_project,
    saas_fetch_dashboard,
    saas_fetch_projects,
    saas_fetch_recommendations,
    saas_login,
    saas_register,
    saas_save_capex_item,
)
from frontend.ui import apply_dashboard_style, format_currency, format_percentage
from frontend.ui import render_decision_split, render_proportional_bars


st.set_page_config(page_title="SP2I SaaS Premium", page_icon="PREMIUM", layout="wide")
apply_dashboard_style("SP2I_Build SaaS Premium")


def _frame_chart(figure, horizontal: bool = False, row_count: int = 10):
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
        height=max(420, min(760, 360 + row_count * 12)) if not horizontal else max(440, min(960, 120 + row_count * 34)),
        margin=dict(
            l=150 if horizontal else 42,
            r=32,
            t=58,
            b=118 if not horizontal else 40,
        ),
        bargap=0.22,
        coloraxis_showscale=False,
    )
    figure.update_xaxes(
        automargin=True,
        tickangle=0 if horizontal else -32,
        title_standoff=16,
        tickfont=dict(size=11),
    )
    figure.update_yaxes(
        automargin=True,
        title_standoff=16,
        tickfont=dict(size=11),
    )
    figure.update_traces(
        marker_color="#7cc4ff",
        marker_line_color="#dbeafe",
        marker_line_width=1.2,
        opacity=0.95,
    )
    return figure


def initialize_state() -> None:
    """
    Etat frontend du module SaaS.
    """
    if "saas_token" not in st.session_state:
        st.session_state.saas_token = None
    if "saas_user" not in st.session_state:
        st.session_state.saas_user = None
    if "saas_project_id" not in st.session_state:
        st.session_state.saas_project_id = None


def show_auth_section() -> None:
    """
    Affiche login et creation de compte.
    """
    auth_tab_login, auth_tab_register = st.tabs(["Connexion", "Inscription"])

    with auth_tab_login:
        with st.form("saas_login_form"):
            email = st.text_input("Email", key="saas_login_email")
            password = st.text_input("Mot de passe", type="password", key="saas_login_password")
            submitted = st.form_submit_button("Se connecter", use_container_width=True)

        if submitted:
            payload, error = saas_login(email, password)
            if error:
                st.error(error)
            else:
                st.session_state.saas_token = payload["access_token"]
                st.session_state.saas_user = payload["user"]
                st.success("Connexion reussie.")
                st.rerun()

    with auth_tab_register:
        with st.form("saas_register_form"):
            full_name = st.text_input("Nom complet", key="saas_register_name")
            email = st.text_input("Email", key="saas_register_email")
            password = st.text_input("Mot de passe", type="password", key="saas_register_password")
            submitted = st.form_submit_button("Creer un compte", use_container_width=True)

        if submitted:
            payload, error = saas_register(full_name, email, password)
            if error:
                st.error(error)
            else:
                st.session_state.saas_token = payload["access_token"]
                st.session_state.saas_user = payload["user"]
                st.success("Compte cree et connecte.")
                st.rerun()


initialize_state()

if not st.session_state.saas_token:
    st.info("Connecte-toi pour activer le mode SaaS multi-projets.")
    show_auth_section()
    st.stop()

st.success(f"Connecte : {st.session_state.saas_user['full_name']}")

projects_payload, projects_error = saas_fetch_projects(st.session_state.saas_token)
if projects_error:
    st.error(projects_error)
    st.stop()

projects = projects_payload or []

with st.expander("Creer un projet", expanded=not bool(projects)):
    with st.form("create_project_form"):
        project_name = st.text_input("Nom du projet")
        project_code = st.text_input("Code projet")
        project_description = st.text_area("Description")
        create_project_submitted = st.form_submit_button(
            "Creer le projet",
            use_container_width=True,
        )

    if create_project_submitted:
        payload, error = saas_create_project(
            st.session_state.saas_token,
            {
                "name": project_name,
                "code": project_code,
                "description": project_description,
            },
        )
        if error:
            st.error(error)
        else:
            st.session_state.saas_project_id = payload["id"]
            st.success("Projet cree.")
            st.rerun()

if not projects:
    st.warning("Aucun projet SaaS pour le moment. Cree le premier pour commencer.")
    st.stop()

project_options = {
    f"{project['code']} - {project['name']}": project["id"] for project in projects
}
default_index = 0
if st.session_state.saas_project_id in project_options.values():
    selected_label = next(
        label
        for label, project_id in project_options.items()
        if project_id == st.session_state.saas_project_id
    )
    default_index = list(project_options.keys()).index(selected_label)

selected_project_label = st.selectbox(
    "Projet actif",
    options=list(project_options.keys()),
    index=default_index,
)
st.session_state.saas_project_id = project_options[selected_project_label]
project_id = st.session_state.saas_project_id

dashboard_payload, dashboard_error = saas_fetch_dashboard(
    st.session_state.saas_token,
    project_id,
    {},
)
if dashboard_error:
    st.error(dashboard_error)
    st.stop()

available_filters = dashboard_payload.get("filters", {})

st.markdown("### Filtres premium")
filter_col_1, filter_col_2, filter_col_3, filter_col_4 = st.columns(4)
with filter_col_1:
    selected_lots = st.multiselect("LOT", options=available_filters.get("lots", []))
with filter_col_2:
    selected_families = st.multiselect("FAMILLE", options=available_filters.get("families", []))
with filter_col_3:
    selected_niveaux = st.multiselect("NIVEAU", options=available_filters.get("niveaux", []))
with filter_col_4:
    selected_batiments = st.multiselect("BATIMENT", options=available_filters.get("batiments", []))

dashboard_payload, dashboard_error = saas_fetch_dashboard(
    st.session_state.saas_token,
    project_id,
    {
        "lot_ids": selected_lots,
        "families": selected_families,
        "niveaux": selected_niveaux,
        "batiments": selected_batiments,
    },
)
if dashboard_error:
    st.error(dashboard_error)
    st.stop()

kpis = dashboard_payload["kpis"]
kpi_col_1, kpi_col_2, kpi_col_3, kpi_col_4 = st.columns(4)
kpi_col_1.metric("CAPEX Brut", format_currency(kpis["capex_brut"]))
kpi_col_2.metric("CAPEX Optimise", format_currency(kpis["capex_optimise"]))
kpi_col_3.metric("Economie", format_currency(kpis["economie"]))
kpi_col_4.metric("Taux", format_percentage(kpis["taux_optimisation"]))

chart_col_1, chart_col_2 = st.columns(2)
capex_by_lot_df = pd.DataFrame(dashboard_payload["charts"]["capex_by_lot"])
decision_mix_df = pd.DataFrame(dashboard_payload["charts"]["decision_mix"])
economy_by_family_df = pd.DataFrame(dashboard_payload["charts"]["economy_by_family"])
top_articles_df = pd.DataFrame(dashboard_payload["charts"]["top_articles"])

with chart_col_1:
    if not capex_by_lot_df.empty:
        render_proportional_bars(
            capex_by_lot_df,
            label_column="lot_id",
            value_column="value",
            title="CAPEX par lot",
            unit_suffix="FCFA",
        )
    else:
        st.info("Pas encore de donnees CAPEX par lot.")

with chart_col_2:
    if not decision_mix_df.empty:
        render_decision_split(
            decision_mix_df.rename(columns={"label": "decision"}),
            label_column="decision",
            value_column="value",
            title="Structure de decision",
        )
    else:
        st.info("Pas encore de structure IMPORT / LOCAL.")

if not economy_by_family_df.empty:
    render_proportional_bars(
        economy_by_family_df,
        label_column="label",
        value_column="value",
        title="Economie par famille",
        unit_suffix="FCFA",
    )

st.subheader("Top articles")
if top_articles_df.empty:
    st.info("Ajoute des lignes CAPEX pour voir apparaitre les top articles.")
else:
    st.dataframe(top_articles_df, use_container_width=True, hide_index=True)

st.subheader("Ajouter une ligne CAPEX")
with st.form("add_capex_item_form"):
    form_col_1, form_col_2, form_col_3 = st.columns(3)
    with form_col_1:
        lot_id = st.text_input("Lot")
        family_article = st.text_input("Famille article")
        code_bpu = st.text_input("Code BPU")
        decision = st.selectbox("Decision", options=["LOCAL", "IMPORT"])
    with form_col_2:
        batiment = st.text_input("Batiment")
        niveau = st.text_input("Niveau")
        quantity = st.number_input("Quantite", min_value=0.0, value=1.0, step=1.0)
    with form_col_3:
        montant_local = st.number_input("Montant local", min_value=0.0, value=0.0, step=1000.0)
        montant_import = st.number_input("Montant import", min_value=0.0, value=0.0, step=1000.0)
        risk_score = st.slider("Risque", min_value=0.0, max_value=5.0, value=2.0, step=0.1)
        import_score = st.slider("Score import", min_value=0.0, max_value=1.0, value=0.5, step=0.05)

    save_item_submitted = st.form_submit_button("Ajouter la ligne", use_container_width=True)

if save_item_submitted:
    payload, error = saas_save_capex_item(
        st.session_state.saas_token,
        project_id,
        {
            "lot_id": lot_id,
            "family_article": family_article,
            "code_bpu": code_bpu,
            "batiment": batiment,
            "niveau": niveau,
            "decision": decision,
            "quantity": quantity,
            "montant_local": montant_local,
            "montant_import": montant_import,
            "risk_score": risk_score,
            "import_score": import_score,
            "source_index": 0,
        },
    )
    if error:
        st.error(error)
    else:
        st.success("Ligne CAPEX ajoutee.")
        st.rerun()

recommendations_payload, recommendations_error = saas_fetch_recommendations(
    st.session_state.saas_token,
    project_id,
)

st.subheader("IA recommandation import")
if recommendations_error:
    st.warning(recommendations_error)
elif not recommendations_payload.get("recommendations"):
    st.info("Ajoute des lignes CAPEX pour activer les recommandations IA.")
else:
    recommendations_df = pd.DataFrame(recommendations_payload["recommendations"])
    st.dataframe(recommendations_df, use_container_width=True, hide_index=True)
