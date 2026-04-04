"""
Composants visuels reutilisables pour Streamlit.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def apply_dashboard_style(page_title: str) -> None:
    """
    Applique le style commun a toutes les pages.
    """
    st.title(page_title)
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(0, 194, 255, 0.16), transparent 28%),
                radial-gradient(circle at top left, rgba(0, 255, 163, 0.10), transparent 22%),
                #0b1220;
            color: #f5f7fa;
        }

        .sp2i-card {
            background: linear-gradient(180deg, rgba(17, 24, 39, 0.92), rgba(15, 23, 42, 0.95));
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 18px;
            padding: 18px;
            box-shadow: 0 12px 32px rgba(2, 6, 23, 0.35);
            min-height: 135px;
        }

        .sp2i-label {
            color: #94a3b8;
            font-size: 0.92rem;
            margin-bottom: 8px;
        }

        .sp2i-value {
            color: #f8fafc;
            font-size: 2rem;
            font-weight: 700;
            line-height: 1.15;
        }

        .sp2i-caption {
            color: #38bdf8;
            font-size: 0.84rem;
            margin-top: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_currency(value: float) -> str:
    return f"{value:,.0f} FCFA".replace(",", " ")


def format_percentage(value: float) -> str:
    return f"{value * 100:,.1f} %".replace(",", " ")


def render_kpi_cards(kpis: list[dict[str, str]]) -> None:
    columns = st.columns(len(kpis))

    for column, kpi in zip(columns, kpis):
        column.markdown(
            f"""
            <div class="sp2i-card">
                <div class="sp2i-label">{kpi["label"]}</div>
                <div class="sp2i-value">{kpi["value"]}</div>
                <div class="sp2i-caption">{kpi["caption"]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _build_option_index(options: list[dict], selected_value) -> int:
    """
    Retrouve l'index correspondant a une valeur deja stockee.
    """
    for index, option in enumerate(options):
        if option["value"] == selected_value:
            return index
    return 0


def render_sidebar_filters(filter_options: dict) -> dict:
    """
    Affiche des filtres synchronises entre toutes les pages Streamlit.
    """
    st.sidebar.header("Filtres")

    lot_options = [{"value": None, "label": "Tous les lots"}] + filter_options.get("lots", [])
    family_options = [{"value": None, "label": "Toutes les familles"}] + filter_options.get("familles", [])
    building_options = [{"value": None, "label": "Tous les batiments"}] + filter_options.get("batiments", [])
    level_options = [{"value": None, "label": "Tous les niveaux"}] + filter_options.get("niveaux", [])

    if "shared_filters" not in st.session_state:
        st.session_state.shared_filters = {
            "lot_id": None,
            "fam_article_id": None,
            "batiment_id": None,
            "niveau_id": None,
        }

    current_filters = st.session_state.shared_filters

    selected_lot = st.sidebar.selectbox(
        "Lot",
        options=lot_options,
        index=_build_option_index(lot_options, current_filters.get("lot_id")),
        format_func=lambda option: option["label"],
        key="sidebar_lot_id",
    )
    selected_family = st.sidebar.selectbox(
        "Famille d'article",
        options=family_options,
        index=_build_option_index(family_options, current_filters.get("fam_article_id")),
        format_func=lambda option: option["label"],
        key="sidebar_fam_article_id",
    )
    selected_building = st.sidebar.selectbox(
        "Batiment",
        options=building_options,
        index=_build_option_index(building_options, current_filters.get("batiment_id")),
        format_func=lambda option: option["label"],
        key="sidebar_batiment_id",
    )
    selected_level = st.sidebar.selectbox(
        "Niveau",
        options=level_options,
        index=_build_option_index(level_options, current_filters.get("niveau_id")),
        format_func=lambda option: option["label"],
        key="sidebar_niveau_id",
    )

    updated_filters = {
        "lot_id": selected_lot["value"],
        "fam_article_id": selected_family["value"],
        "batiment_id": selected_building["value"],
        "niveau_id": selected_level["value"],
    }

    st.session_state.shared_filters = updated_filters

    if st.sidebar.button("Reinitialiser les filtres", use_container_width=True):
        st.session_state.shared_filters = {
            "lot_id": None,
            "fam_article_id": None,
            "batiment_id": None,
            "niveau_id": None,
        }
        st.rerun()

    return updated_filters


def render_active_filters(filters: dict, filter_options: dict) -> None:
    """
    Affiche un resume texte des filtres actifs.
    """
    def find_label(options: list[dict], value) -> str:
        for option in options:
            if option["value"] == value:
                return option["label"]
        return "Tous"

    labels = [
        f"Lot : {find_label(filter_options.get('lots', []), filters.get('lot_id')) if filters.get('lot_id') is not None else 'Tous'}",
        f"Famille : {find_label(filter_options.get('familles', []), filters.get('fam_article_id')) if filters.get('fam_article_id') else 'Toutes'}",
        f"Batiment : {find_label(filter_options.get('batiments', []), filters.get('batiment_id')) if filters.get('batiment_id') else 'Tous'}",
        f"Niveau : {find_label(filter_options.get('niveaux', []), filters.get('niveau_id')) if filters.get('niveau_id') else 'Tous'}",
    ]
    st.caption(" | ".join(labels))


def build_donut_chart(dataframe: pd.DataFrame, names: str, values: str, title: str) -> go.Figure:
    figure = px.pie(
        dataframe,
        names=names,
        values=values,
        hole=0.6,
        color=names,
        color_discrete_sequence=["#00c2ff", "#00f5a0", "#ffb703", "#fb7185"],
        title=title,
    )
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return figure


def build_bar_chart(
    dataframe: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    horizontal: bool = False,
) -> go.Figure:
    if horizontal:
        figure = px.bar(
            dataframe,
            x=y,
            y=x,
            orientation="h",
            title=title,
            color=y,
            color_continuous_scale=["#0ea5e9", "#22c55e"],
        )
    else:
        figure = px.bar(
            dataframe,
            x=x,
            y=y,
            title=title,
            color=y,
            color_continuous_scale=["#0ea5e9", "#22c55e"],
        )

    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
        margin=dict(l=20, r=20, t=60, b=20),
        coloraxis_showscale=False,
    )
    return figure


def build_heatmap(
    dataframe: pd.DataFrame,
    row: str,
    column: str,
    value: str,
    title: str,
) -> go.Figure:
    pivot_table = dataframe.pivot_table(
        index=row,
        columns=column,
        values=value,
        aggfunc="sum",
        fill_value=0,
    )

    figure = go.Figure(
        data=go.Heatmap(
            z=pivot_table.values,
            x=list(pivot_table.columns),
            y=list(pivot_table.index),
            colorscale="Blues",
            hoverongaps=False,
        )
    )
    figure.update_layout(
        title=title,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return figure


def build_scatter_chart(
    dataframe: pd.DataFrame,
    x: str,
    y: str,
    size: str,
    color: str,
    hover_name: str,
    title: str,
) -> go.Figure:
    figure = px.scatter(
        dataframe,
        x=x,
        y=y,
        size=size,
        color=color,
        hover_name=hover_name,
        title=title,
        color_continuous_scale=["#f59e0b", "#10b981"],
        size_max=40,
    )
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return figure


def show_api_error(error_message: str) -> None:
    st.error(error_message)
    st.info(
        "Demarrez d'abord le backend FastAPI avec : "
        "`uvicorn backend.main:app --reload`"
    )
