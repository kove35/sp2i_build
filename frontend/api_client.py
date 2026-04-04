"""
Client HTTP tres simple pour parler a FastAPI.
"""

from __future__ import annotations

import os

import requests


API_BASE_URL = os.getenv("SP2I_API_URL", "http://127.0.0.1:8000")


def fetch_filter_options() -> tuple[dict | None, str | None]:
    """
    Lit les options de filtres depuis le backend.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/filters", timeout=20)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger les filtres : {error}"


def fetch_dashboard_data(endpoint: str, filters: dict) -> tuple[dict | None, str | None]:
    """
    Appelle un endpoint dashboard avec les filtres actifs.
    """
    try:
        clean_filters = {
            key: value
            for key, value in filters.items()
            if value not in (None, "", "all")
        }
        response = requests.get(
            f"{API_BASE_URL}/{endpoint}",
            params=clean_filters,
            timeout=30,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger les donnees : {error}"


def fetch_direction_dataset() -> tuple[dict | None, str | None]:
    """
    Lit les lignes detaillees du dashboard Direction.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/direction_dataset", timeout=30)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger le dataset direction : {error}"


def fetch_direction_kpi_dataset() -> tuple[dict | None, str | None]:
    """
    Lit le dataset KPI ancre sur le PDF de reference.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/direction_kpi_dataset", timeout=30)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger le dataset KPI direction : {error}"


def fetch_articles(filters: dict | None = None) -> tuple[dict | None, str | None]:
    """
    Lit les articles DQE avec filtres facultatifs.
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/articles",
            params=filters or {},
            timeout=20,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger les articles DQE : {error}"


def create_article(payload: dict) -> tuple[dict | None, str | None]:
    """
    Cree un article DQE.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/article",
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de creer l'article : {error}"


def update_article(article_id: int, payload: dict) -> tuple[dict | None, str | None]:
    """
    Met a jour un article DQE.
    """
    try:
        response = requests.put(
            f"{API_BASE_URL}/article/{article_id}",
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de modifier l'article : {error}"


def delete_article(article_id: int) -> tuple[dict | None, str | None]:
    """
    Supprime un article DQE.
    """
    try:
        response = requests.delete(
            f"{API_BASE_URL}/article/{article_id}",
            timeout=20,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de supprimer l'article : {error}"


def _build_auth_headers(token: str) -> dict:
    """
    Construit les headers JWT.
    """
    return {"Authorization": f"Bearer {token}"}


def saas_register(full_name: str, email: str, password: str) -> tuple[dict | None, str | None]:
    """
    Cree un utilisateur SaaS.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/saas/auth/register",
            json={
                "full_name": full_name,
                "email": email,
                "password": password,
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de creer le compte : {error}"


def saas_login(email: str, password: str) -> tuple[dict | None, str | None]:
    """
    Connecte un utilisateur SaaS.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/saas/auth/login",
            json={"email": email, "password": password},
            timeout=20,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de se connecter : {error}"


def saas_fetch_projects(token: str) -> tuple[list | None, str | None]:
    """
    Charge les projets du compte connecte.
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/saas/projects",
            headers=_build_auth_headers(token),
            timeout=20,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger les projets : {error}"


def saas_create_project(token: str, payload: dict) -> tuple[dict | None, str | None]:
    """
    Cree un projet SaaS.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/saas/projects",
            json=payload,
            headers=_build_auth_headers(token),
            timeout=20,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de creer le projet : {error}"


def saas_save_capex_item(
    token: str,
    project_id: int,
    payload: dict,
) -> tuple[dict | None, str | None]:
    """
    Ajoute une ligne CAPEX a un projet.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/saas/projects/{project_id}/items",
            json=payload,
            headers=_build_auth_headers(token),
            timeout=20,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible d'ajouter la ligne CAPEX : {error}"


def saas_fetch_dashboard(
    token: str,
    project_id: int,
    filters: dict,
) -> tuple[dict | None, str | None]:
    """
    Charge le dashboard premium filtre.
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/saas/projects/{project_id}/dashboard",
            params=filters,
            headers=_build_auth_headers(token),
            timeout=30,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger le dashboard SaaS : {error}"


def saas_fetch_recommendations(
    token: str,
    project_id: int,
) -> tuple[dict | None, str | None]:
    """
    Charge les recommandations import.
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/saas/projects/{project_id}/recommendations",
            headers=_build_auth_headers(token),
            timeout=20,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger les recommandations IA : {error}"


def analytics_fetch_projects() -> tuple[list | None, str | None]:
    """
    Charge les projets du schema analytique SQLAlchemy.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/analytics/projects", timeout=20)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger les projets analytiques : {error}"


def analytics_create_project(payload: dict) -> tuple[dict | None, str | None]:
    """
    Cree un projet analytique.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/analytics/projects",
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de creer le projet analytique : {error}"


def analytics_fetch_default_project() -> tuple[dict | None, str | None]:
    """
    Charge le projet analytique utilise par defaut dans les dashboards.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/analytics/default-project", timeout=20)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger le projet par defaut : {error}"


def analytics_set_default_project(project_id: int) -> tuple[dict | None, str | None]:
    """
    Definit le projet analytique par defaut des dashboards.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/analytics/default-project/{project_id}",
            timeout=20,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de definir le projet par defaut : {error}"


def analytics_fetch_filters(project_id: int) -> tuple[dict | None, str | None]:
    """
    Charge les filtres d'un projet analytique.
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/analytics/projects/{project_id}/filters",
            timeout=20,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger les filtres analytiques : {error}"


def analytics_fetch_dashboard(project_id: int, filters: dict) -> tuple[dict | None, str | None]:
    """
    Charge le dashboard du schema analytique SQLAlchemy.
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/analytics/projects/{project_id}/dashboard",
            params={key: value for key, value in filters.items() if value},
            timeout=30,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger le dashboard analytique : {error}"


def analytics_fetch_facts(project_id: int, filters: dict) -> tuple[dict | None, str | None]:
    """
    Charge les lignes de faits analytiques.
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/analytics/projects/{project_id}/facts",
            params={key: value for key, value in filters.items() if value},
            timeout=30,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger les lignes analytiques : {error}"


def analytics_fetch_hierarchy_items(project_id: int, filters: dict) -> tuple[dict | None, str | None]:
    """
    Charge les lignes hierarchiques du module DQE intelligent.
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/analytics/projects/{project_id}/hierarchy-items",
            params={key: value for key, value in filters.items() if value},
            timeout=30,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger les lignes hierarchiques : {error}"


def analytics_save_hierarchy_item(project_id: int, payload: dict) -> tuple[dict | None, str | None]:
    """
    Cree ou met a jour une ligne DQE hierarchique.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/analytics/projects/{project_id}/hierarchy-items",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible d'enregistrer la ligne DQE : {error}"


def analytics_preview_smart_import(
    file_path: str,
    sheet_name: str | None = None,
    custom_mapping: dict[str, str | None] | None = None,
) -> tuple[dict | None, str | None]:
    """
    Analyse un fichier DQE et retourne un apercu de mapping.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/analytics/dqe-smart/preview",
            json={
                "file_path": file_path,
                "sheet_name": sheet_name,
                "custom_mapping": custom_mapping,
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de previsualiser le fichier DQE : {error}"


def analytics_apply_smart_import(
    project_id: int,
    file_path: str,
    sheet_name: str | None = None,
    replace_existing: bool = False,
    custom_mapping: dict[str, str | None] | None = None,
) -> tuple[dict | None, str | None]:
    """
    Importe un fichier DQE dans le schema analytique.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/analytics/dqe-smart/import",
            json={
                "project_id": project_id,
                "file_path": file_path,
                "sheet_name": sheet_name,
                "replace_existing": replace_existing,
                "custom_mapping": custom_mapping,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible d'importer le fichier DQE : {error}"


def analytics_create_fact(project_id: int, payload: dict) -> tuple[dict | None, str | None]:
    """
    Cree une ligne de faits analytique.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/analytics/projects/{project_id}/facts",
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de creer la ligne analytique : {error}"


def analytics_update_fact(fact_id: int, payload: dict) -> tuple[dict | None, str | None]:
    """
    Modifie une ligne de faits analytique.
    """
    try:
        response = requests.put(
            f"{API_BASE_URL}/analytics/facts/{fact_id}",
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de modifier la ligne analytique : {error}"


def analytics_delete_fact(fact_id: int) -> tuple[dict | None, str | None]:
    """
    Supprime une ligne de faits analytique.
    """
    try:
        response = requests.delete(
            f"{API_BASE_URL}/analytics/facts/{fact_id}",
            timeout=20,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de supprimer la ligne analytique : {error}"


def analytics_reseed() -> tuple[dict | None, str | None]:
    """
    Relance le seed complet du schema analytique SQLAlchemy.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/analytics/reseed",
            timeout=120,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de relancer le seed analytique : {error}"


def dqe_control_refresh() -> tuple[dict | None, str | None]:
    """
    Reimporte le DQE PDF puis regenere les rapports de controle.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/analytics/dqe/refresh",
            timeout=120,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de rafraichir le controle DQE : {error}"


def dqe_control_import(pdf_path: str | None = None) -> tuple[dict | None, str | None]:
    """
    Importe un PDF DQE dans les tables sources.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/analytics/dqe/import",
            json={"pdf_path": pdf_path} if pdf_path else {},
            timeout=120,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible d'importer le DQE PDF : {error}"


def dqe_control_promote(
    source_file: str | None = None,
    project_code: str | None = None,
    project_name: str | None = None,
    replace_existing: bool = False,
) -> tuple[dict | None, str | None]:
    """
    Promeut une source DQE PDF en projet analytique.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/analytics/dqe/promote",
            json={
                "source_file": source_file,
                "project_code": project_code,
                "project_name": project_name,
                "replace_existing": replace_existing,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de promouvoir le DQE PDF : {error}"


def dqe_control_fetch_source_files() -> tuple[dict | None, str | None]:
    """
    Charge la liste des DQE PDF importes.
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/analytics/dqe/source-files",
            timeout=30,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger les sources DQE PDF : {error}"


def dqe_control_fetch_summary(source_file: str | None = None) -> tuple[dict | None, str | None]:
    """
    Charge la synthese du controle DQE PDF.
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/analytics/dqe/summary",
            params={"source_file": source_file} if source_file else {},
            timeout=30,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger la synthese DQE : {error}"


def dqe_control_fetch_lot_comparison(source_file: str | None = None) -> tuple[dict | None, str | None]:
    """
    Charge les ecarts lot par lot entre le PDF et la base analytique.
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/analytics/dqe/lot-comparison",
            params={"source_file": source_file} if source_file else {},
            timeout=30,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger les ecarts par lot : {error}"


def dqe_control_fetch_article_comparison(
    source_file: str | None = None,
    lot_code: str | None = None,
) -> tuple[dict | None, str | None]:
    """
    Charge les ecarts article par article.
    """
    try:
        params = {}
        if source_file:
            params["source_file"] = source_file
        if lot_code:
            params["lot_code"] = lot_code
        response = requests.get(
            f"{API_BASE_URL}/analytics/dqe/article-comparison",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger les ecarts article/article : {error}"


def erp_fetch_status() -> tuple[dict | None, str | None]:
    try:
        response = requests.get(f"{API_BASE_URL}/erp/status", timeout=20)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de verifier la base ERP : {error}"


def erp_fetch_filters() -> tuple[dict | None, str | None]:
    try:
        response = requests.get(f"{API_BASE_URL}/erp/filters", timeout=20)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger les filtres ERP : {error}"


def erp_fetch_dashboard(filters: dict) -> tuple[dict | None, str | None]:
    try:
        clean_filters = {key: value for key, value in filters.items() if value not in (None, "", "all")}
        response = requests.get(f"{API_BASE_URL}/erp/dashboard", params=clean_filters, timeout=30)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as error:
        return None, f"Impossible de charger le dashboard ERP : {error}"
