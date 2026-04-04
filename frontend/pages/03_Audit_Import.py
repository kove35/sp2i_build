"""
Dashboard Audit Import.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.api_client import fetch_dashboard_data, fetch_filter_options
from frontend.ui import (
    apply_dashboard_style,
    build_donut_chart,
    format_currency,
    format_percentage,
    render_active_filters,
    render_kpi_cards,
    render_sidebar_filters,
    show_api_error,
)


st.set_page_config(page_title="Audit Import", page_icon="IMPORT", layout="wide")
apply_dashboard_style("Dashboard Audit Import")


def wrap_labels(series: pd.Series, width: int = 22) -> pd.Series:
    return series.fillna("").map(lambda value: "<br>".join(textwrap.wrap(str(value), width=width)) or str(value))


def build_improved_bar_chart(
    dataframe: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    horizontal: bool = False,
):
    chart_df = dataframe.copy()
    chart_df[f"{x}_display"] = wrap_labels(chart_df[x], width=20)

    if horizontal:
        figure = px.bar(
            chart_df,
            x=y,
            y=f"{x}_display",
            orientation="h",
            title=title,
            color=y,
            color_continuous_scale=["#0ea5e9", "#22c55e"],
        )
    else:
        figure = px.bar(
            chart_df,
            x=f"{x}_display",
            y=y,
            title=title,
            color=y,
            color_continuous_scale=["#0ea5e9", "#22c55e"],
        )

    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
        coloraxis_showscale=False,
        height=500,
        margin=dict(l=40, r=40, t=50, b=150 if not horizontal else 40),
        xaxis_tickangle=-45 if not horizontal else 0,
    )
    return figure


def build_improved_scatter_chart(dataframe: pd.DataFrame, title: str):
    figure = px.scatter(
        dataframe,
        x="taux_couverture",
        y="capex_importable",
        size="articles_sans_prix",
        color="capex_import_ttc",
        hover_name="famille_label",
        title=title,
        color_continuous_scale=["#f59e0b", "#10b981"],
        size_max=42,
    )
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
        height=520,
        margin=dict(l=40, r=40, t=50, b=80),
    )
    return figure


def build_control_rows(dashboard_data: dict) -> pd.DataFrame:
    charts = dashboard_data["charts"]
    rows = [
        {
            "Graphique": "Structure IMPORT vs LOCAL",
            "Valeur": float(sum(item["value"] for item in charts["structure_decision"])),
        },
        {
            "Graphique": "Matrice audit sourcing",
            "Valeur": float(sum(item["capex_importable"] for item in charts["matrice_audit_sourcing"])),
        },
        {
            "Graphique": "CAPEX sans prix Chine",
            "Valeur": float(sum(item["capex"] for item in charts["capex_sans_prix_chine"])),
        },
    ]
    audit = dashboard_data.get("audit", {})
    rows.extend(
        [
            {
                "Graphique": "Lignes importables GLOBAL avant ventilation",
                "Valeur": float(audit.get("global_importable_rows_before_ventilation", 0)),
            },
            {
                "Graphique": "Lignes importables GLOBAL apres ventilation",
                "Valeur": float(audit.get("global_importable_rows_after_ventilation", 0)),
            },
        ]
    )
    return pd.DataFrame(rows).sort_values("Valeur", ascending=False)


filter_options, filter_error = fetch_filter_options()
if filter_error:
    show_api_error(filter_error)
    st.stop()

active_filters = render_sidebar_filters(filter_options)
render_active_filters(active_filters, filter_options)

top_n = st.slider("Top N elements affiches", min_value=5, max_value=20, value=10)

dashboard_data, data_error = fetch_dashboard_data("kpi_import", active_filters)
if data_error:
    show_api_error(data_error)
    st.stop()

kpis = dashboard_data["kpis"]
render_kpi_cards(
    [
        {
            "label": "CAPEX FOB",
            "value": format_currency(kpis["capex_fob"]),
            "caption": "Base usine Chine",
        },
        {
            "label": "CAPEX Import TTC",
            "value": format_currency(kpis["capex_import_ttc"]),
            "caption": "Transport + douane + marge",
        },
        {
            "label": "CAPEX Importable",
            "value": format_currency(kpis["capex_importable"]),
            "caption": "Potentiel adressable par le sourcing",
        },
        {
            "label": "Taux couverture sourcing",
            "value": format_percentage(kpis["taux_couverture_sourcing"]),
            "caption": f"Articles sans prix Chine : {kpis['articles_sans_prix_chine']}",
        },
    ]
)

st.warning(
    "Source reelle du dashboard : schema analytique `build_fact_metre`. "
    "Le dashboard ne lit pas directement `fact_metre` historique."
)
st.info(
    "Contexte affiche : "
    f"lot={active_filters.get('lot_id') or 'Tous'} | "
    f"famille={active_filters.get('fam_article_id') or 'Toutes'} | "
    f"batiment={active_filters.get('batiment_id') or 'Tous'} | "
    f"niveau={active_filters.get('niveau_id') or 'Tous'}"
)
st.info(
    "Point de vigilance metier : la couverture sourcing depend encore de lignes "
    "importables restees au niveau GLOBAL et de familles sans prix Chine."
)
if dashboard_data.get("audit"):
    audit = dashboard_data["audit"]
    st.info(
        "Ventilation analytique des lignes importables : "
        f"{audit.get('global_importable_rows_before_ventilation', 0)} lignes GLOBAL avant, "
        f"{audit.get('global_importable_rows_after_ventilation', 0)} apres ventilation."
    )

structure_df = pd.DataFrame(dashboard_data["charts"]["structure_decision"]).sort_values("value", ascending=False)
missing_df = pd.DataFrame(dashboard_data["charts"]["capex_sans_prix_chine"]).sort_values("capex", ascending=False).head(top_n)
coverage_df = pd.DataFrame(dashboard_data["charts"]["matrice_audit_sourcing"]).sort_values(
    "capex_importable", ascending=False
).head(top_n)
import_rate_df = pd.DataFrame(dashboard_data["charts"]["taux_import_par_famille"]).sort_values(
    "taux_import", ascending=False
).head(top_n)
building_df = pd.DataFrame(dashboard_data["charts"].get("importable_par_batiment", [])).sort_values(
    "capex_importable", ascending=False
).head(top_n)
level_df = pd.DataFrame(dashboard_data["charts"].get("importable_par_niveau", [])).sort_values(
    "capex_importable", ascending=False
).head(top_n)

top_row_left, top_row_right = st.columns(2)

with top_row_left:
    st.markdown("## Structure de decision")
    if not structure_df.empty:
        st.plotly_chart(
            build_donut_chart(
                structure_df,
                names="decision",
                values="value",
                title="Structure IMPORT vs LOCAL",
            ),
            use_container_width=True,
        )

with top_row_right:
    st.markdown("## CAPEX sans prix Chine")
    if not missing_df.empty:
        st.plotly_chart(
            build_improved_bar_chart(
                missing_df,
                x="famille",
                y="capex",
                title="Familles sans prix Chine",
                horizontal=True,
            ),
            use_container_width=True,
        )

st.markdown("## Matrice audit sourcing")
if not coverage_df.empty:
    st.plotly_chart(
        build_improved_scatter_chart(
            coverage_df,
            title="Couverture sourcing par famille",
        ),
        use_container_width=True,
    )

st.markdown("## Taux import par famille")
if not import_rate_df.empty:
    st.plotly_chart(
        build_improved_bar_chart(
            import_rate_df,
            x="famille_label",
            y="taux_import",
            title="Taux import par famille",
        ),
        use_container_width=True,
    )

ventilated_left, ventilated_right = st.columns(2)

with ventilated_left:
    st.markdown("## Importable par batiment")
    if not building_df.empty:
        st.plotly_chart(
            build_improved_bar_chart(
                building_df,
                x="batiment",
                y="capex_importable",
                title="Potentiel importable par batiment",
                horizontal=True,
            ),
            use_container_width=True,
        )

with ventilated_right:
    st.markdown("## Importable par niveau")
    if not level_df.empty:
        st.plotly_chart(
            build_improved_bar_chart(
                level_df,
                x="niveau",
                y="capex_importable",
                title="Potentiel importable par niveau",
            ),
            use_container_width=True,
        )

st.markdown("## Tableau de controle")
control_df = build_control_rows(dashboard_data)
control_df["Valeur"] = control_df["Valeur"].map(lambda value: f"{value:,.0f}".replace(",", " "))
st.dataframe(control_df, use_container_width=True, height=260, hide_index=True)

st.markdown("## Detail audit sourcing")
detail_df = coverage_df.rename(
    columns={
        "famille_label": "Famille",
        "capex_importable": "CAPEX importable",
        "capex_import_ttc": "CAPEX import TTC",
        "couverture": "CAPEX couvert",
        "articles_sans_prix": "Articles sans prix",
        "taux_couverture": "Taux couverture",
    }
)
if not detail_df.empty:
    for column in ["CAPEX importable", "CAPEX import TTC", "CAPEX couvert"]:
        detail_df[column] = detail_df[column].map(lambda value: f"{value:,.0f}".replace(",", " "))
    detail_df["Taux couverture"] = detail_df["Taux couverture"].map(
        lambda value: f"{value * 100:,.1f} %".replace(",", " ")
    )
    st.dataframe(detail_df, use_container_width=True, height=400, hide_index=True)
