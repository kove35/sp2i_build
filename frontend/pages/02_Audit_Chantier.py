"""
Dashboard Audit Chantier.
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
    render_heat_grid,
    render_kpi_cards,
    render_proportional_bars,
    render_sidebar_filters,
    show_api_error,
)


st.set_page_config(page_title="Audit Chantier", page_icon="AUDIT", layout="wide")
apply_dashboard_style("Dashboard Audit Chantier")


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


def build_improved_heatmap(dataframe: pd.DataFrame, row: str, column: str, value: str, title: str):
    pivot_table = dataframe.pivot_table(
        index=row,
        columns=column,
        values=value,
        aggfunc="sum",
        fill_value=0,
    )
    figure = px.imshow(
        pivot_table,
        text_auto=".0f",
        aspect="auto",
        color_continuous_scale="Blues",
        title=title,
    )
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
        height=max(480, min(920, 180 + len(pivot_table.index) * 26)),
        margin=dict(l=110, r=32, t=58, b=108),
    )
    figure.update_xaxes(automargin=True, tickangle=-32, tickfont=dict(size=11))
    figure.update_yaxes(automargin=True, tickfont=dict(size=11))
    return figure


def build_chart_control_rows(dashboard_data: dict) -> pd.DataFrame:
    charts = dashboard_data["charts"]
    rows = [
        {
            "Graphique": "Cout total par lot",
            "Valeur": float(sum(item["capex"] for item in charts["cout_par_lot"])),
        },
        {
            "Graphique": "Cout par batiment",
            "Valeur": float(sum(item["capex"] for item in charts["cout_par_batiment"])),
        },
        {
            "Graphique": "Cout par niveau",
            "Valeur": float(sum(item["capex"] for item in charts["cout_par_niveau"])),
        },
        {
            "Graphique": "Repartition LOT x NIVEAU",
            "Valeur": float(sum(item["capex"] for item in charts["repartition_lot_niveau"])),
        },
    ]
    return pd.DataFrame(rows).sort_values("Valeur", ascending=False)


filter_options, filter_error = fetch_filter_options()
if filter_error:
    show_api_error(filter_error)
    st.stop()

active_filters = render_sidebar_filters(filter_options)
render_active_filters(active_filters, filter_options)

top_n = st.slider("Top N elements affiches", min_value=5, max_value=20, value=10)

dashboard_data, data_error = fetch_dashboard_data("kpi_chantier", active_filters)
if data_error:
    show_api_error(data_error)
    st.stop()

kpis = dashboard_data["kpis"]
audit_info = dashboard_data.get("audit", {})
render_kpi_cards(
    [
        {
            "label": "CAPEX Brut",
            "value": format_currency(kpis["capex_brut"]),
            "caption": "Source detaillee : build_fact_metre",
        },
        {
            "label": "CAPEX Optimise",
            "value": format_currency(kpis["capex_optimise"]),
            "caption": "Montant retenu apres decision IMPORT / LOCAL",
        },
        {
            "label": "Economie",
            "value": format_currency(kpis["economie"]),
            "caption": f"Taux : {format_percentage(kpis['taux_optimisation'])}",
        },
    ]
)

st.warning(
    "Source reelle du dashboard : schema analytique `build_fact_metre`. "
    "Ce dashboard ne lit pas directement la table `fact_metre` historique SQLite."
)
if audit_info:
    st.info(
        "Ventilation analytique par niveau : "
        f"{audit_info.get('global_rows_before_ventilation', 0)} lignes GLOBAL avant, "
        f"{audit_info.get('global_rows_after_ventilation', 0)} apres ventilation."
    )
st.info(
    "Contexte affiché : "
    f"lot={active_filters.get('lot_id') or 'Tous'} | "
    f"famille={active_filters.get('fam_article_id') or 'Toutes'} | "
    f"batiment={active_filters.get('batiment_id') or 'Tous'} | "
    f"niveau={active_filters.get('niveau_id') or 'Tous'}"
)

lot_df = pd.DataFrame(dashboard_data["charts"]["cout_par_lot"]).sort_values("capex", ascending=False).head(top_n)
building_df = pd.DataFrame(dashboard_data["charts"]["cout_par_batiment"]).sort_values("capex", ascending=False).head(top_n)
level_df = pd.DataFrame(dashboard_data["charts"]["cout_par_niveau"]).sort_values("capex", ascending=False).head(top_n)
lot_level_df = pd.DataFrame(dashboard_data["charts"]["repartition_lot_niveau"]).sort_values("capex", ascending=False)

top_row_left, top_row_right = st.columns(2)

with top_row_left:
    st.markdown("## Analyse par LOT")
    if not lot_df.empty:
        render_proportional_bars(
            lot_df,
            label_column="lot",
            value_column="capex",
            title="Cout total par lot",
            unit_suffix="FCFA",
        )

with top_row_right:
    st.markdown("## Analyse par BÂTIMENT")
    if not building_df.empty:
        render_proportional_bars(
            building_df,
            label_column="batiment",
            value_column="capex",
            title="Cout par batiment",
            unit_suffix="FCFA",
        )

st.markdown("## Analyse par NIVEAU")
if not level_df.empty:
    render_proportional_bars(
        level_df,
        label_column="niveau",
        value_column="capex",
        title="Cout par niveau",
        unit_suffix="FCFA",
    )

st.markdown("## Répartition LOT x NIVEAU")
if not lot_level_df.empty:
    render_heat_grid(
        lot_level_df,
        row_column="lot_label",
        column_column="niveau_label",
        value_column="capex",
        title="Repartition CAPEX par lot et niveau",
        unit_suffix="FCFA",
    )

st.markdown("## Tableau de contrôle")
chart_control_df = build_chart_control_rows(dashboard_data)
chart_control_df["Valeur"] = chart_control_df["Valeur"].map(lambda value: f"{value:,.0f}".replace(",", " "))
st.dataframe(chart_control_df, use_container_width=True, height=220, hide_index=True)

st.markdown("## Détail des agrégats")
detail_df = lot_level_df.rename(
    columns={
        "lot_label": "Lot",
        "niveau_label": "Niveau",
        "capex": "CAPEX",
    }
)
if not detail_df.empty:
    detail_df = detail_df.sort_values("CAPEX", ascending=False).head(max(top_n * 2, 10))
    detail_df["CAPEX"] = detail_df["CAPEX"].map(lambda value: f"{value:,.0f}".replace(",", " "))
    st.dataframe(detail_df, use_container_width=True, height=400, hide_index=True)

st.info("Les graphiques de synthese Chantier utilisent maintenant un rendu proportionnel stable.")
