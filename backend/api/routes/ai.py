"""
Routes de recommandation import.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.routes.auth import get_current_user
from backend.db.session import get_db_session
from backend.saas_services.import_advisor import ImportAdvisor
from backend.saas_services.project_service import ProjectService


router = APIRouter(prefix="/saas/projects", tags=["SaaS AI"])
project_service = ProjectService()
import_advisor = ImportAdvisor()


@router.get("/{project_id}/recommendations")
def get_import_recommendations(
    project_id: int,
    db_session: Session = Depends(get_db_session),
    user=Depends(get_current_user),
) -> dict:
    dataframe = project_service.build_project_dataframe(db_session, user, project_id)
    return import_advisor.build_recommendations(project_id, dataframe)
