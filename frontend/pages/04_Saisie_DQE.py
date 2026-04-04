"""
Page Streamlit de saisie DQE.
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.api_client import (
    create_article,
    delete_article,
    fetch_articles,
    fetch_filter_options,
    update_article,
)
from frontend.ui import apply_dashboard_style, format_currency, show_api_error


st.set_page_config(page_title="Saisie DQE", page_icon="DQE", layout="wide")
apply_dashboard_style("Saisie DQE")

st.markdown(
    """
    Interface de saisie rapide du DQE :

    - creation d'articles
    - calcul automatique des totaux
    - modification et suppression
    - filtre par lot et sous-lot
    """
)


def build_lot_label_map(filter_options: dict) -> dict[str, str]:
    """
    Construit un dictionnaire d'affichage :
    'LOT 1' -> 'LOT 1 - Gros oeuvre et demolition'
    """
    lot_label_map: dict[str, str] = {}
    for option in filter_options.get("lots", []):
        raw_lot = f"LOT {option['value']}"
        lot_label_map[raw_lot] = option["label"]
        lot_label_map[raw_lot.lower()] = option["label"]
        lot_label_map[raw_lot.title()] = option["label"]
    return lot_label_map


def display_lot_label(raw_lot: str, lot_label_map: dict[str, str]) -> str:
    """
    Retourne le libelle metier si connu.
    """
    return lot_label_map.get(raw_lot, lot_label_map.get(raw_lot.lower(), raw_lot))


def initialize_form_state() -> None:
    """
    Initialise l'etat local du formulaire.
    """
    if "dqe_edit_id" not in st.session_state:
        st.session_state.dqe_edit_id = None

    if "dqe_form_values" not in st.session_state:
        st.session_state.dqe_form_values = {
            "lot": "",
            "sous_lot": "",
            "designation": "",
            "unite": "U",
            "quantite": 1.0,
            "pu_local": 0.0,
            "pu_chine": 0.0,
        }


def reset_form() -> None:
    """
    Reinitialise le formulaire.
    """
    st.session_state.dqe_edit_id = None
    st.session_state.dqe_form_values = {
        "lot": "",
        "sous_lot": "",
        "designation": "",
        "unite": "U",
        "quantite": 1.0,
        "pu_local": 0.0,
        "pu_chine": 0.0,
    }


def load_article_into_form(article: dict) -> None:
    """
    Charge un article existant dans le formulaire.
    """
    st.session_state.dqe_edit_id = article["id"]
    st.session_state.dqe_form_values = {
        "lot": article["lot"],
        "sous_lot": article["sous_lot"],
        "designation": article["designation"],
        "unite": article["unite"],
        "quantite": float(article["quantite"]),
        "pu_local": float(article["pu_local"]),
        "pu_chine": float(article["pu_chine"]),
    }


def build_payload_from_form() -> dict:
    """
    Construit le payload API a partir du formulaire.
    """
    return {
        "lot": st.session_state.dqe_lot,
        "sous_lot": st.session_state.dqe_sous_lot,
        "designation": st.session_state.dqe_designation,
        "unite": st.session_state.dqe_unite,
        "quantite": float(st.session_state.dqe_quantite),
        "pu_local": float(st.session_state.dqe_pu_local),
        "pu_chine": float(st.session_state.dqe_pu_chine),
    }


initialize_form_state()

filter_options, filter_error = fetch_filter_options()
if filter_error:
    show_api_error(filter_error)
    st.stop()

lot_label_map = build_lot_label_map(filter_options)

articles_response, articles_error = fetch_articles()
if articles_error:
    show_api_error(articles_error)
    st.stop()

default_lot_options = [f"LOT {option['value']}" for option in filter_options.get("lots", [])]
article_family_options = articles_response.get("filters", {}).get("familles", [])
article_lot_options = articles_response.get("filters", {}).get("lots", [])

filter_column_1, filter_column_2 = st.columns([1, 1])
with filter_column_1:
    selected_lot_filter = st.selectbox(
        "Filtre lot",
        options=["Tous les lots"] + article_lot_options,
        format_func=lambda option: (
            option if option == "Tous les lots" else display_lot_label(option, lot_label_map)
        ),
    )
with filter_column_2:
    selected_family_filter = st.selectbox(
        "Filtre sous-lot / famille",
        options=["Toutes les familles"] + article_family_options,
    )

query_filters = {}
if selected_lot_filter != "Tous les lots":
    query_filters["lot"] = selected_lot_filter
if selected_family_filter != "Toutes les familles":
    query_filters["sous_lot"] = selected_family_filter

filtered_articles_response, filtered_articles_error = fetch_articles(query_filters)
if filtered_articles_error:
    show_api_error(filtered_articles_error)
    st.stop()

form_values = st.session_state.dqe_form_values
lot_form_options = default_lot_options.copy()
if form_values["lot"] and form_values["lot"] not in lot_form_options:
    lot_form_options.append(form_values["lot"])
if not lot_form_options:
    lot_form_options = ["LOT 1"]

st.subheader("Formulaire de saisie")
with st.form("dqe_form", clear_on_submit=False):
    form_col_1, form_col_2 = st.columns(2)

    with form_col_1:
        st.selectbox(
            "LOT",
            options=lot_form_options,
            index=lot_form_options.index(form_values["lot"]) if form_values["lot"] in lot_form_options else 0,
            key="dqe_lot",
            format_func=lambda option: display_lot_label(option, lot_label_map),
        )
        st.text_input(
            "Sous-lot / famille",
            value=form_values["sous_lot"],
            key="dqe_sous_lot",
        )
        st.text_area(
            "Designation",
            value=form_values["designation"],
            key="dqe_designation",
            height=110,
        )

    with form_col_2:
        st.text_input(
            "Unite",
            value=form_values["unite"],
            key="dqe_unite",
        )
        quantite_value = st.number_input(
            "Quantite",
            min_value=0.0,
            value=float(form_values["quantite"]),
            step=1.0,
            key="dqe_quantite",
        )
        pu_local_value = st.number_input(
            "Prix unitaire local",
            min_value=0.0,
            value=float(form_values["pu_local"]),
            step=100.0,
            key="dqe_pu_local",
        )
        pu_chine_value = st.number_input(
            "Prix unitaire Chine",
            min_value=0.0,
            value=float(form_values["pu_chine"]),
            step=100.0,
            key="dqe_pu_chine",
        )

    total_local = quantite_value * pu_local_value
    total_import = quantite_value * pu_chine_value

    preview_col_1, preview_col_2 = st.columns(2)
    preview_col_1.metric("Total local", format_currency(total_local))
    preview_col_2.metric("Total import", format_currency(total_import))

    submit_col_1, submit_col_2 = st.columns([1, 1])
    submit_label = "Modifier l'article" if st.session_state.dqe_edit_id else "Ajouter l'article"
    submit_clicked = submit_col_1.form_submit_button(submit_label, use_container_width=True)
    reset_clicked = submit_col_2.form_submit_button("Vider le formulaire", use_container_width=True)

if reset_clicked:
    reset_form()
    st.rerun()

if submit_clicked:
    payload = build_payload_from_form()
    if st.session_state.dqe_edit_id:
        _, save_error = update_article(st.session_state.dqe_edit_id, payload)
    else:
        _, save_error = create_article(payload)

    if save_error:
        st.error(save_error)
    else:
        st.success("Article enregistre avec succes.")
        reset_form()
        st.rerun()

items = filtered_articles_response.get("items", [])
items_dataframe = pd.DataFrame(items)

st.subheader("Tableau dynamique DQE")

if items_dataframe.empty:
    st.info("Aucun article DQE pour les filtres courants.")
else:
    display_dataframe = items_dataframe[
        [
            "id",
            "lot",
            "sous_lot",
            "designation",
            "unite",
            "quantite",
            "pu_local",
            "pu_chine",
            "total_local",
            "total_import",
        ]
    ].copy()
    display_dataframe["lot"] = display_dataframe["lot"].apply(
        lambda value: display_lot_label(value, lot_label_map)
    )

    st.dataframe(display_dataframe, use_container_width=True, hide_index=True)

    total_col_1, total_col_2 = st.columns(2)
    total_col_1.metric("Total local cumule", format_currency(display_dataframe["total_local"].sum()))
    total_col_2.metric("Total import cumule", format_currency(display_dataframe["total_import"].sum()))

    st.subheader("Actions")
    for article in items:
        action_col_1, action_col_2, action_col_3 = st.columns([5, 1, 1])
        action_col_1.markdown(
            f"**{display_lot_label(article['lot'], lot_label_map)}** | {article['designation']} | "
            f"Qte: {article['quantite']} | "
            f"Local: {format_currency(article['total_local'])} | "
            f"Import: {format_currency(article['total_import'])}"
        )

        if action_col_2.button("Modifier", key=f"edit_{article['id']}"):
            load_article_into_form(article)
            st.rerun()

        if action_col_3.button("Supprimer", key=f"delete_{article['id']}"):
            _, delete_error = delete_article(article["id"])
            if delete_error:
                st.error(delete_error)
            else:
                if st.session_state.dqe_edit_id == article["id"]:
                    reset_form()
                st.success("Article supprime avec succes.")
                st.rerun()
