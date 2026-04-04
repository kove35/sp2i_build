"""
Module DQE intelligent pour SP2I_Build.

Cette page propose deux modes :
- import intelligent depuis un Excel/CSV
- construction manuelle d'une arborescence DQE
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
    analytics_apply_smart_import,
    analytics_create_project,
    analytics_fetch_default_project,
    analytics_fetch_hierarchy_items,
    analytics_fetch_projects,
    analytics_preview_smart_import,
    analytics_save_hierarchy_item,
    analytics_set_default_project,
)
from frontend.ui import apply_dashboard_style, format_currency, format_percentage, show_api_error


st.set_page_config(page_title="DQE Intelligent", page_icon="📐", layout="wide")
apply_dashboard_style("DQE Intelligent")
st.caption(
    "Module multi-dimensionnel : Projet -> Batiment -> Niveau -> Lot -> Sous-lot -> Article."
)


@st.cache_data(show_spinner=False)
def load_projects() -> list[dict]:
    payload, error_message = analytics_fetch_projects()
    if error_message:
        raise RuntimeError(error_message)
    return payload


@st.cache_data(show_spinner=False)
def load_default_project() -> dict | None:
    payload, error_message = analytics_fetch_default_project()
    if error_message:
        raise RuntimeError(error_message)
    return payload.get("project") if payload else None


@st.cache_data(show_spinner=False)
def load_hierarchy_items(project_id: int, filters_key: tuple[str | None, str | None, str | None]) -> pd.DataFrame:
    payload, error_message = analytics_fetch_hierarchy_items(
        project_id,
        {
            "batiment": filters_key[0],
            "niveau": filters_key[1],
            "lot": filters_key[2],
        },
    )
    if error_message:
        raise RuntimeError(error_message)
    return pd.DataFrame(payload["items"])


def clear_dqe_intelligent_cache() -> None:
    load_projects.clear()
    load_default_project.clear()
    load_hierarchy_items.clear()


def get_selected_project(projects: list[dict]) -> dict:
    project_labels = {
        f"{project['name']} ({project['code']})": project
        for project in projects
    }
    default_project = None
    try:
        default_project = load_default_project()
    except RuntimeError:
        default_project = None

    default_label = next(iter(project_labels.keys()))
    if default_project:
        for label, project in project_labels.items():
            if project["id"] == default_project["id"]:
                default_label = label
                break
    labels = list(project_labels.keys())
    selected_label = st.selectbox(
        "Projet analytique",
        options=labels,
        index=labels.index(default_label),
    )
    return project_labels.get(selected_label, project_labels[default_label])


def render_project_creation_box() -> None:
    with st.expander("Creer un nouveau projet analytique", expanded=False):
        with st.form("create_project_form"):
            code = st.text_input("Code projet", value="")
            name = st.text_input("Nom projet", value="")
            description = st.text_area("Description", value="")
            devise = st.text_input("Devise", value="FCFA")
            statut = st.selectbox("Statut", options=["draft", "active", "archived"], index=0)
            submitted = st.form_submit_button("Creer le projet", use_container_width=True)

        if submitted:
            payload, error_message = analytics_create_project(
                {
                    "code": code,
                    "name": name,
                    "description": description,
                    "devise": devise,
                    "statut": statut,
                }
            )
            if error_message:
                st.error(error_message)
            else:
                clear_dqe_intelligent_cache()
                st.success(f"Projet cree : {payload['name']} ({payload['code']})")
                st.rerun()


def render_hierarchy_tree(dataframe: pd.DataFrame) -> None:
    """
    Affiche l'arborescence metier avec des expanders imbriques.
    """
    if dataframe.empty:
        st.info("Aucune ligne DQE pour le perimetre courant.")
        return

    for building_name, building_df in dataframe.groupby("batiment", dropna=False):
        building_total = float(building_df["montant_local"].sum())
        with st.expander(f"Batiment : {building_name} | {format_currency(building_total)}", expanded=False):
            for level_name, level_df in building_df.groupby("niveau", dropna=False):
                level_total = float(level_df["montant_local"].sum())
                with st.expander(f"Niveau : {level_name} | {format_currency(level_total)}", expanded=False):
                    for lot_name, lot_df in level_df.groupby("lot", dropna=False):
                        lot_total = float(lot_df["montant_local"].sum())
                        with st.expander(f"Lot : {lot_name} | {format_currency(lot_total)}", expanded=False):
                            display_columns = [
                                "sous_lot",
                                "designation",
                                "unite",
                                "quantite",
                                "pu_local",
                                "pu_chine",
                                "montant_local",
                                "montant_import",
                                "economie",
                                "decision",
                            ]
                            st.dataframe(
                                lot_df[display_columns],
                                use_container_width=True,
                                hide_index=True,
                            )


try:
    projects = load_projects()
except RuntimeError as error:
    show_api_error(str(error))
    st.stop()

if not projects:
    st.warning("Aucun projet analytique n'est disponible.")
    render_project_creation_box()
    st.stop()

selected_project = get_selected_project(projects)
selected_project_id = selected_project["id"]
render_project_creation_box()

default_action_col_1, default_action_col_2 = st.columns([1.2, 2.8])
with default_action_col_1:
    if st.button("Utiliser ce projet pour les dashboards", use_container_width=True):
        payload, error_message = analytics_set_default_project(selected_project_id)
        if error_message:
            st.error(error_message)
        else:
            clear_dqe_intelligent_cache()
            st.success(
                f"Projet par defaut mis a jour : {payload['project_name']} ({payload['project_code']})"
            )
with default_action_col_2:
    st.caption(
        "Les dashboards Direction, Chantier et Import utiliseront ce projet analytique comme source detaillee par defaut."
    )

tab_import, tab_manual = st.tabs(["Import intelligent", "Construction manuelle"])

with tab_import:
    st.subheader("Mode 1 - Import intelligent")
    st.write(
        "Le moteur detecte automatiquement les colonnes Batiment, Niveau, Lot, Sous-lot, "
        "Designation, Quantite et Prix, puis construit un format standard."
    )

    preview_payload = st.session_state.get("dqe_import_preview")
    custom_mapping = st.session_state.get("dqe_import_custom_mapping", {})

    import_col_1, import_col_2, import_col_3 = st.columns([2, 1.2, 1])
    with import_col_1:
        file_path = st.text_input(
            "Chemin du fichier Excel / CSV",
            value=st.session_state.get("dqe_import_file_path", ""),
            placeholder=r"C:\...\mon_dqe.xlsx",
        )
    with import_col_2:
        sheet_name = st.text_input(
            "Feuille Excel (optionnel)",
            value=st.session_state.get("dqe_import_sheet_name", ""),
        )
    with import_col_3:
        replace_existing = st.checkbox("Remplacer les lignes de ce fichier", value=False)

    action_col_1, action_col_2 = st.columns([1, 1])
    with action_col_1:
        if st.button("Analyser le fichier", use_container_width=True):
            payload, error_message = analytics_preview_smart_import(
                file_path=file_path,
                sheet_name=sheet_name or None,
                custom_mapping=custom_mapping,
            )
            if error_message:
                st.error(error_message)
            else:
                st.session_state["dqe_import_preview"] = payload
                st.session_state["dqe_import_file_path"] = file_path
                st.session_state["dqe_import_sheet_name"] = sheet_name
                st.rerun()
    with action_col_2:
        if st.button("Importer dans le projet", use_container_width=True, type="primary"):
            payload, error_message = analytics_apply_smart_import(
                project_id=selected_project_id,
                file_path=file_path,
                sheet_name=sheet_name or None,
                replace_existing=replace_existing,
                custom_mapping=custom_mapping,
            )
            if error_message:
                st.error(error_message)
            else:
                clear_dqe_intelligent_cache()
                st.success(
                    f"Import termine : {payload['imported_rows']} lignes chargees dans le projet."
                )
                st.session_state.pop("dqe_import_preview", None)
                st.rerun()

    if preview_payload:
        st.info(
            "Detection terminee. Verifie le mapping propose avant de lancer l'import."
        )
        info_col_1, info_col_2, info_col_3 = st.columns(3)
        info_col_1.metric("Lignes source", preview_payload["row_count_source"])
        info_col_2.metric("Lignes standardisees", preview_payload["row_count_standardized"])
        info_col_3.metric("Champs par defaut", len(preview_payload["defaults_applied"]))

        st.write("Mapping detecte")
        mapping_dataframe = pd.DataFrame(
            [
                {"champ_standard": key, "colonne_source": value}
                for key, value in preview_payload["detected_mapping"].items()
            ]
        )
        st.dataframe(mapping_dataframe, use_container_width=True, hide_index=True)

        with st.expander("Ajuster le mapping des colonnes", expanded=False):
            available_columns = ["__NONE__"] + preview_payload["source_columns"]
            updated_mapping: dict[str, str | None] = {}

            for standard_field, detected_column in preview_payload["detected_mapping"].items():
                current_value = custom_mapping.get(standard_field, detected_column)
                current_value = current_value if current_value in available_columns else "__NONE__"
                selected_column = st.selectbox(
                    f"{standard_field}",
                    options=available_columns,
                    index=available_columns.index(current_value),
                    key=f"mapping_{standard_field}",
                )
                updated_mapping[standard_field] = None if selected_column == "__NONE__" else selected_column

            if st.button("Appliquer ce mapping a l'aperçu", use_container_width=True):
                st.session_state["dqe_import_custom_mapping"] = updated_mapping
                payload, error_message = analytics_preview_smart_import(
                    file_path=file_path,
                    sheet_name=sheet_name or None,
                    custom_mapping=updated_mapping,
                )
                if error_message:
                    st.error(error_message)
                else:
                    st.session_state["dqe_import_preview"] = payload
                    st.rerun()

        if preview_payload["missing_required_fields"]:
            st.warning(
                "Champs importants non detectes automatiquement : "
                + ", ".join(preview_payload["missing_required_fields"])
            )
        if preview_payload["defaults_applied"]:
            st.caption(
                "Valeurs par defaut appliquees a certains champs : "
                + ", ".join(preview_payload["defaults_applied"])
            )

        preview_dataframe = pd.DataFrame(preview_payload["preview_rows"])
        if not preview_dataframe.empty:
            st.write("Apercu des lignes standardisees")
            st.dataframe(preview_dataframe, use_container_width=True, hide_index=True)

with tab_manual:
    st.subheader("Mode 2 - Construction manuelle")
    st.write(
        "Ajoute des lignes DQE directement dans la structure analytique hierarchique."
    )

    filter_col_1, filter_col_2, filter_col_3 = st.columns(3)
    with filter_col_1:
        filter_batiment = st.text_input("Filtre batiment", value="")
    with filter_col_2:
        filter_niveau = st.text_input("Filtre niveau", value="")
    with filter_col_3:
        filter_lot = st.text_input("Filtre lot", value="")

    filters_key = (
        filter_batiment or None,
        filter_niveau or None,
        filter_lot or None,
    )

    try:
        hierarchy_dataframe = load_hierarchy_items(selected_project_id, filters_key)
    except RuntimeError as error:
        show_api_error(str(error))
        st.stop()

    form_col, tree_col = st.columns([1.15, 1.85])

    with form_col:
        with st.form("hierarchy_item_form"):
            batiment = st.text_input("Batiment", value=filter_batiment or "Batiment Global")
            niveau = st.text_input("Niveau", value=filter_niveau or "GLOBAL")
            lot = st.text_input("Lot", value=filter_lot or "LOT GLOBAL")
            sous_lot = st.text_input("Sous-lot", value="SOUS-LOT GLOBAL")
            famille = st.text_input("Famille article", value="")
            designation = st.text_area("Designation", value="")
            unite = st.text_input("Unite", value="U")
            code_bpu = st.text_input("Code BPU (optionnel)", value="")
            quantite = st.number_input("Quantite", min_value=0.0001, value=1.0, step=1.0)
            pu_local = st.number_input("Prix local", min_value=0.0, value=0.0, step=1000.0)
            pu_chine = st.number_input("Prix Chine", min_value=0.0, value=0.0, step=1000.0)

            montant_local = quantite * pu_local
            montant_import = quantite * pu_chine if pu_chine > 0 else 0.0
            economie = montant_local - montant_import if pu_chine > 0 else 0.0
            decision = "IMPORT" if pu_chine > 0 and economie > 0 else "LOCAL"
            taux = economie / montant_local if montant_local else 0.0

            st.caption(
                f"Montant local : {format_currency(montant_local)} | "
                f"Montant import : {format_currency(montant_import)} | "
                f"Economie : {format_currency(economie)} | "
                f"Decision : {decision} | "
                f"Taux : {format_percentage(taux)}"
            )

            submitted = st.form_submit_button("Enregistrer la ligne", use_container_width=True)

        if submitted:
            payload, error_message = analytics_save_hierarchy_item(
                selected_project_id,
                {
                    "batiment": batiment,
                    "niveau": niveau,
                    "lot": lot,
                    "sous_lot": sous_lot,
                    "designation": designation,
                    "unite": unite,
                    "quantite": quantite,
                    "pu_local": pu_local,
                    "pu_chine": pu_chine if pu_chine > 0 else None,
                    "code_bpu": code_bpu or None,
                    "famille": famille or None,
                },
            )
            if error_message:
                st.error(error_message)
            else:
                clear_dqe_intelligent_cache()
                st.success(
                    f"Ligne enregistree : {payload['designation']} | "
                    f"{payload['decision']} | {format_currency(payload['montant_local'])}"
                )
                st.rerun()

    with tree_col:
        st.write("Vue hierarchique")
        render_hierarchy_tree(hierarchy_dataframe)

        if not hierarchy_dataframe.empty:
            st.write("Table detaillee")
            st.dataframe(hierarchy_dataframe, use_container_width=True, hide_index=True)
