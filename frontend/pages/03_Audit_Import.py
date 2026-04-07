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
try:
    from streamlit_plotly_events import plotly_events
except ImportError:  # pragma: no cover - handled visually in Streamlit
    plotly_events = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.api_client import fetch_dashboard_data, fetch_filter_options
from frontend.ui import (
    apply_dashboard_style,
    format_currency,
    format_percentage,
    render_active_filters,
    render_decision_split,
    render_kpi_cards,
    render_proportional_bars,
    render_sourcing_matrix,
    render_sidebar_filters,
    show_api_error,
)


st.set_page_config(page_title="Audit Import", page_icon="IMPORT", layout="wide")
apply_dashboard_style("Dashboard Audit Import")


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


def wrap_labels(series: pd.Series, width: int = 22) -> pd.Series:
    return series.fillna("").map(lambda value: "<br>".join(textwrap.wrap(str(value), width=width)) or str(value))


def _recommended_chart_height(dataframe: pd.DataFrame, horizontal: bool = False) -> int:
    row_count = max(len(dataframe.index), 1)
    if horizontal:
        return max(440, min(980, 120 + row_count * 34))
    return max(440, min(780, 360 + row_count * 12))


def build_improved_bar_chart(
    dataframe: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    horizontal: bool = False,
    scale_millions: bool = False,
):
    chart_df = dataframe.copy()
    chart_df[f"{x}_display"] = wrap_labels(chart_df[x], width=20)
    original_value_column = "_original_value"
    if scale_millions and y in chart_df.columns:
        chart_df[original_value_column] = pd.to_numeric(chart_df[y], errors="coerce").fillna(0.0)
        chart_df[y] = chart_df[original_value_column] / 1_000_000

    if horizontal:
        figure = px.bar(
            chart_df,
            x=y,
            y=f"{x}_display",
            orientation="h",
            title=title,
            custom_data=[x, original_value_column] if scale_millions else [x],
        )
    else:
        figure = px.bar(
            chart_df,
            x=f"{x}_display",
            y=y,
            title=title,
            custom_data=[x, original_value_column] if scale_millions else [x],
        )

    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
        height=_recommended_chart_height(chart_df, horizontal=horizontal),
        margin=dict(
            l=150 if horizontal else 42,
            r=32,
            t=58,
            b=118 if not horizontal else 40,
        ),
        xaxis_tickangle=-32 if not horizontal else 0,
        bargap=0.22,
        uniformtext_minsize=10,
        uniformtext_mode="hide",
    )
    figure.update_xaxes(
        automargin=True,
        title_standoff=16,
        tickfont=dict(size=11),
        gridcolor="rgba(148, 163, 184, 0.18)",
    )
    figure.update_yaxes(
        automargin=True,
        title_standoff=16,
        tickfont=dict(size=11),
        gridcolor="rgba(148, 163, 184, 0.12)",
    )
    if horizontal:
        figure.update_xaxes(
            tickformat=",.0f",
            separatethousands=True,
            exponentformat="none",
            showexponent="none",
        )
        if scale_millions:
            figure.update_xaxes(title_text=f"{y} (M FCFA)")
            hover_template = "%{customdata[0]}<br>Valeur=%{customdata[1]:,.0f} FCFA<extra></extra>"
        else:
            hover_template = "%{customdata[0]}<br>Valeur=%{x:,.0f}<extra></extra>"
    else:
        figure.update_yaxes(
            tickformat=",.0f",
            separatethousands=True,
            exponentformat="none",
            showexponent="none",
        )
        if scale_millions:
            figure.update_yaxes(title_text=f"{y} (M FCFA)")
            hover_template = "%{customdata[0]}<br>Valeur=%{customdata[1]:,.0f} FCFA<extra></extra>"
        else:
            hover_template = "%{customdata[0]}<br>Valeur=%{y:,.0f}<extra></extra>"
    figure.update_traces(
        marker_color="#7cc4ff",
        marker_line_color="#dbeafe",
        marker_line_width=1.2,
        opacity=0.95,
        text=chart_df[y].map(
            lambda value: f"{value:,.1f} M" if scale_millions else f"{value:,.0f}"
        ),
        textposition="inside",
        insidetextanchor="end",
        textfont=dict(color="#f8fafc", size=12),
        hovertemplate=hover_template,
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
        custom_data=["famille_label"],
    )
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
        height=520,
        margin=dict(l=78, r=32, t=58, b=78),
    )
    figure.update_xaxes(automargin=True, title_standoff=16, tickfont=dict(size=11))
    figure.update_yaxes(automargin=True, title_standoff=16, tickfont=dict(size=11))
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
        render_decision_split(
            structure_df,
            label_column="decision",
            value_column="value",
            title="Structure IMPORT vs LOCAL",
        )

with top_row_right:
    st.markdown("## CAPEX sans prix Chine")
    if not missing_df.empty:
        render_proportional_bars(
            missing_df,
            label_column="famille",
            value_column="capex",
            title="Familles sans prix Chine",
            unit_suffix="FCFA",
        )

st.markdown("## Matrice audit sourcing")
if not coverage_df.empty:
    render_sourcing_matrix(
        coverage_df,
        label_column="famille_label",
        title="Couverture sourcing par famille",
    )

st.markdown("## Taux import par famille")
if not import_rate_df.empty:
    render_proportional_bars(
        import_rate_df,
        label_column="famille_label",
        value_column="taux_import",
        title="Taux import par famille",
        percentage_mode=True,
    )

ventilated_left, ventilated_right = st.columns(2)

with ventilated_left:
    st.markdown("## Importable par batiment")
    if not building_df.empty:
        render_proportional_bars(
            building_df,
            label_column="batiment",
            value_column="capex_importable",
            title="Potentiel importable par batiment",
            unit_suffix="FCFA",
        )

with ventilated_right:
    st.markdown("## Importable par niveau")
    if not level_df.empty:
        render_proportional_bars(
            level_df,
            label_column="niveau",
            value_column="capex_importable",
            title="Potentiel importable par niveau",
            unit_suffix="FCFA",
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

st.info("Les graphiques de synthese Import utilisent maintenant un rendu proportionnel stable.")
