"""
API FastAPI pour exposer les KPI et les graphiques.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.build_analytics import router as build_analytics_router
from backend.api.routes.erp_dqe import router as erp_dqe_router
from backend.config import AUTO_SEED_ANALYTICS
from backend.database import get_data_debug_stats, initialize_database
from backend.db.seed_build_analytics import seed_build_analytics
from backend.schemas import DQEArticlePayload, DashboardFilters
from backend.services.dashboard_service import DashboardService
from backend.services.dqe_service import DQEArticleService


logger = logging.getLogger(__name__)

saas_import_error: str | None = None
saas_routers: list = []

try:
    from backend.api.routes.ai import router as saas_ai_router
    from backend.api.routes.auth import router as saas_auth_router
    from backend.api.routes.dashboard import router as saas_dashboard_router
    from backend.api.routes.projects import router as saas_projects_router

    saas_routers = [
        saas_auth_router,
        saas_projects_router,
        saas_dashboard_router,
        saas_ai_router,
    ]
except ModuleNotFoundError as error:
    # Le module SaaS devient optionnel au demarrage.
    # Cela evite de bloquer toute l'API si un environnement Python
    # n'a pas encore toutes les dependances JWT / SQLAlchemy.
    saas_import_error = str(error)


app = FastAPI(
    title="SP2I_Build API",
    description="API de pilotage CAPEX, chantier et sourcing import.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in saas_routers:
    app.include_router(router)

app.include_router(build_analytics_router)
app.include_router(erp_dqe_router)

dashboard_service = DashboardService()
dqe_article_service = DQEArticleService()


@app.on_event("startup")
def startup_event() -> None:
    """
    Cree les tables applicatives manquantes au demarrage.
    """
    initialize_database()
    debug_stats = get_data_debug_stats()
    logger.info("Etat des donnees au demarrage: %s", debug_stats)

    sqlalchemy_counts = debug_stats.get("sqlalchemy", {}).get("counts", {})
    source_tables = debug_stats.get("source_sqlite", {}).get("tables", {})
    build_fact_rows = int(sqlalchemy_counts.get("build_fact_rows", 0))
    source_staging_rows = int(source_tables.get("staging", {}).get("rows", 0))

    if AUTO_SEED_ANALYTICS and build_fact_rows == 0 and source_staging_rows > 0:
        logger.warning(
            "Schema analytique vide detecte avec source SQLite disponible. Lancement du seed automatique."
        )
        seed_result = seed_build_analytics()
        logger.info("Seed automatique termine: %s", seed_result)


def build_filters(
    lot_id: int | None = Query(default=None),
    fam_article_id: str | None = Query(default=None),
    batiment_id: str | None = Query(default=None),
    niveau_id: str | None = Query(default=None),
) -> DashboardFilters:
    """
    Construit un objet filtre a partir des query params.
    """
    return DashboardFilters(
        lot_id=lot_id,
        fam_article_id=fam_article_id,
        batiment_id=batiment_id,
        niveau_id=niveau_id,
    )


@app.get("/")
def read_root() -> dict:
    available_endpoints = [
        "/debug/data-stats",
        "/filters",
        "/direction_dataset",
        "/kpi_direction",
        "/kpi_chantier",
        "/kpi_import",
        "/article",
        "/articles",
        "/analytics/projects",
    ]

    if not saas_import_error:
        available_endpoints.extend(
            [
                "/saas/auth/register",
                "/saas/auth/login",
                "/saas/projects",
            ]
        )

    return {
        "application": "SP2I_Build API",
        "status": "ok",
        "saas_enabled": saas_import_error is None,
        "saas_import_error": saas_import_error,
        "available_endpoints": available_endpoints,
    }


@app.get("/debug/data-stats")
def get_data_stats() -> dict:
    """
    Expose l'etat des sources de donnees et des volumes utiles au diagnostic.
    """
    debug_stats = get_data_debug_stats()
    debug_stats["default_dashboard_project"] = dashboard_service.get_default_dashboard_project()
    return debug_stats


@app.get("/filters")
def get_filters() -> dict:
    return dashboard_service.get_filter_options()


@app.get("/direction_dataset")
def get_direction_dataset() -> dict:
    """
    Retourne les lignes detaillees pour la page Direction.
    """
    return dashboard_service.get_direction_dataset()


@app.get("/direction_kpi_dataset")
def get_direction_kpi_dataset() -> dict:
    """
    Retourne le dataset detaille du dashboard Direction.
    """
    return dashboard_service.get_direction_kpi_dataset()


@app.get("/kpi_direction")
def get_direction_dashboard(
    lot_id: int | None = Query(default=None),
    fam_article_id: str | None = Query(default=None),
    batiment_id: str | None = Query(default=None),
    niveau_id: str | None = Query(default=None),
) -> dict:
    filters = build_filters(lot_id, fam_article_id, batiment_id, niveau_id)
    return dashboard_service.get_direction_dashboard(filters)


@app.get("/kpi_chantier")
def get_chantier_dashboard(
    lot_id: int | None = Query(default=None),
    fam_article_id: str | None = Query(default=None),
    batiment_id: str | None = Query(default=None),
    niveau_id: str | None = Query(default=None),
) -> dict:
    filters = build_filters(lot_id, fam_article_id, batiment_id, niveau_id)
    return dashboard_service.get_chantier_dashboard(filters)


@app.get("/kpi_import")
def get_import_dashboard(
    lot_id: int | None = Query(default=None),
    fam_article_id: str | None = Query(default=None),
    batiment_id: str | None = Query(default=None),
    niveau_id: str | None = Query(default=None),
) -> dict:
    filters = build_filters(lot_id, fam_article_id, batiment_id, niveau_id)
    return dashboard_service.get_import_dashboard(filters)


@app.post("/article")
def create_article(payload: DQEArticlePayload) -> dict:
    """
    Cree un article DQE.
    """
    return dqe_article_service.create_article(payload)


@app.put("/article/{article_id}")
def update_article(article_id: int, payload: DQEArticlePayload) -> dict:
    """
    Modifie un article DQE existant.
    """
    try:
        return dqe_article_service.update_article(article_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/articles")
def get_articles(
    lot: str | None = Query(default=None),
    sous_lot: str | None = Query(default=None),
) -> dict:
    """
    Retourne les articles DQE avec filtres facultatifs.
    """
    return dqe_article_service.list_articles(lot=lot, sous_lot=sous_lot)


@app.delete("/article/{article_id}")
def delete_article(article_id: int) -> dict:
    """
    Supprime un article DQE.
    """
    try:
        dqe_article_service.delete_article(article_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return {"status": "deleted", "article_id": article_id}
