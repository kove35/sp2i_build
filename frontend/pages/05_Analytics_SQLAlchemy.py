"""
Dashboard branche directement sur le schema analytique SQLAlchemy.
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
    analytics_create_fact,
    analytics_delete_fact,
    analytics_fetch_dashboard,
    analytics_fetch_facts,
    analytics_fetch_filters,
    analytics_fetch_projects,
    analytics_reseed,
    analytics_update_fact,
)
from frontend.ui import (
    apply_dashboard_style,
    format_currency,
    format_percentage,
    render_decision_split,
    render_kpi_cards,
    render_proportional_bars,
    show_api_error,
)


st.set_page_config(
    page_title="Analytics SQLAlchemy",
    page_icon="DB",
    layout="wide",
)

apply_dashboard_style("Analytics SQLAlchemy")

st.caption(
    "Cette page lit et ecrit directement dans le schema SQLAlchemy : "
    "`build_projects`, `build_articles`, `build_fact_metre`."
)


@st.cache_data(show_spinner=False)
def load_projects() -> list[dict]:
    payload, error_message = analytics_fetch_projects()
    if error_message:
        raise RuntimeError(error_message)
    return payload


@st.cache_data(show_spinner=False)
def load_project_filters(project_id: int) -> dict:
    payload, error_message = analytics_fetch_filters(project_id)
    if error_message:
        raise RuntimeError(error_message)
    return payload


@st.cache_data(show_spinner=False)
def load_dashboard(project_id: int, filters_key: tuple) -> dict:
    filters = {
        "lots": list(filters_key[0]),
        "familles": list(filters_key[1]),
        "niveaux": list(filters_key[2]),
        "batiments": list(filters_key[3]),
    }
    payload, error_message = analytics_fetch_dashboard(project_id, filters)
    if error_message:
        raise RuntimeError(error_message)
    return payload


@st.cache_data(show_spinner=False)
def load_facts(project_id: int, filters_key: tuple) -> pd.DataFrame:
    filters = {
        "lots": list(filters_key[0]),
        "familles": list(filters_key[1]),
        "niveaux": list(filters_key[2]),
        "batiments": list(filters_key[3]),
    }
    payload, error_message = analytics_fetch_facts(project_id, filters)
    if error_message:
        raise RuntimeError(error_message)
    return pd.DataFrame(payload["items"])


def normalize_facts_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Harmonise les noms de colonnes renvoyes par l'API pour la page Streamlit.

    La page a besoin de libelles lisibles (`famille`, `quantite`, `total_local`...),
    alors que certaines routes exposent encore des noms plus techniques
    (`family_article`, `quantity`, `montant_local`...).
    """
    if dataframe.empty:
        return dataframe

    normalized = dataframe.copy()
    column_aliases = {
        "family_article": "famille",
        "quantity": "quantite",
        "montant_local": "total_local",
        "montant_import": "total_import",
        "lot_label": "lot",
    }

    for source_column, target_column in column_aliases.items():
        if target_column not in normalized.columns and source_column in normalized.columns:
            normalized[target_column] = normalized[source_column]

    return normalized


def clear_analytics_cache() -> None:
    """
    Vide les caches Streamlit lies a cette page.
    """
    load_projects.clear()
    load_project_filters.clear()
    load_dashboard.clear()
    load_facts.clear()


def format_fact_option(row: pd.Series) -> str:
    """
    Libelle lisible pour choisir une ligne a modifier.
    """
    return (
        f"#{int(row['id'])} | {row['code_bpu']} | {row['designation']} | "
        f"{row['lot']} | {row['batiment'] or '-'} | {row['niveau'] or '-'}"
    )


def extract_code_from_lot_label(lot_label: str | None) -> str | None:
    """
    Convertit un libelle comme 'LOT 1 - Gros œuvre' en code de lot SQLAlchemy.
    """
    if not lot_label:
        return None

    left_part = lot_label.split(" - ", 1)[0].strip()
    if left_part.upper().startswith("LOT "):
        suffix = left_part[4:].strip()
        if suffix.isdigit():
            return f"L{int(suffix):02d}"

    return left_part


def default_form_values(all_facts_df: pd.DataFrame) -> dict:
    """
    Valeurs par defaut du formulaire.
    """
    if all_facts_df.empty:
        return {
            "code_bpu": None,
            "lot": None,
            "famille": None,
            "niveau": None,
            "batiment": None,
            "quantite": 1.0,
            "pu_local": 0.0,
            "pu_chine": 0.0,
            "decision": "LOCAL",
            "source_row_key": "",
        }

    first_row = all_facts_df.iloc[0]
    return {
        "code_bpu": first_row["code_bpu"],
        "lot": first_row["lot"],
        "famille": first_row["famille"],
        "niveau": first_row["niveau"],
        "batiment": first_row["batiment"],
        "quantite": 1.0,
        "pu_local": float(first_row["pu_local"]),
        "pu_chine": float(first_row["pu_chine"] or 0),
        "decision": "LOCAL",
        "source_row_key": "",
    }


def build_fact_payload(
    code_bpu: str,
    lot_label: str | None,
    famille_label: str | None,
    niveau_label: str | None,
    batiment_label: str | None,
    quantite: float,
    pu_local: float,
    pu_chine: float,
    decision: str,
    source_row_key: str,
    family_label_to_code: dict[str, str],
    level_label_to_code: dict[str, str],
    building_label_to_code: dict[str, str],
) -> dict:
    """
    Construit le payload JSON attendu par l'API.
    """
    total_local = quantite * pu_local
    total_import = quantite * pu_chine if pu_chine > 0 else None
    capex_optimise = total_import if decision == "IMPORT" and total_import is not None else total_local
    economie = total_local - capex_optimise
    taux_economie = economie / total_local if total_local else 0.0

    return {
        "code_bpu": code_bpu,
        "lot_code": extract_code_from_lot_label(lot_label),
        "famille_code": family_label_to_code.get(famille_label) if famille_label else None,
        "niveau_code": level_label_to_code.get(niveau_label) if niveau_label else None,
        "batiment_code": building_label_to_code.get(batiment_label) if batiment_label else None,
        "quantite": quantite,
        "pu_local": pu_local,
        "pu_chine": pu_chine if pu_chine > 0 else None,
        "total_local": total_local,
        "total_import": total_import,
        "economie": economie,
        "taux_economie": taux_economie,
        "decision": decision,
        "source_row_key": source_row_key.strip() or None,
    }


try:
    project_options = load_projects()
except RuntimeError as error:
    show_api_error(str(error))
    st.stop()

if not project_options:
    st.warning("Aucun projet analytique n'est disponible. Lance d'abord le seed SQLAlchemy.")
    st.stop()

project_by_label = {
    f"{project['name']} ({project['code']})": project
    for project in project_options
}

preferred_project_code = st.session_state.get("analytics_selected_project_code")
default_project_label = next(
    (
        label
        for label, project in project_by_label.items()
        if project["code"] == preferred_project_code
    ),
    next(iter(project_by_label.keys())),
)

selected_project_label = st.selectbox(
    "Projet analytique",
    options=list(project_by_label.keys()),
    index=list(project_by_label.keys()).index(default_project_label),
)
selected_project = project_by_label[selected_project_label]
selected_project_id = selected_project["id"]

last_promoted_project = st.session_state.get("analytics_last_promoted_project")
if (
    last_promoted_project
    and last_promoted_project.get("project_code") == selected_project["code"]
):
    st.success(
        f"Projet promu ouvert : {last_promoted_project['project_name']} "
        f"({last_promoted_project['project_code']}) | "
        f"{last_promoted_project['fact_rows']} lignes analytiques."
    )
    st.session_state.pop("analytics_last_promoted_project", None)

action_col_1, action_col_2 = st.columns([0.8, 3.2])
with action_col_1:
    if st.button("Reseed Analytics", use_container_width=True):
        with st.spinner("Rechargement du schema analytique depuis les sources..."):
            payload, error_message = analytics_reseed()
        if error_message:
            st.error(error_message)
        else:
            clear_analytics_cache()
            st.success(
                f"Seed termine : {payload['fact_rows']} lignes de faits, "
                f"{payload['articles']} articles, {payload['lots']} lots."
            )
            st.rerun()
with action_col_2:
    st.caption(
        "Ce bouton recharge `build_projects`, `build_articles` et `build_fact_metre` "
        "depuis les tables sources historiques."
    )

try:
    project_filters = load_project_filters(selected_project_id)
except RuntimeError as error:
    show_api_error(str(error))
    st.stop()

filter_col_1, filter_col_2, filter_col_3, filter_col_4 = st.columns(4)
with filter_col_1:
    selected_lots = st.multiselect("Lots", options=project_filters["lots"])
with filter_col_2:
    selected_families = st.multiselect("Familles", options=project_filters["familles"])
with filter_col_3:
    selected_levels = st.multiselect("Niveaux", options=project_filters["niveaux"])
with filter_col_4:
    selected_buildings = st.multiselect("Batiments", options=project_filters["batiments"])

filters_key = (
    tuple(selected_lots),
    tuple(selected_families),
    tuple(selected_levels),
    tuple(selected_buildings),
)

try:
    dashboard_payload = load_dashboard(selected_project_id, filters_key)
    facts_dataframe = load_facts(selected_project_id, filters_key)
    all_facts_dataframe = load_facts(selected_project_id, (tuple(), tuple(), tuple(), tuple()))
except RuntimeError as error:
    show_api_error(str(error))
    st.stop()

facts_dataframe = normalize_facts_dataframe(facts_dataframe)
all_facts_dataframe = normalize_facts_dataframe(all_facts_dataframe)

family_label_to_code = {}
if (
    not all_facts_dataframe.empty
    and "famille" in all_facts_dataframe.columns
    and "family_code" in all_facts_dataframe.columns
):
    family_label_to_code = (
        all_facts_dataframe[["famille", "family_code"]]
        .dropna()
        .drop_duplicates()
        .set_index("famille")["family_code"]
        .to_dict()
    )
level_label_to_code = {
    label: label
    for label in project_filters["niveaux"]
}
building_label_to_code = {
    label: f"BAT_{label.upper().replace(' ', '_')}"
    for label in project_filters["batiments"]
}

kpis = dashboard_payload["kpis"]
render_kpi_cards(
    [
        {
            "label": "CAPEX Brut",
            "value": format_currency(kpis["capex_brut"]),
            "caption": "Depuis build_fact_metre",
        },
        {
            "label": "CAPEX Optimise",
            "value": format_currency(kpis["capex_optimise"]),
            "caption": "Decision appliquee",
        },
        {
            "label": "Economie",
            "value": format_currency(kpis["economie"]),
            "caption": "Gain total calcule",
        },
        {
            "label": "Taux Optimisation",
            "value": format_percentage(kpis["taux_optimisation"]),
            "caption": "Recalcule en temps reel",
        },
    ]
)

chart_col_1, chart_col_2 = st.columns(2)

with chart_col_1:
    capex_by_lot = pd.DataFrame(dashboard_payload["charts"]["capex_by_lot"])
    if not capex_by_lot.empty:
        render_proportional_bars(
            capex_by_lot,
            label_column="lot_id",
            value_column="value",
            title="CAPEX par lot",
            unit_suffix="FCFA",
        )

with chart_col_2:
    decision_mix = pd.DataFrame(dashboard_payload["charts"]["decision_mix"])
    if not decision_mix.empty:
        render_decision_split(
            decision_mix.rename(columns={"label": "decision"}),
            label_column="decision",
            value_column="value",
            title="Structure de decision",
        )

family_chart_df = pd.DataFrame(dashboard_payload["charts"]["economy_by_family"])
if not family_chart_df.empty:
    render_proportional_bars(
        family_chart_df.head(15),
        label_column="label",
        value_column="value",
        title="Economie par famille",
        unit_suffix="FCFA",
    )

st.subheader("Top articles")
top_articles_df = pd.DataFrame(dashboard_payload["charts"]["top_articles"])
if top_articles_df.empty:
    st.info("Aucune ligne disponible dans le perimetre courant.")
else:
    st.dataframe(top_articles_df, use_container_width=True, hide_index=True)

st.subheader("Edition des lignes de faits")
editor_col_1, editor_col_2 = st.columns([1.2, 1.8])

with editor_col_1:
    if all_facts_dataframe.empty:
        st.info("Aucune ligne disponible pour alimenter le formulaire.")
    else:
        mode = st.radio(
            "Mode",
            options=["Créer", "Modifier"],
            horizontal=True,
        )

        selected_row = None
        if mode == "Modifier":
            fact_options = {
                format_fact_option(row): row
                for _, row in all_facts_dataframe.sort_values("id", ascending=False).iterrows()
            }
            selected_option = st.selectbox(
                "Ligne a modifier",
                options=list(fact_options.keys()),
            )
            selected_row = fact_options[selected_option]

        defaults = default_form_values(all_facts_dataframe) if selected_row is None else {
            "code_bpu": selected_row["code_bpu"],
            "lot": selected_row["lot"],
            "famille": selected_row["famille"],
            "niveau": selected_row["niveau"],
            "batiment": selected_row["batiment"],
            "quantite": float(selected_row["quantite"]),
            "pu_local": float(selected_row["pu_local"]),
            "pu_chine": float(selected_row["pu_chine"] or 0),
            "decision": selected_row["decision"],
            "source_row_key": selected_row["source_row_key"] or "",
        }

        article_options = {
            f"{row['code_bpu']} | {row['designation']}": row["code_bpu"]
            for _, row in all_facts_dataframe[["code_bpu", "designation"]]
            .drop_duplicates()
            .sort_values("code_bpu")
            .iterrows()
        }
        article_labels = list(article_options.keys())
        default_article_label = next(
            (
                label
                for label, code in article_options.items()
                if code == defaults["code_bpu"]
            ),
            article_labels[0],
        )

        with st.form("analytics_fact_form"):
            article_label = st.selectbox(
                "Article / BPU",
                options=article_labels,
                index=article_labels.index(default_article_label),
            )

            lot_label = st.selectbox(
                "Lot",
                options=project_filters["lots"],
                index=project_filters["lots"].index(defaults["lot"]) if defaults["lot"] in project_filters["lots"] else 0,
            )

            famille_label = st.selectbox(
                "Famille",
                options=project_filters["familles"],
                index=project_filters["familles"].index(defaults["famille"]) if defaults["famille"] in project_filters["familles"] else 0,
            )

            niveau_label = st.selectbox(
                "Niveau",
                options=project_filters["niveaux"],
                index=project_filters["niveaux"].index(defaults["niveau"]) if defaults["niveau"] in project_filters["niveaux"] else 0,
            )

            batiment_label = st.selectbox(
                "Batiment",
                options=project_filters["batiments"],
                index=project_filters["batiments"].index(defaults["batiment"]) if defaults["batiment"] in project_filters["batiments"] else 0,
            )

            quantite = st.number_input("Quantite", min_value=0.0001, value=float(defaults["quantite"]), step=1.0)
            pu_local = st.number_input("PU local", min_value=0.0, value=float(defaults["pu_local"]), step=1000.0)
            pu_chine = st.number_input("PU Chine", min_value=0.0, value=float(defaults["pu_chine"]), step=1000.0)
            decision = st.selectbox(
                "Decision",
                options=["LOCAL", "IMPORT"],
                index=["LOCAL", "IMPORT"].index(defaults["decision"]) if defaults["decision"] in ["LOCAL", "IMPORT"] else 0,
            )
            source_row_key = st.text_input("Source row key", value=defaults["source_row_key"])

            total_local_preview = quantite * pu_local
            total_import_preview = quantite * pu_chine if pu_chine > 0 else 0.0
            capex_optimise_preview = total_import_preview if decision == "IMPORT" and pu_chine > 0 else total_local_preview
            economie_preview = total_local_preview - capex_optimise_preview
            taux_preview = economie_preview / total_local_preview if total_local_preview else 0.0

            st.caption(
                f"Calcul temps reel : total local={format_currency(total_local_preview)} | "
                f"total import={format_currency(total_import_preview)} | "
                f"economie={format_currency(economie_preview)} | "
                f"taux={format_percentage(taux_preview)}"
            )

            submitted = st.form_submit_button(
                "Creer la ligne" if mode == "Créer" else "Enregistrer les modifications",
                use_container_width=True,
            )

        if submitted:
            payload = build_fact_payload(
                code_bpu=article_options[article_label],
                lot_label=lot_label,
                famille_label=famille_label,
                niveau_label=niveau_label,
                batiment_label=batiment_label,
                quantite=quantite,
                pu_local=pu_local,
                pu_chine=pu_chine,
                decision=decision,
                source_row_key=source_row_key,
                family_label_to_code=family_label_to_code,
                level_label_to_code=level_label_to_code,
                building_label_to_code=building_label_to_code,
            )

            if mode == "Créer":
                response, error_message = analytics_create_fact(selected_project_id, payload)
            else:
                response, error_message = analytics_update_fact(int(selected_row["id"]), payload)

            if error_message:
                st.error(error_message)
            else:
                clear_analytics_cache()
                st.success(
                    "Ligne analytique creee." if mode == "Créer" else "Ligne analytique mise a jour."
                )
                st.rerun()

        if mode == "Modifier" and selected_row is not None:
            if st.button("Supprimer la ligne selectionnee", type="secondary", use_container_width=True):
                response, error_message = analytics_delete_fact(int(selected_row["id"]))
                if error_message:
                    st.error(error_message)
                else:
                    clear_analytics_cache()
                    st.success("Ligne analytique supprimee.")
                    st.rerun()

with editor_col_2:
    st.subheader("Lignes de faits")
    if facts_dataframe.empty:
        st.info("Aucune ligne de faits apres filtrage.")
    else:
        st.dataframe(facts_dataframe, use_container_width=True, hide_index=True)
