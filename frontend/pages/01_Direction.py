"""
Dashboard Direction avec vrai cross-filter interactif.

Cette page utilise `streamlit-plotly-events` pour reproduire un
comportement proche de Power BI :

- clic sur LOT -> filtre les familles, articles et KPI
- clic sur FAMILLE -> filtre les articles et KPI
- clic sur ARTICLE -> zoom final sur l'article
- reset global des filtres
"""

from __future__ import annotations

import sys
import textwrap
import unicodedata
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.api_client import fetch_direction_dataset
from frontend.ui import (
    apply_dashboard_style,
    format_currency,
    format_percentage,
    render_decision_split,
    render_kpi_cards,
    render_proportional_bars,
    show_api_error,
)

try:
    from streamlit_plotly_events import plotly_events
except ImportError:  # pragma: no cover - handled visually in Streamlit
    plotly_events = None


st.set_page_config(page_title="Dashboard Direction", page_icon="DIR", layout="wide")
apply_dashboard_style("Dashboard Direction")


@st.cache_data(show_spinner=False)
def load_direction_dataframe() -> pd.DataFrame:
    """
    Charge le dataset unique du dashboard Direction depuis la source DQE d'origine enrichie.
    """
    payload, error_message = fetch_direction_dataset()
    if error_message:
        raise RuntimeError(error_message)

    dataframe = pd.DataFrame(payload["items"])
    if dataframe.empty:
        return dataframe

    numeric_columns = ["montant_local", "capex_optimise_line", "economie_line", "lot_number"]
    for column in numeric_columns:
        if column in dataframe.columns:
            dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce").fillna(0.0)

    if "designation_normalized" not in dataframe.columns and "designation" in dataframe.columns:
        dataframe["designation_normalized"] = dataframe["designation"].fillna("").astype(str).str.upper()

    if "decision_label" not in dataframe.columns:
        dataframe["decision_label"] = "LOCAL"

    if "source_name" not in dataframe.columns:
        dataframe["source_name"] = "PDF_DQE"

    return dataframe


def initialize_direction_state() -> None:
    """
    Initialise les filtres globaux et le drill-down par clic.
    """
    if "direction_filters" not in st.session_state:
        st.session_state.direction_filters = {
            "lot": None,
            "famille": None,
            "article": None,
            "lot_ids": [],
            "famille_ids": [],
            "niveau_ids": [],
            "batiment_ids": [],
            "top_n": 10,
        }


def filter_data(dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Applique tous les filtres stockes dans le state Streamlit.
    """
    filters = st.session_state.direction_filters
    filtered_dataframe = dataframe.copy()

    if filters["lot_ids"]:
        filtered_dataframe = filtered_dataframe[
            filtered_dataframe["lot_number"].isin(filters["lot_ids"])
        ]

    if filters["famille_ids"]:
        filtered_dataframe = filtered_dataframe[
            filtered_dataframe["fam_article_id"].isin(filters["famille_ids"])
        ]

    if filters["niveau_ids"]:
        filtered_dataframe = filtered_dataframe[
            filtered_dataframe["niveau_id"].isin(filters["niveau_ids"])
        ]

    if filters["batiment_ids"]:
        filtered_dataframe = filtered_dataframe[
            filtered_dataframe["batiment_id"].isin(filters["batiment_ids"])
        ]

    if filters["lot"]:
        filtered_dataframe = filtered_dataframe[
            filtered_dataframe["lot_label"] == filters["lot"]
        ]

    if filters["famille"]:
        filtered_dataframe = filtered_dataframe[
            filtered_dataframe["famille_label"] == filters["famille"]
        ]

    if filters["article"]:
        filtered_dataframe = filtered_dataframe[
            filtered_dataframe["designation"] == filters["article"]
        ]

    return filtered_dataframe


def normalize_text(value: str | None) -> str:
    """
    Normalise les libelles pour les rapprochements article et les filtres visuels.
    """
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(normalized.upper().split())


def compute_kpis(dataframe: pd.DataFrame) -> dict[str, float]:
    """
    Recalcule les KPI sur le perimetre filtre.
    """
    if dataframe.empty:
        return {
            "capex_brut": 0.0,
            "capex_opt": 0.0,
            "economie": 0.0,
            "taux": 0.0,
        }

    kpi_dataframe = dataframe.copy()

    if "capex_optimise_line" in kpi_dataframe.columns:
        kpi_dataframe["cout_opt"] = pd.to_numeric(
            kpi_dataframe["capex_optimise_line"], errors="coerce"
        ).fillna(0.0)
    else:
        kpi_dataframe["cout_opt"] = kpi_dataframe.apply(
            lambda row: row["montant_import"]
            if row.get("decision_label") == "IMPORT" and row.get("montant_import", 0) > 0
            else row["montant_local"],
            axis=1,
        )

    capex_brut = float(kpi_dataframe["montant_local"].sum())
    capex_opt = float(kpi_dataframe["cout_opt"].sum())
    economie = capex_brut - capex_opt
    taux = economie / capex_brut if capex_brut else 0.0

    return {
        "capex_brut": capex_brut,
        "capex_opt": capex_opt,
        "economie": economie,
        "taux": taux,
    }


def detect_direction_anomalies(dataframe: pd.DataFrame) -> list[str]:
    """
    Signale les anomalies visibles dans la source detaillee.
    """
    anomalies: list[str] = []

    duplicated_rows = int(dataframe.duplicated(subset=["code_bpu", "designation"]).sum())
    if duplicated_rows:
        anomalies.append(
            f"Doublons detectes dans la source DQE : {duplicated_rows} lignes sur code_bpu + designation."
        )

    missing_local_amounts = int(dataframe["montant_local"].isna().sum())
    if missing_local_amounts:
        anomalies.append(f"Valeurs nulles sur montant_local : {missing_local_amounts}.")

    if "batiment_label" in dataframe.columns:
        unresolved_buildings = int((dataframe["batiment_label"].fillna("Global") == "Global").sum())
        if unresolved_buildings:
            anomalies.append(
                f"Lignes sans batiment precis deduit depuis la source DQE : {unresolved_buildings}."
            )

    if "niveau_label" in dataframe.columns:
        unresolved_levels = int((dataframe["niveau_label"].fillna("GLOBAL") == "GLOBAL").sum())
        if unresolved_levels:
            anomalies.append(
                f"Lignes sans niveau precis deduit depuis la source DQE : {unresolved_levels}."
            )

    if "optimization_ratio" in dataframe.columns:
        optimization_ratio = pd.to_numeric(dataframe["optimization_ratio"], errors="coerce")
        abnormal_ratio_count = int(((optimization_ratio < 0) | (optimization_ratio > 1.5)).sum())
        if abnormal_ratio_count:
            anomalies.append(
                f"Ratios d'optimisation anormaux detectes : {abnormal_ratio_count} lignes."
            )

    return anomalies


def wrap_labels(series: pd.Series, width: int = 22) -> pd.Series:
    """
    Coupe les libelles longs sur plusieurs lignes.
    """
    return series.fillna("").map(lambda value: "<br>".join(textwrap.wrap(str(value), width=width)) or str(value))


def _recommended_chart_height(dataframe: pd.DataFrame, horizontal: bool = False) -> int:
    row_count = max(len(dataframe.index), 1)
    if horizontal:
        return max(440, min(980, 120 + row_count * 34))
    return max(440, min(780, 360 + row_count * 12))


def format_dataframe_for_display(dataframe: pd.DataFrame, numeric_columns: list[str]) -> pd.DataFrame:
    """
    Formate le tableau final pour un affichage plus lisible.
    """
    formatted = dataframe.copy()
    for column in numeric_columns:
        if column in formatted.columns:
            formatted[column] = pd.to_numeric(formatted[column], errors="coerce").fillna(0.0)
            formatted[column] = formatted[column].map(lambda value: f"{value:,.0f}".replace(",", " "))
    return formatted


def build_chart_audit_rows(filtered_dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Petit tableau de controle des graphiques affiches.
    """
    rows = [
        {
            "Graphique": "CAPEX par LOT",
            "Source": float(filtered_dataframe.groupby("lot_label")["montant_local"].sum().sum()),
            "Valeur affichee": float(filtered_dataframe["montant_local"].sum()),
        },
        {
            "Graphique": "CAPEX brut par FAMILLE",
            "Source": float(filtered_dataframe.groupby("famille_label")["montant_local"].sum().sum()),
            "Valeur affichee": float(filtered_dataframe["montant_local"].sum()),
        },
        {
            "Graphique": "Structure IMPORT / LOCAL sur CAPEX brut",
            "Source": float(filtered_dataframe.groupby("decision_label")["montant_local"].sum().sum()),
            "Valeur affichee": float(filtered_dataframe["montant_local"].sum()),
        },
    ]
    audit_dataframe = pd.DataFrame(rows)
    audit_dataframe["Ecart"] = audit_dataframe["Valeur affichee"] - audit_dataframe["Source"]
    audit_dataframe["OK/KO"] = audit_dataframe["Ecart"].map(
        lambda value: "OK" if abs(value) < 0.0001 else "KO"
    )
    return audit_dataframe


def reset_cross_filters() -> None:
    """
    Reinitialise uniquement le drill-down par clic.
    """
    st.session_state.direction_filters["lot"] = None
    st.session_state.direction_filters["famille"] = None
    st.session_state.direction_filters["article"] = None


def build_filter_options(dataframe: pd.DataFrame, value_column: str, label_column: str) -> list[dict]:
    """
    Construit des options stables pour les widgets de filtres.
    """
    if dataframe.empty:
        return []
    options_dataframe = (
        dataframe[[value_column, label_column]]
        .dropna()
        .drop_duplicates()
        .sort_values(label_column)
    )
    return options_dataframe.rename(
        columns={value_column: "value", label_column: "label"}
    ).to_dict(orient="records")


def migrate_legacy_global_filters(dataframe: pd.DataFrame) -> None:
    """
    Convertit d'anciens filtres stockes par libelle vers des identifiants stables.
    """
    filters = st.session_state.direction_filters

    if "familles" in filters and filters["familles"] and not filters.get("famille_ids"):
        famille_map = (
            dataframe[["fam_article_id", "famille_label"]]
            .dropna()
            .drop_duplicates()
            .set_index("famille_label")["fam_article_id"]
            .to_dict()
        )
        filters["famille_ids"] = [famille_map[label] for label in filters["familles"] if label in famille_map]
        filters.pop("familles", None)

    if "niveaux" in filters and filters["niveaux"] and not filters.get("niveau_ids"):
        niveau_map = (
            dataframe[["niveau_id", "niveau_label"]]
            .dropna()
            .drop_duplicates()
            .set_index("niveau_label")["niveau_id"]
            .to_dict()
        )
        filters["niveau_ids"] = [niveau_map[label] for label in filters["niveaux"] if label in niveau_map]
        filters.pop("niveaux", None)

    if "batiments" in filters and filters["batiments"] and not filters.get("batiment_ids"):
        batiment_map = (
            dataframe[["batiment_id", "batiment_label"]]
            .dropna()
            .drop_duplicates()
            .set_index("batiment_label")["batiment_id"]
            .to_dict()
        )
        filters["batiment_ids"] = [batiment_map[label] for label in filters["batiments"] if label in batiment_map]
        filters.pop("batiments", None)

    for key in ("famille_ids", "niveau_ids", "batiment_ids"):
        filters.setdefault(key, [])


def labels_for_values(options: list[dict], values: list) -> str:
    """
    Retourne les libelles associes aux valeurs selectionnees.
    """
    label_map = {option["value"]: option["label"] for option in options}
    labels = [label_map[value] for value in values if value in label_map]
    return ", ".join(labels) if labels else "aucun"


def option_label_lookup(options: list[dict]) -> dict:
    """
    Construit un mapping valeur -> libelle pour les widgets.
    """
    return {option["value"]: option["label"] for option in options}


def build_bar_figure(
    dataframe: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    selected_value: str | None = None,
    horizontal: bool = False,
    scale_millions: bool = False,
):
    """
    Construit un graphique a barres avec mise en evidence de la selection.
    """
    chart_dataframe = dataframe.copy()
    chart_dataframe["is_selected"] = chart_dataframe[x].eq(selected_value)
    chart_dataframe[f"{x}_display"] = wrap_labels(chart_dataframe[x], width=20)
    original_value_column = "_original_value"
    if scale_millions and y in chart_dataframe.columns:
        chart_dataframe[original_value_column] = pd.to_numeric(
            chart_dataframe[y], errors="coerce"
        ).fillna(0.0)
        chart_dataframe[y] = chart_dataframe[original_value_column] / 1_000_000

    if horizontal:
        figure = px.bar(
            chart_dataframe,
            x=y,
            y=f"{x}_display",
            orientation="h",
            title=title,
            color="is_selected",
            color_discrete_map={True: "#22c55e", False: "#0ea5e9"},
            custom_data=[x, original_value_column] if scale_millions else [x],
        )
    else:
        figure = px.bar(
            chart_dataframe,
            x=f"{x}_display",
            y=y,
            title=title,
            color="is_selected",
            color_discrete_map={True: "#22c55e", False: "#0ea5e9"},
            custom_data=[x, original_value_column] if scale_millions else [x],
        )

    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
        height=_recommended_chart_height(chart_dataframe, horizontal=horizontal),
        margin=dict(
            l=150 if horizontal else 42,
            r=32,
            t=58,
            b=118 if not horizontal else 40,
        ),
        showlegend=False,
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
            figure.update_traces(
                hovertemplate="%{customdata[0]}<br>Valeur=%{customdata[1]:,.0f} FCFA<extra></extra>",
            )
        else:
            figure.update_traces(
                hovertemplate="%{customdata[0]}<br>Valeur=%{x:,.0f}<extra></extra>",
            )
    else:
        figure.update_yaxes(
            tickformat=",.0f",
            separatethousands=True,
            exponentformat="none",
            showexponent="none",
        )
        if scale_millions:
            figure.update_yaxes(title_text=f"{y} (M FCFA)")
            figure.update_traces(
                hovertemplate="%{customdata[0]}<br>Valeur=%{customdata[1]:,.0f} FCFA<extra></extra>",
            )
        else:
            figure.update_traces(
                hovertemplate="%{customdata[0]}<br>Valeur=%{y:,.0f}<extra></extra>",
            )
    return figure


def build_pie_figure(dataframe: pd.DataFrame, title: str):
    """
    Construit le donut chart de structure IMPORT / LOCAL.
    """
    figure = px.pie(
        dataframe,
        names="decision_label",
        values="value",
        hole=0.58,
        title=title,
        color="decision_label",
        color_discrete_map={"IMPORT": "#00c2ff", "LOCAL": "#22c55e"},
    )
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
        height=460,
        margin=dict(l=32, r=32, t=58, b=32),
    )
    return figure


def apply_click_selection(selected_points: list[dict], level: str) -> None:
    """
    Met a jour le state selon le graphique clique.
    """
    if not selected_points:
        return

    selected_value = selected_points[0].get("x")
    if selected_value is None:
        selected_value = selected_points[0].get("y")
    if selected_value is None and selected_points[0].get("customdata"):
        selected_value = selected_points[0]["customdata"][0]

    if not selected_value:
        return

    filters = st.session_state.direction_filters

    if level == "lot":
        filters["lot"] = selected_value
        filters["famille"] = None
        filters["article"] = None
    elif level == "famille":
        filters["famille"] = selected_value
        filters["article"] = None
    elif level == "article":
        filters["article"] = selected_value


initialize_direction_state()

try:
    source_dataframe = load_direction_dataframe()
except RuntimeError as error:
    show_api_error(str(error))
    st.stop()

if plotly_events is None:
    st.error(
        "Le package `streamlit-plotly-events` est requis pour le cross-filter. "
        "Installe-le avec `pip install streamlit-plotly-events`."
    )
    st.stop()

if source_dataframe.empty:
    st.warning("Aucune donnee disponible pour le dashboard Direction.")
    st.stop()

filters = st.session_state.direction_filters
migrate_legacy_global_filters(source_dataframe)

lot_options = build_filter_options(source_dataframe, "lot_number", "lot_label")
famille_options = build_filter_options(source_dataframe, "fam_article_id", "famille_label")
niveau_options = build_filter_options(source_dataframe, "niveau_id", "niveau_label")
batiment_options = build_filter_options(source_dataframe, "batiment_id", "batiment_label")
lot_label_lookup = option_label_lookup(lot_options)
famille_label_lookup = option_label_lookup(famille_options)
niveau_label_lookup = option_label_lookup(niveau_options)
batiment_label_lookup = option_label_lookup(batiment_options)

st.markdown("### Filtres globaux")
filter_col_1, filter_col_2, filter_col_3, filter_col_4 = st.columns(4)

with filter_col_1:
    filters["lot_ids"] = st.multiselect(
        "LOT",
        options=[option["value"] for option in lot_options],
        default=filters["lot_ids"],
        format_func=lambda value: lot_label_lookup.get(value, str(value)),
    )

with filter_col_2:
    filters["famille_ids"] = st.multiselect(
        "FAMILLE ARTICLE",
        options=[option["value"] for option in famille_options],
        default=filters["famille_ids"],
        format_func=lambda value: famille_label_lookup.get(value, str(value)),
    )

with filter_col_3:
    filters["niveau_ids"] = st.multiselect(
        "NIVEAU",
        options=[option["value"] for option in niveau_options],
        default=filters["niveau_ids"],
        format_func=lambda value: niveau_label_lookup.get(value, str(value)),
    )

with filter_col_4:
    filters["batiment_ids"] = st.multiselect(
        "BATIMENT",
        options=[option["value"] for option in batiment_options],
        default=filters["batiment_ids"],
        format_func=lambda value: batiment_label_lookup.get(value, str(value)),
    )

control_col_1, control_col_2 = st.columns([1, 1])
with control_col_1:
    filters["top_n"] = st.slider(
        "Top articles",
        min_value=5,
        max_value=20,
        value=int(filters["top_n"]),
    )
with control_col_2:
    st.markdown(" ")
    if st.button("Reset filtres", use_container_width=True):
        st.session_state.direction_filters = {
            "lot": None,
            "famille": None,
            "article": None,
            "lot_ids": [],
            "famille_ids": [],
            "niveau_ids": [],
            "batiment_ids": [],
            "top_n": 10,
        }
        st.rerun()

filtered_dataframe = filter_data(source_dataframe)
kpis = compute_kpis(filtered_dataframe)
st.success("Source de reference du dashboard Direction : DQE d'origine enrichi pour le drill-down.")
st.info("Les montants affiches dans les graphiques Direction sont ancres sur le CAPEX brut de la source DQE.")

render_kpi_cards(
    [
        {
            "label": "CAPEX Brut",
            "value": format_currency(kpis["capex_brut"]),
            "caption": "Source KPI : DQE d'origine",
        },
        {
            "label": "CAPEX Optimise",
            "value": format_currency(kpis["capex_opt"]),
            "caption": "Projection IMPORT / LOCAL sur la source DQE",
        },
        {
            "label": "Economie",
            "value": format_currency(kpis["economie"]),
            "caption": "CAPEX brut - CAPEX optimise",
        },
        {
            "label": "Taux",
            "value": format_percentage(kpis["taux"]),
            "caption": "KPI recalcule en temps reel",
        },
    ]
)

st.info(
    "Filtres actifs : "
    f"lot={filters['lot'] or 'aucun'} | "
    f"famille={filters['famille'] or 'aucune'} | "
    f"article={filters['article'] or 'aucun'} | "
    f"niveau={labels_for_values(niveau_options, filters['niveau_ids'])} | "
    f"batiment={labels_for_values(batiment_options, filters['batiment_ids'])}"
)

anomalies = detect_direction_anomalies(source_dataframe)
with st.expander("Audit rapide des donnees source", expanded=False):
    st.caption("Source auditee : dataset DQE d'origine enrichi pour le dashboard Direction.")
    if anomalies:
        for anomaly in anomalies:
            st.warning(anomaly)
    else:
        st.success("Aucune anomalie immediate detectee sur la source detaillee.")

lot_dataframe = (
    filtered_dataframe.groupby("lot_label", as_index=False)
    .agg(capex=("montant_local", "sum"))
    .sort_values("capex", ascending=False)
    .head(int(filters["top_n"]))
)

famille_dataframe = (
    filtered_dataframe.groupby("famille_label", as_index=False)
    .agg(economie=("economie_line", "sum"))
    .sort_values("economie", ascending=False)
)

article_dataframe = (
    filtered_dataframe.groupby("designation", as_index=False)
    .agg(economie=("economie_line", "sum"))
    .sort_values("economie", ascending=False)
    .head(int(filters["top_n"]))
)

decision_dataframe = (
    filtered_dataframe.groupby("decision_label", as_index=False)
    .agg(value=("capex_optimise_line", "sum"))
    .sort_values("value", ascending=False)
)

chart_col_1, chart_col_2 = st.columns(2)

with chart_col_1:
    render_proportional_bars(
        lot_dataframe,
        label_column="lot_label",
        value_column="capex",
        title="Analyse par LOT",
        unit_suffix="FCFA",
    )

with chart_col_2:
    render_decision_split(
        decision_dataframe.rename(columns={"decision_label": "decision"}),
        label_column="decision",
        value_column="value",
        title="Structure de decision",
    )

famille_section_df = filter_data(source_dataframe)
famille_dataframe = (
    famille_section_df.groupby("famille_label", as_index=False)
    .agg(capex=("montant_local", "sum"))
    .sort_values("capex", ascending=False)
)

render_proportional_bars(
    famille_dataframe,
    label_column="famille_label",
    value_column="capex",
    title="Analyse par FAMILLE",
    unit_suffix="FCFA",
)

article_section_df = filter_data(source_dataframe)
article_dataframe = (
    article_section_df.groupby("designation", as_index=False)
    .agg(capex=("montant_local", "sum"))
    .sort_values("capex", ascending=False)
    .head(int(filters["top_n"]))
)

render_proportional_bars(
    article_dataframe,
    label_column="designation",
    value_column="capex",
    title="Analyse par ARTICLE",
    unit_suffix="FCFA",
)

st.markdown("## Top articles de la source")
current_filtered_dataframe = filter_data(source_dataframe)
top_articles_dataframe = (
    current_filtered_dataframe
    .groupby(["code_bpu", "designation"], as_index=False)
    .agg(
        capex_brut=("montant_local", "sum"),
        capex_optimise=("capex_optimise_line", "sum"),
        economie=("economie_line", "sum"),
    )
    .sort_values("capex_brut", ascending=False)
    .head(int(filters["top_n"]))
)

if top_articles_dataframe.empty:
    st.info("Aucun article disponible dans le perimetre courant.")
else:
    top_articles_display = format_dataframe_for_display(
        top_articles_dataframe.sort_values("economie", ascending=False),
        ["capex_brut", "capex_optimise", "economie"],
    )
    st.dataframe(
        top_articles_display,
        use_container_width=True,
        height=400,
        hide_index=True,
    )

st.markdown("## Tableau de controle")
chart_audit_dataframe = build_chart_audit_rows(current_filtered_dataframe)
chart_audit_display = format_dataframe_for_display(
    chart_audit_dataframe,
    ["Source", "Valeur affichee", "Ecart"],
)
st.dataframe(
    chart_audit_display,
    use_container_width=True,
    height=220,
    hide_index=True,
)

st.info("Les graphiques de synthese Direction utilisent maintenant un rendu proportionnel stable.")
