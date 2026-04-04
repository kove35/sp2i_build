"""
Routes multi-projets.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.routes.auth import get_current_user
from backend.contracts.projects import (
    CapexItemCreateRequest,
    CapexItemResponse,
    ProjectCreateRequest,
    ProjectResponse,
)
from backend.db.session import get_db_session
from backend.saas_services.project_service import ProjectService


router = APIRouter(prefix="/saas/projects", tags=["SaaS Projects"])
project_service = ProjectService()


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    db_session: Session = Depends(get_db_session),
    user=Depends(get_current_user),
) -> list[ProjectResponse]:
    projects = project_service.list_projects(db_session, user)
    return [ProjectResponse.model_validate(project) for project in projects]


@router.post("", response_model=ProjectResponse)
def create_project(
    payload: ProjectCreateRequest,
    db_session: Session = Depends(get_db_session),
    user=Depends(get_current_user),
) -> ProjectResponse:
    project = project_service.create_project(db_session, user, payload)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db_session: Session = Depends(get_db_session),
    user=Depends(get_current_user),
) -> ProjectResponse:
    project = project_service.get_project(db_session, user, project_id)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}/items", response_model=list[CapexItemResponse])
def list_project_items(
    project_id: int,
    db_session: Session = Depends(get_db_session),
    user=Depends(get_current_user),
) -> list[CapexItemResponse]:
    items = project_service.list_capex_items(db_session, user, project_id)
    return [CapexItemResponse.model_validate(item) for item in items]


@router.post("/{project_id}/items", response_model=CapexItemResponse)
def create_project_item(
    project_id: int,
    payload: CapexItemCreateRequest,
    db_session: Session = Depends(get_db_session),
    user=Depends(get_current_user),
) -> CapexItemResponse:
    item = project_service.add_capex_item(db_session, user, project_id, payload)
    return CapexItemResponse.model_validate(item)

