"""
Page de controle entre le DQE PDF source et la base analytique.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.api_client import (
    dqe_control_fetch_article_comparison,
    dqe_control_fetch_lot_comparison,
    dqe_control_fetch_source_files,
    dqe_control_fetch_summary,
    dqe_control_import,
    dqe_control_promote,
    dqe_control_refresh,
)
from frontend.ui import (
    apply_dashboard_style,
    format_currency,
    render_kpi_cards,
    render_proportional_bars,
    render_signed_bars,
    show_api_error,
)


st.set_page_config(
    page_title="Controle DQE PDF",
    page_icon="PDF",
    layout="wide",
)

apply_dashboard_style("Controle DQE PDF")

st.caption(
    "Cette page compare le DQE PDF de reference avec `build_fact_metre` "
    "pour identifier les ecarts de total, de designation et de granularite."
)


@st.cache_data(show_spinner=False)
def load_source_files() -> list[str]:
    payload, error_message = dqe_control_fetch_source_files()
    if error_message:
        raise RuntimeError(error_message)
    return payload["items"]


@st.cache_data(show_spinner=False)
def load_summary(source_file: str | None) -> dict:
    payload, error_message = dqe_control_fetch_summary(source_file=source_file)
    if error_message:
        raise RuntimeError(error_message)
    return payload


@st.cache_data(show_spinner=False)
def load_lot_comparison(source_file: str | None) -> pd.DataFrame:
    payload, error_message = dqe_control_fetch_lot_comparison(source_file=source_file)
    if error_message:
        raise RuntimeError(error_message)
    return pd.DataFrame(payload["items"])


@st.cache_data(show_spinner=False)
def load_article_comparison(source_file: str | None, lot_code: str | None) -> pd.DataFrame:
    payload, error_message = dqe_control_fetch_article_comparison(
        source_file=source_file,
        lot_code=lot_code,
    )
    if error_message:
        raise RuntimeError(error_message)
    return pd.DataFrame(payload["items"])


def clear_control_cache() -> None:
    load_source_files.clear()
    load_summary.clear()
    load_lot_comparison.clear()
    load_article_comparison.clear()


try:
    source_files = load_source_files()
except RuntimeError as error:
    show_api_error(str(error))
    st.stop()

selected_source_file = st.selectbox(
    "Source DQE PDF active",
    options=source_files if source_files else ["Aucune source importee"],
)
selected_source_value = None if selected_source_file == "Aucune source importee" else selected_source_file

toolbar_left, toolbar_center, toolbar_right = st.columns([1, 1, 2])
with toolbar_left:
    if st.button("Rafraichir depuis le PDF", use_container_width=True):
        with st.spinner("Import du PDF et regeneration des rapports..."):
            payload, error_message = dqe_control_refresh()
        if error_message:
            st.error(error_message)
        else:
            clear_control_cache()
            st.success(
                f"Controle regenere : {payload['lots_imported']} lots, "
                f"{payload['articles_imported']} lignes PDF, "
                f"{payload['compared_article_rows']} lignes comparees."
            )
            st.rerun()
with toolbar_center:
    with st.popover("Importer un nouveau DQE"):
        pdf_path_input = st.text_input(
            "Chemin complet du PDF",
            value="",
            placeholder=r"C:\Users\...\mon_dqe.pdf",
        )
        if st.button("Importer ce PDF", use_container_width=True):
            with st.spinner("Import du nouveau DQE PDF..."):
                payload, error_message = dqe_control_import(pdf_path=pdf_path_input or None)
            if error_message:
                st.error(error_message)
            else:
                clear_control_cache()
                st.success(
                    f"Import termine : {payload['source_file']} | "
                    f"{payload['lots_imported']} lots | {payload['articles_imported']} lignes."
                )
                st.rerun()
with toolbar_right:
    st.caption(
        "Tu peux soit recharger le PDF par defaut, soit importer un nouveau DQE PDF "
        "par chemin local avant de le promouvoir en projet analytique."
    )

try:
    summary = load_summary(selected_source_value)
    lot_comparison_df = load_lot_comparison(selected_source_value)
except RuntimeError as error:
    show_api_error(str(error))
    st.stop()

with st.expander("Promouvoir cette source en projet analytique"):
    default_project_code = (
        f"PDF_{Path(selected_source_value).stem}".upper().replace(" ", "_")
        if selected_source_value
        else "PDF_DQE"
    )
    default_project_name = (
        f"DQE PDF - {Path(selected_source_value).stem}" if selected_source_value else "DQE PDF"
    )
    promo_project_code = st.text_input("Code projet analytique", value=default_project_code)
    promo_project_name = st.text_input("Nom projet analytique", value=default_project_name)
    replace_existing = st.checkbox("Ecraser si le code projet existe deja", value=False)
    if st.button("Promouvoir en nouveau projet analytique", use_container_width=True):
        with st.spinner("Promotion vers le schema analytique SQLAlchemy..."):
            payload, error_message = dqe_control_promote(
                source_file=selected_source_value,
                project_code=promo_project_code,
                project_name=promo_project_name,
                replace_existing=replace_existing,
            )
        if error_message:
            st.error(error_message)
        else:
            st.session_state["analytics_selected_project_code"] = payload["project_code"]
            st.session_state["analytics_last_promoted_project"] = {
                "project_id": payload["project_id"],
                "project_code": payload["project_code"],
                "project_name": payload["project_name"],
                "fact_rows": payload["fact_rows"],
            }
            st.success(
                f"Projet cree : {payload['project_name']} ({payload['project_code']}) | "
                f"{payload['fact_rows']} lignes analytiques."
            )
            open_col_1, open_col_2 = st.columns([1.2, 2.8])
            with open_col_1:
                if st.button(
                    "Ouvrir le projet promu",
                    key="open_promoted_project",
                    use_container_width=True,
                ):
                    st.switch_page("pages/05_Analytics_SQLAlchemy.py")
            with open_col_2:
                st.caption(
                    "Ce bouton ouvre directement la page Analytics SQLAlchemy "
                    "sur le projet qui vient d'etre cree."
                )

render_kpi_cards(
    [
        {
            "label": "Lots importes",
            "value": str(summary["lots_imported"]),
            "caption": f"Source : {summary['source_file']}",
        },
        {
            "label": "Articles PDF",
            "value": str(summary["articles_imported"]),
            "caption": "Lignes detaillees extraites",
        },
        {
            "label": "Lots alignes",
            "value": str(summary["matching_lots"]),
            "caption": f"Lots en ecart : {summary['lots_with_gap']}",
        },
        {
            "label": "Ecarts article",
            "value": str(summary["article_rows_compared"]),
            "caption": (
                f"Absents base : {summary['missing_in_db']} | "
                f"Absents PDF : {summary['missing_in_pdf']}"
            ),
        },
    ]
)

if lot_comparison_df.empty:
    st.info("Aucun rapport de comparaison n'est disponible pour le moment.")
    st.stop()

lot_comparison_df["abs_ecart_ht"] = lot_comparison_df["ecart_base_ht_vs_pdf"].abs()

chart_col_1, chart_col_2 = st.columns(2)

with chart_col_1:
    top_gap_df = lot_comparison_df.sort_values("abs_ecart_ht", ascending=False).head(10)
    render_signed_bars(
        top_gap_df,
        label_column="lot_code",
        value_column="ecart_base_ht_vs_pdf",
        title="Ecart HT par lot (base analytique - PDF)",
        unit_suffix="FCFA",
    )

with chart_col_2:
    match_status_df = pd.DataFrame(
        [
            {"label": "Lots alignes", "value": int(lot_comparison_df["match_base_ht"].sum())},
            {
                "label": "Lots en ecart",
                "value": int((~lot_comparison_df["match_base_ht"]).sum()),
            },
        ]
    )
    render_proportional_bars(
        match_status_df,
        label_column="label",
        value_column="value",
        title="Statut de rapprochement des lots",
    )

st.subheader("Comparaison lot par lot")
display_lot_df = lot_comparison_df.copy()
display_lot_df["total_ht_pdf"] = display_lot_df["total_ht_pdf"].apply(format_currency)
display_lot_df["base_ht_db"] = display_lot_df["base_ht_db"].apply(format_currency)
display_lot_df["total_local_db"] = display_lot_df["total_local_db"].apply(format_currency)
display_lot_df["ecart_base_ht_vs_pdf"] = display_lot_df["ecart_base_ht_vs_pdf"].apply(format_currency)
display_lot_df["ecart_total_local_vs_pdf"] = display_lot_df["ecart_total_local_vs_pdf"].apply(format_currency)
st.dataframe(display_lot_df, use_container_width=True, hide_index=True)

available_lots = lot_comparison_df["lot_code"].dropna().sort_values().tolist()
selected_lot_code = st.selectbox(
    "Lot a analyser en detail",
    options=["Tous les lots"] + available_lots,
)

selected_lot_filter = None if selected_lot_code == "Tous les lots" else selected_lot_code

try:
    article_comparison_df = load_article_comparison(selected_source_value, selected_lot_filter)
except RuntimeError as error:
    show_api_error(str(error))
    st.stop()

if article_comparison_df.empty:
    st.info("Aucun ecart article/article n'est disponible pour ce lot.")
    st.stop()

view_col_1, view_col_2 = st.columns([1, 1])
with view_col_1:
    discrepancy_only = st.checkbox("Afficher uniquement les ecarts reels", value=True)
with view_col_2:
    only_missing = st.checkbox("Afficher uniquement les absences PDF / base", value=False)

filtered_article_df = article_comparison_df.copy()
if discrepancy_only:
    filtered_article_df = filtered_article_df[
        filtered_article_df["ecart_base_ht"].abs() >= 1.0
    ]
if only_missing:
    filtered_article_df = filtered_article_df[
        (~filtered_article_df["present_pdf"]) | (~filtered_article_df["present_db"])
    ]

top_article_gaps = (
    filtered_article_df.assign(abs_ecart=lambda df: df["ecart_base_ht"].abs())
    .sort_values("abs_ecart", ascending=False)
    .head(15)
)

if not top_article_gaps.empty:
    render_signed_bars(
        top_article_gaps,
        label_column="designation_normalized",
        value_column="ecart_base_ht",
        title="Plus grands ecarts article/article",
        unit_suffix="FCFA",
    )

st.subheader("Comparaison article par article")
display_article_df = filtered_article_df.copy()
for column in ["total_ht_pdf", "base_ht_db", "ecart_base_ht"]:
    display_article_df[column] = display_article_df[column].apply(format_currency)
st.dataframe(display_article_df, use_container_width=True, hide_index=True)
