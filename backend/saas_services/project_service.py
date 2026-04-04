"""
Services multi-projets.
"""

from __future__ import annotations

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.contracts.projects import CapexItemCreateRequest, ProjectCreateRequest
from backend.models.capex_item import ProjectCapexItem
from backend.models.project import Project
from backend.models.user import User


class ProjectService:
    """
    Gere les projets et leurs lignes CAPEX.
    """

    def create_project(
        self,
        db_session: Session,
        owner: User,
        payload: ProjectCreateRequest,
    ) -> Project:
        existing_project = (
            db_session.query(Project).filter(Project.code == payload.code.strip()).first()
        )
        if existing_project:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un projet existe deja avec ce code.",
            )

        project = Project(
            name=payload.name.strip(),
            code=payload.code.strip().upper(),
            description=(payload.description or "").strip() or None,
            owner_id=owner.id,
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        return project

    def list_projects(self, db_session: Session, owner: User) -> list[Project]:
        return (
            db_session.query(Project)
            .filter(Project.owner_id == owner.id)
            .order_by(Project.id.desc())
            .all()
        )

    def get_project(self, db_session: Session, owner: User, project_id: int) -> Project:
        project = (
            db_session.query(Project)
            .filter(Project.id == project_id, Project.owner_id == owner.id)
            .first()
        )
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Projet introuvable.",
            )
        return project

    def add_capex_item(
        self,
        db_session: Session,
        owner: User,
        project_id: int,
        payload: CapexItemCreateRequest,
    ) -> ProjectCapexItem:
        self.get_project(db_session, owner, project_id)

        item = ProjectCapexItem(
            project_id=project_id,
            lot_id=payload.lot_id.strip(),
            family_article=payload.family_article.strip(),
            code_bpu=payload.code_bpu.strip(),
            batiment=payload.batiment.strip(),
            niveau=payload.niveau.strip(),
            decision=payload.decision.strip().upper(),
            quantity=payload.quantity,
            montant_local=payload.montant_local,
            montant_import=payload.montant_import,
            risk_score=payload.risk_score,
            import_score=payload.import_score,
            source_index=payload.source_index,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        return item

    def list_capex_items(
        self,
        db_session: Session,
        owner: User,
        project_id: int,
    ) -> list[ProjectCapexItem]:
        self.get_project(db_session, owner, project_id)
        return (
            db_session.query(ProjectCapexItem)
            .filter(ProjectCapexItem.project_id == project_id)
            .order_by(ProjectCapexItem.id.desc())
            .all()
        )

    def build_project_dataframe(
        self,
        db_session: Session,
        owner: User,
        project_id: int,
    ) -> pd.DataFrame:
        items = self.list_capex_items(db_session, owner, project_id)
        if not items:
            return pd.DataFrame(
                columns=[
                    "lot_id",
                    "family_article",
                    "code_bpu",
                    "batiment",
                    "niveau",
                    "decision",
                    "quantity",
                    "montant_local",
                    "montant_import",
                    "risk_score",
                    "import_score",
                    "source_index",
                ]
            )

        return pd.DataFrame(
            [
                {
                    "id": item.id,
                    "lot_id": item.lot_id,
                    "family_article": item.family_article,
                    "code_bpu": item.code_bpu,
                    "batiment": item.batiment,
                    "niveau": item.niveau,
                    "decision": item.decision,
                    "quantity": item.quantity,
                    "montant_local": item.montant_local,
                    "montant_import": item.montant_import,
                    "risk_score": item.risk_score,
                    "import_score": item.import_score,
                    "source_index": item.source_index,
                }
                for item in items
            ]
        )
