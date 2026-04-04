"""
Routes dashboard premium.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.routes.auth import get_current_user
from backend.db.session import get_db_session
from backend.saas_services.capex_engine import CapexEngine
from backend.saas_services.project_service import ProjectService


router = APIRouter(prefix="/saas/projects", tags=["SaaS Dashboard"])
project_service = ProjectService()
capex_engine = CapexEngine()


@router.get("/{project_id}/dashboard")
def get_project_dashboard(
    project_id: int,
    lot_ids: list[str] | None = Query(default=None),
    families: list[str] | None = Query(default=None),
    niveaux: list[str] | None = Query(default=None),
    batiments: list[str] | None = Query(default=None),
    db_session: Session = Depends(get_db_session),
    user=Depends(get_current_user),
) -> dict:
    dataframe = project_service.build_project_dataframe(db_session, user, project_id)
    filters = {
        "lot_ids": lot_ids or [],
        "families": families or [],
        "niveaux": niveaux or [],
        "batiments": batiments or [],
    }
    return capex_engine.build_dashboard_payload(dataframe, filters)

