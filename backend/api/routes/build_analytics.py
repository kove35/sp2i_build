"""
Routes FastAPI pour le schema analytique SQLAlchemy.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.db.seed_build_analytics import seed_build_analytics
from backend.db.session import get_db_session
from backend.schemas import (
    BuildAnalyticsDashboardResponse,
    BuildAnalyticsProjectCreatePayload,
    BuildAnalyticsFiltersResponse,
    BuildAnalyticsProjectResponse,
    BuildFactPayload,
    DQEHierarchyItemPayload,
    DQEImportApplyPayload,
    DQEImportPreviewPayload,
    DQEPdfImportPayload,
    DQEPdfPromotePayload,
)
from backend.services.build_analytics_service import BuildAnalyticsService
from backend.services.dashboard_service import DashboardService
from backend.services.dqe_control_service import DQEControlService
from backend.services.dqe_hierarchy_service import DQEHierarchyService
from backend.services.dqe_import_service import DQEImportService


router = APIRouter(prefix="/analytics", tags=["Build Analytics"])
analytics_service = BuildAnalyticsService()
dashboard_service = DashboardService()
dqe_control_service = DQEControlService()
dqe_hierarchy_service = DQEHierarchyService()
dqe_import_service = DQEImportService()


@router.get("/projects", response_model=list[BuildAnalyticsProjectResponse])
def list_build_projects(
    db_session: Session = Depends(get_db_session),
) -> list[BuildAnalyticsProjectResponse]:
    projects = analytics_service.list_projects(db_session)
    return [BuildAnalyticsProjectResponse.model_validate(project) for project in projects]


@router.post("/projects", response_model=BuildAnalyticsProjectResponse)
def create_build_project(
    payload: BuildAnalyticsProjectCreatePayload,
    db_session: Session = Depends(get_db_session),
) -> BuildAnalyticsProjectResponse:
    project = dqe_hierarchy_service.create_project(db_session, payload)
    return BuildAnalyticsProjectResponse.model_validate(project)


@router.get("/default-project")
def get_default_dashboard_project() -> dict:
    project = dashboard_service.get_default_dashboard_project()
    return {"project": project}


@router.post("/default-project/{project_id}")
def set_default_dashboard_project(project_id: int) -> dict:
    return dashboard_service.set_default_dashboard_project(project_id)


@router.post("/reseed")
def reseed_build_analytics() -> dict[str, int | str]:
    """
    Recharge completement le schema analytique a partir des sources historiques.

    Endpoint pratique pour relancer un seed sans passer par le terminal.
    """
    return seed_build_analytics()


@router.post("/dqe/refresh")
def refresh_dqe_pdf_control(payload: DQEPdfImportPayload | None = None) -> dict[str, int | str]:
    """
    Reimporte le DQE PDF source puis regenere les rapports de controle.
    """
    try:
        return dqe_control_service.refresh_source_and_reports(
            pdf_path=payload.pdf_path if payload else None
        )
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/dqe/import")
def import_dqe_pdf_source(payload: DQEPdfImportPayload | None = None) -> dict[str, int | str]:
    """
    Importe un nouveau DQE PDF dans les tables sources.
    """
    try:
        return dqe_control_service.import_source_pdf(pdf_path=payload.pdf_path if payload else None)
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/dqe/promote")
def promote_dqe_pdf_to_analytics(payload: DQEPdfPromotePayload | None = None) -> dict[str, int | str]:
    """
    Promeut une source PDF importee en nouveau projet analytique.
    """
    payload = payload or DQEPdfPromotePayload()
    try:
        return dqe_control_service.promote_source_to_analytics(
            source_file=payload.source_file,
            project_code=payload.project_code,
            project_name=payload.project_name,
            replace_existing=payload.replace_existing,
        )
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/dqe/source-files")
def list_dqe_pdf_sources() -> dict[str, list[str]]:
    """
    Retourne la liste des DQE PDF importes.
    """
    return {"items": dqe_control_service.list_source_files()}


@router.get("/dqe/summary")
def get_dqe_pdf_control_summary(
    source_file: str | None = Query(default=None),
) -> dict:
    """
    Retourne la synthese du controle PDF courant.
    """
    return dqe_control_service.get_summary(source_file=source_file)


@router.get("/dqe/lot-comparison")
def get_dqe_pdf_lot_comparison(
    source_file: str | None = Query(default=None),
) -> dict[str, list[dict]]:
    """
    Retourne les ecarts lot par lot entre le PDF et la base analytique.
    """
    return {"items": dqe_control_service.get_lot_comparison(source_file=source_file)}


@router.get("/dqe/article-comparison")
def get_dqe_pdf_article_comparison(
    source_file: str | None = Query(default=None),
    lot_code: str | None = Query(default=None),
) -> dict[str, list[dict]]:
    """
    Retourne les ecarts article par article, avec filtre facultatif par lot.
    """
    return {
        "items": dqe_control_service.get_article_comparison(
            source_file=source_file,
            lot_code=lot_code,
        )
    }


@router.get("/projects/{project_id}", response_model=BuildAnalyticsProjectResponse)
def get_build_project(
    project_id: int,
    db_session: Session = Depends(get_db_session),
) -> BuildAnalyticsProjectResponse:
    project = analytics_service.get_project(db_session, project_id)
    return BuildAnalyticsProjectResponse.model_validate(project)


@router.get("/projects/{project_id}/filters", response_model=BuildAnalyticsFiltersResponse)
def get_build_project_filters(
    project_id: int,
    db_session: Session = Depends(get_db_session),
) -> BuildAnalyticsFiltersResponse:
    filters = analytics_service.get_project_filters(db_session, project_id)
    return BuildAnalyticsFiltersResponse(**filters)


@router.get("/projects/{project_id}/facts")
def list_build_fact_rows(
    project_id: int,
    lots: list[str] | None = Query(default=None),
    familles: list[str] | None = Query(default=None),
    niveaux: list[str] | None = Query(default=None),
    batiments: list[str] | None = Query(default=None),
    db_session: Session = Depends(get_db_session),
) -> dict:
    items = analytics_service.list_fact_rows(
        db_session,
        project_id,
        {
            "lots": lots or [],
            "familles": familles or [],
            "niveaux": niveaux or [],
            "batiments": batiments or [],
        },
    )
    return {"items": items}


@router.get("/projects/{project_id}/hierarchy-items")
def list_build_hierarchy_items(
    project_id: int,
    batiment: str | None = Query(default=None),
    niveau: str | None = Query(default=None),
    lot: str | None = Query(default=None),
    db_session: Session = Depends(get_db_session),
) -> dict[str, list[dict]]:
    items = dqe_hierarchy_service.list_hierarchy_items(
        db_session,
        project_id,
        batiment=batiment,
        niveau=niveau,
        lot=lot,
    )
    return {"items": items}


@router.post("/projects/{project_id}/hierarchy-items")
def create_build_hierarchy_item(
    project_id: int,
    payload: DQEHierarchyItemPayload,
    db_session: Session = Depends(get_db_session),
) -> dict:
    return dqe_hierarchy_service.save_hierarchy_item(db_session, project_id, payload)


@router.post("/dqe-smart/preview")
def preview_smart_dqe_import(payload: DQEImportPreviewPayload) -> dict:
    return dqe_import_service.preview_import(
        file_path=payload.file_path,
        sheet_name=payload.sheet_name,
        custom_mapping=payload.custom_mapping,
    )


@router.post("/dqe-smart/import")
def import_smart_dqe(
    payload: DQEImportApplyPayload,
    db_session: Session = Depends(get_db_session),
) -> dict:
    return dqe_import_service.apply_import(
        db_session,
        project_id=payload.project_id,
        file_path=payload.file_path,
        sheet_name=payload.sheet_name,
        replace_existing=payload.replace_existing,
        custom_mapping=payload.custom_mapping,
    )


@router.post("/projects/{project_id}/facts")
def create_build_fact_row(
    project_id: int,
    payload: BuildFactPayload,
    db_session: Session = Depends(get_db_session),
) -> dict:
    fact_row = analytics_service.create_fact_row(db_session, project_id, payload)
    db_session.refresh(fact_row)
    return analytics_service.serialize_fact_row(fact_row)


@router.put("/facts/{fact_id}")
def update_build_fact_row(
    fact_id: int,
    payload: BuildFactPayload,
    db_session: Session = Depends(get_db_session),
) -> dict:
    fact_row = analytics_service.update_fact_row(db_session, fact_id, payload)
    db_session.refresh(fact_row)
    return analytics_service.serialize_fact_row(fact_row)


@router.delete("/facts/{fact_id}")
def delete_build_fact_row(
    fact_id: int,
    db_session: Session = Depends(get_db_session),
) -> dict:
    analytics_service.delete_fact_row(db_session, fact_id)
    return {"status": "deleted", "fact_id": fact_id}


@router.get("/projects/{project_id}/dashboard", response_model=BuildAnalyticsDashboardResponse)
def get_build_project_dashboard(
    project_id: int,
    lots: list[str] | None = Query(default=None),
    familles: list[str] | None = Query(default=None),
    niveaux: list[str] | None = Query(default=None),
    batiments: list[str] | None = Query(default=None),
    db_session: Session = Depends(get_db_session),
) -> BuildAnalyticsDashboardResponse:
    payload = analytics_service.get_dashboard_payload(
        db_session,
        project_id,
        {
            "lots": lots or [],
            "familles": familles or [],
            "niveaux": niveaux or [],
            "batiments": batiments or [],
        },
    )
    return BuildAnalyticsDashboardResponse(
        project=BuildAnalyticsProjectResponse.model_validate(payload["project"]),
        kpis=payload["kpis"],
        charts=payload["charts"],
        filters=BuildAnalyticsFiltersResponse(
            lots=payload["filters"]["lots"],
            familles=payload["filters"].get("familles", payload["filters"].get("families", [])),
            niveaux=payload["filters"]["niveaux"],
            batiments=payload["filters"]["batiments"],
        ),
    )
