"""
Service de gestion hierarchique DQE.

Ce service centralise la creation des dimensions et des lignes de faits
pour une structure metier :

PROJET -> BATIMENT -> NIVEAU -> LOT -> SOUS_LOT -> ARTICLE
"""

from __future__ import annotations

import re
import unicodedata

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
    BuildSousLot,
)
from backend.schemas import BuildAnalyticsProjectCreatePayload, DQEHierarchyItemPayload


class DQEHierarchyService:
    """
    Service applicatif pour la saisie / import DQE multi-dimensionnelle.
    """

    @staticmethod
    def _slugify(value: str, prefix: str) -> str:
        """
        Construit un code technique stable a partir d'un libelle.
        """
        normalized = unicodedata.normalize("NFKD", value)
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = re.sub(r"[^A-Za-z0-9]+", "_", normalized.upper()).strip("_")
        return f"{prefix}_{normalized or 'DEFAULT'}"

    def create_project(
        self,
        db_session: Session,
        payload: BuildAnalyticsProjectCreatePayload,
    ) -> BuildProject:
        """
        Cree un projet analytique s'il n'existe pas deja.
        """
        existing_project = (
            db_session.query(BuildProject)
            .filter(BuildProject.code == payload.code.strip())
            .one_or_none()
        )
        if existing_project is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un projet analytique avec ce code existe deja.",
            )

        project = BuildProject(
            code=payload.code.strip(),
            name=payload.name.strip(),
            description=payload.description.strip() if payload.description else None,
            devise=payload.devise.strip(),
            statut=payload.statut.strip(),
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        return project

    def get_project(self, db_session: Session, project_id: int) -> BuildProject:
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

    def _get_or_create_building(
        self,
        db_session: Session,
        project_id: int,
        label: str,
    ) -> BuildBuildingDimension:
        code = self._slugify(label, "BAT")
        building = (
            db_session.query(BuildBuildingDimension)
            .filter(
                BuildBuildingDimension.project_id == project_id,
                BuildBuildingDimension.code == code,
            )
            .one_or_none()
        )
        if building is None:
            building = BuildBuildingDimension(
                project_id=project_id,
                code=code,
                label=label,
                display_order=0,
            )
            db_session.add(building)
            db_session.flush()
        return building

    def _get_or_create_level(
        self,
        db_session: Session,
        project_id: int,
        label: str,
    ) -> BuildLevelDimension:
        code = self._slugify(label, "NIV")
        level = (
            db_session.query(BuildLevelDimension)
            .filter(
                BuildLevelDimension.project_id == project_id,
                BuildLevelDimension.code == code,
            )
            .one_or_none()
        )
        if level is None:
            level = BuildLevelDimension(
                project_id=project_id,
                code=code,
                label=label,
                display_order=0,
            )
            db_session.add(level)
            db_session.flush()
        return level

    def _get_or_create_lot(
        self,
        db_session: Session,
        project_id: int,
        label: str,
    ) -> BuildLot:
        code = self._slugify(label, "LOT")
        lot = (
            db_session.query(BuildLot)
            .filter(BuildLot.project_id == project_id, BuildLot.code == code)
            .one_or_none()
        )
        if lot is None:
            lot = BuildLot(
                project_id=project_id,
                code=code,
                name=label,
                description=label,
                display_order=0,
            )
            db_session.add(lot)
            db_session.flush()
        return lot

    def _get_or_create_sous_lot(
        self,
        db_session: Session,
        project_id: int,
        lot_id: int,
        label: str,
    ) -> BuildSousLot:
        code = self._slugify(label, "SLOT")
        sous_lot = (
            db_session.query(BuildSousLot)
            .filter(BuildSousLot.lot_id == lot_id, BuildSousLot.code == code)
            .one_or_none()
        )
        if sous_lot is None:
            sous_lot = BuildSousLot(
                project_id=project_id,
                lot_id=lot_id,
                code=code,
                name=label,
                description=label,
                display_order=0,
            )
            db_session.add(sous_lot)
            db_session.flush()
        return sous_lot

    def _get_or_create_family(
        self,
        db_session: Session,
        project_id: int,
        label: str,
        lot_label: str | None = None,
    ) -> BuildFamilyDimension:
        code = self._slugify(label, "FAM")
        family = (
            db_session.query(BuildFamilyDimension)
            .filter(
                BuildFamilyDimension.project_id == project_id,
                BuildFamilyDimension.code == code,
            )
            .one_or_none()
        )
        if family is None:
            family = BuildFamilyDimension(
                project_id=project_id,
                code=code,
                label=label,
                category=lot_label,
                importable=True,
                risk_score=0.0,
            )
            db_session.add(family)
            db_session.flush()
        return family

    def _get_or_create_article(
        self,
        db_session: Session,
        project_id: int,
        lot: BuildLot,
        sous_lot: BuildSousLot,
        family: BuildFamilyDimension,
        payload: DQEHierarchyItemPayload,
    ) -> BuildArticle:
        code_bpu = payload.code_bpu or self._slugify(
            f"{lot.name}_{sous_lot.name}_{payload.designation}",
            "BPU",
        )
        article = (
            db_session.query(BuildArticle)
            .filter(BuildArticle.project_id == project_id, BuildArticle.code_bpu == code_bpu)
            .one_or_none()
        )
        if article is None:
            article = BuildArticle(
                project_id=project_id,
                lot_id=lot.id,
                sous_lot_id=sous_lot.id,
                famille_id=family.id,
                code_bpu=code_bpu,
                designation=payload.designation,
                unite=payload.unite,
                type_cout="DQE",
                pu_local_reference=payload.pu_local,
                pu_chine_reference=payload.pu_chine,
            )
            db_session.add(article)
            db_session.flush()
        else:
            article.lot_id = lot.id
            article.sous_lot_id = sous_lot.id
            article.famille_id = family.id
            article.designation = payload.designation
            article.unite = payload.unite
            article.pu_local_reference = payload.pu_local
            article.pu_chine_reference = payload.pu_chine
        return article

    def save_hierarchy_item(
        self,
        db_session: Session,
        project_id: int,
        payload: DQEHierarchyItemPayload,
    ) -> dict:
        """
        Cree une ligne DQE complete avec ses dimensions si besoin.
        """
        self.get_project(db_session, project_id)

        building = self._get_or_create_building(db_session, project_id, payload.batiment)
        level = self._get_or_create_level(db_session, project_id, payload.niveau)
        lot = self._get_or_create_lot(db_session, project_id, payload.lot)
        sous_lot = self._get_or_create_sous_lot(db_session, project_id, lot.id, payload.sous_lot)
        family = self._get_or_create_family(
            db_session,
            project_id,
            payload.famille or payload.sous_lot,
            lot.name,
        )
        article = self._get_or_create_article(
            db_session,
            project_id,
            lot,
            sous_lot,
            family,
            payload,
        )

        montant_local = payload.quantite * payload.pu_local
        montant_import = (
            payload.quantite * payload.pu_chine if payload.pu_chine is not None else None
        )
        economie = (
            montant_local - montant_import if montant_import is not None else 0.0
        )
        decision = "IMPORT" if montant_import is not None and economie > 0 else "LOCAL"
        taux_economie = economie / montant_local if montant_local else 0.0
        source_row_key = payload.source_row_key or self._slugify(
            f"{project_id}_{building.code}_{level.code}_{lot.code}_{sous_lot.code}_{article.code_bpu}",
            "MANUAL",
        )

        fact_row = (
            db_session.query(BuildFactMetre)
            .filter(
                BuildFactMetre.project_id == project_id,
                BuildFactMetre.source_row_key == source_row_key,
            )
            .one_or_none()
        )

        if fact_row is None:
            fact_row = BuildFactMetre(
                project_id=project_id,
                article_id=article.id,
                lot_id=lot.id,
                sous_lot_id=sous_lot.id,
                famille_id=family.id,
                niveau_id=level.id,
                batiment_id=building.id,
                quantite=payload.quantite,
                pu_local=payload.pu_local,
                pu_chine=payload.pu_chine,
                total_local=montant_local,
                total_import=montant_import,
                economie=economie,
                taux_economie=taux_economie,
                decision=decision,
                source_row_key=source_row_key,
            )
            db_session.add(fact_row)
        else:
            fact_row.article_id = article.id
            fact_row.lot_id = lot.id
            fact_row.sous_lot_id = sous_lot.id
            fact_row.famille_id = family.id
            fact_row.niveau_id = level.id
            fact_row.batiment_id = building.id
            fact_row.quantite = payload.quantite
            fact_row.pu_local = payload.pu_local
            fact_row.pu_chine = payload.pu_chine
            fact_row.total_local = montant_local
            fact_row.total_import = montant_import
            fact_row.economie = economie
            fact_row.taux_economie = taux_economie
            fact_row.decision = decision

        db_session.commit()
        db_session.refresh(fact_row)

        return {
            "project_id": project_id,
            "fact_id": fact_row.id,
            "batiment": building.label,
            "niveau": level.label,
            "lot": lot.name,
            "sous_lot": sous_lot.name,
            "designation": article.designation,
            "quantite": float(fact_row.quantite or 0),
            "montant_local": float(fact_row.total_local or 0),
            "montant_import": float(fact_row.total_import or 0)
            if fact_row.total_import is not None
            else None,
            "economie": float(fact_row.economie or 0),
            "decision": fact_row.decision,
        }

    def list_hierarchy_items(
        self,
        db_session: Session,
        project_id: int,
        batiment: str | None = None,
        niveau: str | None = None,
        lot: str | None = None,
    ) -> list[dict]:
        """
        Retourne les lignes hiérarchiques pour affichage Streamlit.
        """
        query = (
            db_session.query(BuildFactMetre)
            .options(
                joinedload(BuildFactMetre.article),
                joinedload(BuildFactMetre.lot),
                joinedload(BuildFactMetre.sous_lot),
                joinedload(BuildFactMetre.famille),
                joinedload(BuildFactMetre.niveau),
                joinedload(BuildFactMetre.batiment),
            )
            .filter(BuildFactMetre.project_id == project_id)
        )

        if batiment:
            query = query.join(BuildFactMetre.batiment).filter(
                BuildBuildingDimension.label == batiment
            )
        if niveau:
            query = query.join(BuildFactMetre.niveau).filter(BuildLevelDimension.label == niveau)
        if lot:
            query = query.join(BuildFactMetre.lot).filter(BuildLot.name == lot)

        fact_rows = query.order_by(BuildFactMetre.id.desc()).all()

        return [
            {
                "id": fact.id,
                "batiment": fact.batiment.label if fact.batiment else "Global",
                "niveau": fact.niveau.label if fact.niveau else "Global",
                "lot": fact.lot.name if fact.lot else None,
                "sous_lot": fact.sous_lot.name if fact.sous_lot else None,
                "famille": fact.famille.label if fact.famille else None,
                "code_bpu": fact.article.code_bpu if fact.article else None,
                "designation": fact.article.designation if fact.article else None,
                "unite": fact.article.unite if fact.article else None,
                "quantite": float(fact.quantite or 0),
                "pu_local": float(fact.pu_local or 0),
                "pu_chine": float(fact.pu_chine or 0) if fact.pu_chine is not None else None,
                "montant_local": float(fact.total_local or 0),
                "montant_import": float(fact.total_import or 0)
                if fact.total_import is not None
                else None,
                "economie": float(fact.economie or 0),
                "decision": fact.decision,
            }
            for fact in fact_rows
        ]
