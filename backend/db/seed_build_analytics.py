"""
Seed du schema analytique SQLAlchemy a partir des tables sources SQLite.

Usage :
    python -m backend.db.seed_build_analytics

Ce script :
- initialise les tables SQLAlchemy si besoin
- lit les donnees sources dans sp2i_build.db
- alimente le schema analytique dans sp2i_saas.db

Le seed est idempotent :
- les dimensions sont mises a jour si elles existent deja
- les articles sont mis a jour via leur code BPU
- les faits sont mis a jour via source_row_key
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from sqlalchemy.orm import Session

from backend.config import DATABASE_PATH
from backend.db.session import SessionLocal, initialize_all_sqlalchemy_tables
from backend.models.build_analytics import (
    BuildArticle,
    BuildBuildingDimension,
    BuildFactMetre,
    BuildFamilyDimension,
    BuildLevelDimension,
    BuildLot,
    BuildProject,
)


def _open_source_connection() -> sqlite3.Connection:
    """
    Ouvre la base source historique SQLite.
    """
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _normalize_text(value: str | None) -> str | None:
    """
    Nettoie un texte simple.

    On garde la fonction volontairement minimale pour qu'elle soit lisible
    et facile a reutiliser ailleurs.
    """
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _extract_lot_id(value: str | None) -> int | None:
    """
    Extrait le numero d'un lot a partir d'un libelle comme :
    - LOT 12
    - L0T 12
    - L12
    """
    if value is None:
        return None

    match = re.search(r"(\d+)", value)
    if not match:
        return None
    return int(match.group(1))


def _get_or_create_project(
    db_session: Session,
    source_connection: sqlite3.Connection,
) -> BuildProject:
    """
    Cree ou met a jour le projet principal.
    """
    source_project = source_connection.execute(
        """
        SELECT projet_id, nom_projet, statut, devise
        FROM t_projet
        ORDER BY id
        LIMIT 1
        """
    ).fetchone()

    if source_project is None:
        raise ValueError("Aucun projet source n'a ete trouve dans t_projet.")

    project_code = source_project["projet_id"]
    project = (
        db_session.query(BuildProject)
        .filter(BuildProject.code == project_code)
        .one_or_none()
    )

    if project is None:
        project = BuildProject(
            code=project_code,
            name=source_project["nom_projet"],
            statut=_normalize_text(source_project["statut"]) or "draft",
            devise=_normalize_text(source_project["devise"]) or "FCFA",
            description="Projet charge depuis les tables historiques SP2I_Build.",
        )
        db_session.add(project)
        db_session.flush()
    else:
        project.name = source_project["nom_projet"]
        project.statut = _normalize_text(source_project["statut"]) or project.statut
        project.devise = _normalize_text(source_project["devise"]) or project.devise

    return project


def _seed_lots(
    db_session: Session,
    source_connection: sqlite3.Connection,
    project: BuildProject,
) -> dict[int, BuildLot]:
    """
    Charge les lots depuis t_lot.

    Retourne un dictionnaire {lot_id_source: objet_sqlalchemy}.
    """
    lot_map: dict[int, BuildLot] = {}

    source_rows = source_connection.execute(
        """
        SELECT lot_id, code_lot, nom_lot, description_lot, ordre_lot
        FROM t_lot
        ORDER BY lot_id
        """
    ).fetchall()

    for row in source_rows:
        source_lot_id = row["lot_id"]
        lot_code = _normalize_text(row["code_lot"]) or f"L{source_lot_id:02d}"
        lot_name = _normalize_text(row["nom_lot"]) or f"LOT {source_lot_id}"
        lot_description = _normalize_text(row["description_lot"])

        lot = (
            db_session.query(BuildLot)
            .filter(BuildLot.project_id == project.id, BuildLot.code == lot_code)
            .one_or_none()
        )

        if lot is None:
            lot = BuildLot(
                project_id=project.id,
                code=lot_code,
                name=lot_name,
                description=lot_description,
                display_order=row["ordre_lot"] or source_lot_id,
            )
            db_session.add(lot)
            db_session.flush()
        else:
            lot.name = lot_name
            lot.description = lot_description
            lot.display_order = row["ordre_lot"] or lot.display_order

        lot_map[source_lot_id] = lot

    return lot_map


def _seed_families(
    db_session: Session,
    source_connection: sqlite3.Connection,
    project: BuildProject,
) -> dict[str, BuildFamilyDimension]:
    """
    Charge les familles d'articles.
    """
    family_map: dict[str, BuildFamilyDimension] = {}

    source_rows = source_connection.execute(
        """
        SELECT fam_article_id, code_fam_article, libelle_fam_article, fam_metier_id, importable, risque_import
        FROM dim_fam_article
        ORDER BY fam_article_id
        """
    ).fetchall()

    for row in source_rows:
        family_code = row["fam_article_id"]
        family = (
            db_session.query(BuildFamilyDimension)
            .filter(
                BuildFamilyDimension.project_id == project.id,
                BuildFamilyDimension.code == family_code,
            )
            .one_or_none()
        )

        if family is None:
            family = BuildFamilyDimension(
                project_id=project.id,
                code=family_code,
                label=_normalize_text(row["libelle_fam_article"]) or family_code,
                category=_normalize_text(row["fam_metier_id"]),
                importable=bool(row["importable"]),
                risk_score=float(row["risque_import"] or 0),
            )
            db_session.add(family)
            db_session.flush()
        else:
            family.label = _normalize_text(row["libelle_fam_article"]) or family.label
            family.category = _normalize_text(row["fam_metier_id"])
            family.importable = bool(row["importable"])
            family.risk_score = float(row["risque_import"] or 0)

        family_map[family_code] = family

    return family_map


def _seed_buildings(
    db_session: Session,
    source_connection: sqlite3.Connection,
    project: BuildProject,
) -> dict[str, BuildBuildingDimension]:
    """
    Charge les batiments depuis le staging.
    """
    building_map: dict[str, BuildBuildingDimension] = {}

    source_rows = source_connection.execute(
        """
        SELECT DISTINCT batiment_id
        FROM staging
        WHERE batiment_id IS NOT NULL AND TRIM(batiment_id) <> ''
        ORDER BY batiment_id
        """
    ).fetchall()

    for index, row in enumerate(source_rows, start=1):
        building_code = row["batiment_id"]
        building_label = building_code.replace("BAT_", "").replace("_", " ").title()
        building = (
            db_session.query(BuildBuildingDimension)
            .filter(
                BuildBuildingDimension.project_id == project.id,
                BuildBuildingDimension.code == building_code,
            )
            .one_or_none()
        )

        if building is None:
            building = BuildBuildingDimension(
                project_id=project.id,
                code=building_code,
                label=building_label,
                display_order=index,
            )
            db_session.add(building)
            db_session.flush()
        else:
            building.label = building_label
            building.display_order = index

        building_map[building_code] = building

    return building_map


def _seed_levels(
    db_session: Session,
    source_connection: sqlite3.Connection,
    project: BuildProject,
) -> dict[str, BuildLevelDimension]:
    """
    Charge les niveaux depuis le staging.
    """
    level_map: dict[str, BuildLevelDimension] = {}

    source_rows = source_connection.execute(
        """
        SELECT niveau_id, COUNT(*) AS row_count
        FROM staging
        WHERE niveau_id IS NOT NULL AND TRIM(niveau_id) <> ''
        GROUP BY niveau_id
        ORDER BY row_count DESC, niveau_id
        """
    ).fetchall()

    for index, row in enumerate(source_rows, start=1):
        level_code = row["niveau_id"]
        level = (
            db_session.query(BuildLevelDimension)
            .filter(
                BuildLevelDimension.project_id == project.id,
                BuildLevelDimension.code == level_code,
            )
            .one_or_none()
        )

        if level is None:
            level = BuildLevelDimension(
                project_id=project.id,
                code=level_code,
                label=level_code,
                display_order=index,
            )
            db_session.add(level)
            db_session.flush()
        else:
            level.label = level_code
            level.display_order = index

        level_map[level_code] = level

    return level_map


def _build_lot_fallback_map(source_connection: sqlite3.Connection) -> dict[str, int]:
    """
    Construit un mapping code_bpu -> lot_id a partir du BPU local.

    Ce fallback permet de corriger certains trous du staging,
    par exemple le cas du lot 12 / ascenseur.
    """
    fallback_map: dict[str, int] = {}

    source_rows = source_connection.execute(
        """
        SELECT code_bpu, lot
        FROM raw_bpu_local
        WHERE code_bpu IS NOT NULL
        """
    ).fetchall()

    for row in source_rows:
        source_lot_id = _extract_lot_id(row["lot"])
        if source_lot_id is not None:
            fallback_map[row["code_bpu"]] = source_lot_id

    return fallback_map


def _seed_articles(
    db_session: Session,
    source_connection: sqlite3.Connection,
    project: BuildProject,
    lot_map: dict[int, BuildLot],
    family_map: dict[str, BuildFamilyDimension],
) -> dict[str, BuildArticle]:
    """
    Charge le catalogue article depuis le staging.
    """
    article_map: dict[str, BuildArticle] = {}
    lot_fallback_map = _build_lot_fallback_map(source_connection)

    source_rows = source_connection.execute(
        """
        SELECT
            code_bpu,
            designation,
            unite,
            type_cout,
            lot_id,
            fam_article_id,
            pu_local,
            pu_chine_fob
        FROM staging
        GROUP BY code_bpu
        ORDER BY code_bpu
        """
    ).fetchall()

    for row in source_rows:
        code_bpu = row["code_bpu"]
        source_lot_id = row["lot_id"]
        if source_lot_id is None:
            source_lot_id = lot_fallback_map.get(code_bpu)

        lot = lot_map.get(source_lot_id)
        if lot is None:
            # Si un article reste sans lot resolu, on le saute volontairement.
            # Cela evite de charger une reference incoherente dans le modele cible.
            continue

        family = family_map.get(row["fam_article_id"])

        article = (
            db_session.query(BuildArticle)
            .filter(BuildArticle.project_id == project.id, BuildArticle.code_bpu == code_bpu)
            .one_or_none()
        )

        if article is None:
            article = BuildArticle(
                project_id=project.id,
                lot_id=lot.id,
                sous_lot_id=None,
                famille_id=family.id if family else None,
                code_bpu=code_bpu,
                designation=row["designation"],
                unite=row["unite"],
                type_cout=_normalize_text(row["type_cout"]),
                pu_local_reference=float(row["pu_local"] or 0),
                pu_chine_reference=(
                    float(row["pu_chine_fob"]) if row["pu_chine_fob"] is not None else None
                ),
            )
            db_session.add(article)
            db_session.flush()
        else:
            article.lot_id = lot.id
            article.famille_id = family.id if family else None
            article.designation = row["designation"]
            article.unite = row["unite"]
            article.type_cout = _normalize_text(row["type_cout"])
            article.pu_local_reference = float(row["pu_local"] or 0)
            article.pu_chine_reference = (
                float(row["pu_chine_fob"]) if row["pu_chine_fob"] is not None else None
            )

        article_map[code_bpu] = article

    return article_map


def _seed_fact_rows(
    db_session: Session,
    source_connection: sqlite3.Connection,
    project: BuildProject,
    lot_map: dict[int, BuildLot],
    family_map: dict[str, BuildFamilyDimension],
    building_map: dict[str, BuildBuildingDimension],
    level_map: dict[str, BuildLevelDimension],
    article_map: dict[str, BuildArticle],
) -> int:
    """
    Charge la table de faits a partir du staging.

    Retourne le nombre de lignes chargees / mises a jour.
    """
    row_count = 0
    lot_fallback_map = _build_lot_fallback_map(source_connection)

    source_rows = source_connection.execute(
        """
        SELECT *
        FROM staging
        ORDER BY id
        """
    ).fetchall()

    for row in source_rows:
        code_bpu = row["code_bpu"]
        article = article_map.get(code_bpu)
        if article is None:
            continue

        source_lot_id = row["lot_id"]
        if source_lot_id is None:
            source_lot_id = lot_fallback_map.get(code_bpu)

        lot = lot_map.get(source_lot_id)
        building = building_map.get(row["batiment_id"])
        level = level_map.get(row["niveau_id"])
        family = family_map.get(row["fam_article_id"])
        source_row_key = f"staging:{row['id']}"

        fact_row = (
            db_session.query(BuildFactMetre)
            .filter(
                BuildFactMetre.project_id == project.id,
                BuildFactMetre.source_row_key == source_row_key,
            )
            .one_or_none()
        )

        fact_values = {
            "project_id": project.id,
            "article_id": article.id,
            "lot_id": lot.id if lot else article.lot_id,
            "sous_lot_id": None,
            "famille_id": family.id if family else article.famille_id,
            "niveau_id": level.id if level else None,
            "batiment_id": building.id if building else None,
            "quantite": float(row["qte"] or 0),
            "pu_local": float(row["pu_local"] or 0),
            "pu_chine": float(row["pu_chine_fob"]) if row["pu_chine_fob"] is not None else None,
            "total_local": float(row["montant_local"] or 0),
            "total_import": (
                float(row["montant_import"]) if row["montant_import"] is not None else None
            ),
            "economie": float(row["economie_nette"] or 0),
            "taux_economie": float(row["taux_economie"] or 0),
            "decision": _normalize_text(row["decision"]) or "LOCAL",
            "source_row_key": source_row_key,
        }

        if fact_row is None:
            fact_row = BuildFactMetre(**fact_values)
            db_session.add(fact_row)
        else:
            for field_name, field_value in fact_values.items():
                setattr(fact_row, field_name, field_value)

        row_count += 1

    return row_count


def seed_build_analytics() -> dict[str, int | str]:
    """
    Point d'entree principal du seed.
    """
    initialize_all_sqlalchemy_tables()

    with _open_source_connection() as source_connection:
        db_session = SessionLocal()
        try:
            project = _get_or_create_project(db_session, source_connection)
            lot_map = _seed_lots(db_session, source_connection, project)
            family_map = _seed_families(db_session, source_connection, project)
            building_map = _seed_buildings(db_session, source_connection, project)
            level_map = _seed_levels(db_session, source_connection, project)
            article_map = _seed_articles(
                db_session,
                source_connection,
                project,
                lot_map,
                family_map,
            )
            fact_count = _seed_fact_rows(
                db_session,
                source_connection,
                project,
                lot_map,
                family_map,
                building_map,
                level_map,
                article_map,
            )

            db_session.commit()
            return {
                "project_code": project.code,
                "lots": len(lot_map),
                "familles": len(family_map),
                "batiments": len(building_map),
                "niveaux": len(level_map),
                "articles": len(article_map),
                "fact_rows": fact_count,
                "source_database": str(Path(DATABASE_PATH).name),
            }
        except Exception:
            db_session.rollback()
            raise
        finally:
            db_session.close()


def main() -> None:
    """
    Point d'entree CLI.
    """
    result = seed_build_analytics()
    print("Seed analytique termine :")
    for key, value in result.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
