"""
Services de lecture / ecriture pour le schema analytique SQLAlchemy.
"""

from __future__ import annotations

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from backend.models.build_analytics import (
    BuildArticle,
    BuildBuildingDimension,
    BuildFactMetre,
    BuildFamilyDimension,
    BuildLevelDimension,
    BuildLot,
    BuildProject,
)
from backend.saas_services.capex_engine import CapexEngine
from backend.schemas import BuildFactPayload


class BuildAnalyticsService:
    """
    Service applicatif du schema analytique.
    """

    def __init__(self) -> None:
        self.capex_engine = CapexEngine()

    def list_projects(self, db_session: Session) -> list[BuildProject]:
        """
        Retourne les projets analytiques disponibles.
        """
        return db_session.query(BuildProject).order_by(BuildProject.name.asc()).all()

    def get_project(self, db_session: Session, project_id: int) -> BuildProject:
        """
        Charge un projet ou lève une erreur 404.
        """
        project = (
            db_session.query(BuildProject)
            .filter(BuildProject.id == project_id)
            .one_or_none()
        )
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Projet analytique introuvable.",
            )
        return project

    def build_project_dataframe(self, db_session: Session, project_id: int) -> pd.DataFrame:
        """
        Transforme les lignes de faits SQLAlchemy en DataFrame pandas.
        """
        self.get_project(db_session, project_id)

        fact_rows = (
            db_session.query(BuildFactMetre)
            .options(
                joinedload(BuildFactMetre.article),
                joinedload(BuildFactMetre.lot),
                joinedload(BuildFactMetre.famille),
                joinedload(BuildFactMetre.niveau),
                joinedload(BuildFactMetre.batiment),
            )
            .filter(BuildFactMetre.project_id == project_id)
            .order_by(BuildFactMetre.id.asc())
            .all()
        )

        if not fact_rows:
            return pd.DataFrame(
                columns=[
                    "id",
                    "lot_id",
                    "lot_code",
                    "lot_label",
                    "family_article",
                    "family_code",
                    "code_bpu",
                    "designation",
                    "batiment",
                    "niveau",
                    "decision",
                    "quantity",
                    "montant_local",
                    "montant_import",
                    "source_row_key",
                ]
            )

        return pd.DataFrame(
            [
                {
                    "id": fact.id,
                    "project_id": fact.project_id,
                    "lot_code": fact.lot.code if fact.lot else None,
                    "lot_label": (
                        f"{fact.lot.name} - {fact.lot.description}"
                        if fact.lot and fact.lot.description
                        else (fact.lot.name if fact.lot else None)
                    ),
                    "lot_id": (
                        f"{fact.lot.name} - {fact.lot.description}"
                        if fact.lot and fact.lot.description
                        else (fact.lot.name if fact.lot else None)
                    ),
                    "family_article": fact.famille.label if fact.famille else None,
                    "family_code": fact.famille.code if fact.famille else None,
                    "code_bpu": fact.article.code_bpu if fact.article else None,
                    "designation": fact.article.designation if fact.article else None,
                    "pu_local": float(fact.pu_local or 0),
                    "pu_chine": float(fact.pu_chine or 0) if fact.pu_chine is not None else 0.0,
                    "importable": bool(fact.famille.importable) if fact.famille else False,
                    "risk_score": float(fact.famille.risk_score or 0) if fact.famille else 0.0,
                    "batiment_code": fact.batiment.code if fact.batiment else None,
                    "batiment": fact.batiment.label if fact.batiment else None,
                    "niveau_code": fact.niveau.code if fact.niveau else None,
                    "niveau": fact.niveau.label if fact.niveau else None,
                    "decision": fact.decision,
                    "quantity": float(fact.quantite or 0),
                    "montant_local": float(fact.total_local or 0),
                    "montant_import": float(fact.total_import or 0),
                    "source_row_key": fact.source_row_key,
                }
                for fact in fact_rows
            ]
        )

    def get_project_filters(self, db_session: Session, project_id: int) -> dict[str, list[str]]:
        """
        Retourne les options de filtres disponibles pour un projet.
        """
        dataframe = self.build_project_dataframe(db_session, project_id)
        if dataframe.empty:
            return {"lots": [], "familles": [], "niveaux": [], "batiments": []}

        return {
            "lots": sorted(dataframe["lot_label"].dropna().unique().tolist()),
            "familles": sorted(dataframe["family_article"].dropna().unique().tolist()),
            "niveaux": sorted(dataframe["niveau"].dropna().unique().tolist()),
            "batiments": sorted(dataframe["batiment"].dropna().unique().tolist()),
        }

    def get_dashboard_payload(
        self,
        db_session: Session,
        project_id: int,
        filters: dict,
    ) -> dict:
        """
        Construit le payload dashboard du projet analytique.
        """
        project = self.get_project(db_session, project_id)
        dataframe = self.build_project_dataframe(db_session, project_id)

        engine_filters = {
            "lot_ids": filters.get("lots", []),
            "families": filters.get("familles", []),
            "niveaux": filters.get("niveaux", []),
            "batiments": filters.get("batiments", []),
        }
        payload = self.capex_engine.build_dashboard_payload(dataframe, engine_filters)
        payload["project"] = project
        return payload

    def list_fact_rows(
        self,
        db_session: Session,
        project_id: int,
        filters: dict | None = None,
    ) -> list[dict]:
        """
        Retourne les lignes de faits, avec filtres facultatifs.
        """
        dataframe = self.build_project_dataframe(db_session, project_id)
        filtered_dataframe = self.capex_engine.filter_data(
            dataframe,
            {
                "lot_ids": (filters or {}).get("lots", []),
                "families": (filters or {}).get("familles", []),
                "niveaux": (filters or {}).get("niveaux", []),
                "batiments": (filters or {}).get("batiments", []),
            },
        )
        return filtered_dataframe.to_dict(orient="records")

    def _get_article_by_code(
        self,
        db_session: Session,
        project_id: int,
        code_bpu: str,
    ) -> BuildArticle:
        article = (
            db_session.query(BuildArticle)
            .filter(BuildArticle.project_id == project_id, BuildArticle.code_bpu == code_bpu)
            .one_or_none()
        )
        if article is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Article introuvable pour code_bpu={code_bpu}.",
            )
        return article

    def _find_dimension_id(
        self,
        db_session: Session,
        model_class,
        project_id: int,
        code: str | None,
    ) -> int | None:
        if not code:
            return None

        dimension = (
            db_session.query(model_class)
            .filter(model_class.project_id == project_id, model_class.code == code)
            .one_or_none()
        )
        if dimension is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dimension introuvable pour code={code}.",
            )
        return dimension.id

    def _build_fact_values(
        self,
        db_session: Session,
        project_id: int,
        payload: BuildFactPayload,
    ) -> dict:
        """
        Calcule et normalise les valeurs a enregistrer.
        """
        article = self._get_article_by_code(db_session, project_id, payload.code_bpu)
        lot_id = self._find_dimension_id(
            db_session,
            BuildLot,
            project_id,
            payload.lot_code or article.lot.code,
        )
        famille_id = self._find_dimension_id(
            db_session,
            BuildFamilyDimension,
            project_id,
            payload.famille_code or (article.famille.code if article.famille else None),
        )
        niveau_id = self._find_dimension_id(
            db_session,
            BuildLevelDimension,
            project_id,
            payload.niveau_code,
        )
        batiment_id = self._find_dimension_id(
            db_session,
            BuildBuildingDimension,
            project_id,
            payload.batiment_code,
        )

        total_local = payload.total_local
        if total_local is None:
            total_local = payload.quantite * payload.pu_local

        total_import = payload.total_import
        if total_import is None and payload.pu_chine is not None:
            total_import = payload.quantite * payload.pu_chine

        if payload.decision.upper() == "IMPORT" and total_import is not None:
            capex_optimise = total_import
        else:
            capex_optimise = total_local

        economie = payload.economie
        if economie is None:
            economie = total_local - capex_optimise

        taux_economie = payload.taux_economie
        if taux_economie is None:
            taux_economie = economie / total_local if total_local else 0.0

        return {
            "project_id": project_id,
            "article_id": article.id,
            "lot_id": lot_id,
            "sous_lot_id": article.sous_lot_id,
            "famille_id": famille_id,
            "niveau_id": niveau_id,
            "batiment_id": batiment_id,
            "quantite": payload.quantite,
            "pu_local": payload.pu_local,
            "pu_chine": payload.pu_chine,
            "total_local": total_local,
            "total_import": total_import,
            "economie": economie,
            "taux_economie": taux_economie,
            "decision": payload.decision.upper(),
            "source_row_key": payload.source_row_key,
        }

    def create_fact_row(
        self,
        db_session: Session,
        project_id: int,
        payload: BuildFactPayload,
    ) -> BuildFactMetre:
        """
        Cree une ligne de faits analytique.
        """
        self.get_project(db_session, project_id)
        fact_row = BuildFactMetre(**self._build_fact_values(db_session, project_id, payload))
        db_session.add(fact_row)
        db_session.commit()
        db_session.refresh(fact_row)
        return fact_row

    def update_fact_row(
        self,
        db_session: Session,
        fact_id: int,
        payload: BuildFactPayload,
    ) -> BuildFactMetre:
        """
        Met a jour une ligne de faits analytique.
        """
        fact_row = (
            db_session.query(BuildFactMetre)
            .options(joinedload(BuildFactMetre.article))
            .filter(BuildFactMetre.id == fact_id)
            .one_or_none()
        )
        if fact_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ligne de faits introuvable.",
            )

        values = self._build_fact_values(db_session, fact_row.project_id, payload)
        for field_name, field_value in values.items():
            setattr(fact_row, field_name, field_value)

        db_session.commit()
        db_session.refresh(fact_row)
        return fact_row

    def delete_fact_row(self, db_session: Session, fact_id: int) -> None:
        """
        Supprime une ligne de faits analytique.
        """
        fact_row = (
            db_session.query(BuildFactMetre)
            .filter(BuildFactMetre.id == fact_id)
            .one_or_none()
        )
        if fact_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ligne de faits introuvable.",
            )

        db_session.delete(fact_row)
        db_session.commit()

    def serialize_fact_row(self, fact_row: BuildFactMetre) -> dict:
        """
        Transforme une ligne SQLAlchemy en dictionnaire lisible pour l'API.
        """
        article = fact_row.article
        lot = fact_row.lot
        famille = fact_row.famille
        niveau = fact_row.niveau
        batiment = fact_row.batiment

        return {
            "id": fact_row.id,
            "project_id": fact_row.project_id,
            "article_id": fact_row.article_id,
            "code_bpu": article.code_bpu if article else None,
            "designation": article.designation if article else None,
            "lot": (
                f"{lot.name} - {lot.description}"
                if lot and lot.description
                else (lot.name if lot else None)
            ),
            "famille": famille.label if famille else None,
            "niveau": niveau.label if niveau else None,
            "batiment": batiment.label if batiment else None,
            "quantite": float(fact_row.quantite or 0),
            "pu_local": float(fact_row.pu_local or 0),
            "pu_chine": float(fact_row.pu_chine) if fact_row.pu_chine is not None else None,
            "total_local": float(fact_row.total_local or 0),
            "total_import": (
                float(fact_row.total_import) if fact_row.total_import is not None else None
            ),
            "economie": float(fact_row.economie or 0),
            "taux_economie": float(fact_row.taux_economie or 0),
            "decision": fact_row.decision,
            "source_row_key": fact_row.source_row_key,
        }
