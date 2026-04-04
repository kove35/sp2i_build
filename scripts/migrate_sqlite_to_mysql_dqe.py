"""ETL SQLite -> MySQL pour reconstruire le DQE SP2I_BUILD.

Ce script lit la base SQLite locale ``sp2i_build.db`` puis alimente le modele
MySQL cible defini dans ``sql/sp2i_build_mysql_upgrade.sql``.

Objectifs :
- garder le PDF importe comme source de verite DQE ;
- reconstruire la hierarchie chantier -> projet -> batiment -> niveau -> lot ;
- creer les sous-lots et prestations a partir des lignes PDF ;
- ventiler chaque prestation sur un batiment et un niveau.

Usage exemple :
    python scripts/migrate_sqlite_to_mysql_dqe.py ^
        --target-url "mysql+pymysql://user:password@localhost:3306/sp2i_build"

Mode simulation :
    python scripts/migrate_sqlite_to_mysql_dqe.py --dry-run
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import NoSuchModuleError


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_PATH = ROOT_DIR / "sp2i_build.db"
DEFAULT_PROJECT_SOURCE_ID = "PNR_MEDICAL_CENTER"
DEFAULT_PROJECT_CODE = "SP2I_BUILD"
DEFAULT_PROJECT_NAME = "Centre medical Pointe-Noire"
DEFAULT_DQE_VERSION = "DQE_2025_08_13"


@dataclass
class MigrationContext:
    chantier_id: int
    projet_id: int
    version_id: int
    responsable_id: int


def normalize_text(value: Any) -> str:
    """Normalise une chaine pour faciliter la detection metier."""
    if value is None:
        return ""
    text_value = str(value).strip()
    normalized = unicodedata.normalize("NFKD", text_value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text).upper()


def slugify(value: Any) -> str:
    """Construit un code lisible et stable en snake-like upper."""
    normalized = normalize_text(value)
    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"[^A-Z0-9 ]", "", normalized)
    return re.sub(r"\s+", "_", normalized).strip("_") or "GENERAL"


def infer_building_code(section_label: Any, designation: Any) -> str:
    """Deduit le batiment depuis les textes du PDF."""
    combined = " ".join(filter(None, [normalize_text(section_label), normalize_text(designation)]))
    if "ANNEXE" in combined:
        return "BAT_ANNEXE"
    if "BATIMENT PRINCIPAL" in combined or "PRINCIPAL" in combined:
        return "BAT_PRINCIPAL"

    normalized_section = normalize_text(section_label)
    principal_levels = {
        "FONDATIONS",
        "RDC",
        "REZ DE CHAUSSEE",
        "ETAGE 1",
        "ETAGE 2",
        "DUPLEX 1",
        "DUPLEX 2",
        "TERRASSE",
    }
    if normalized_section in principal_levels:
        return "BAT_PRINCIPAL"
    return "BAT_GLOBAL"


def infer_level_code(section_label: Any, designation: Any) -> str:
    """Deduit le niveau depuis la section PDF ou la designation."""
    section = normalize_text(section_label)
    designation_text = normalize_text(designation)

    section_map = {
        "REZ DE CHAUSSEE": "RDC",
        "RDC": "RDC",
        "ETAGE 1": "ETAGE 1",
        "ETAGE 2": "ETAGE 2",
        "DUPLEX 1": "DUPLEX 1",
        "DUPLEX 2": "DUPLEX 2",
        "TERRASSE": "TERRASSE",
        "FONDATIONS": "FONDATIONS",
        "BATIMENT PRINCIPAL": "GLOBAL",
        "BATIMENT ANNEXE": "GLOBAL",
    }
    if section in section_map:
        return section_map[section]

    if "(RDC)" in designation_text:
        return "RDC"
    if "(ETAGE 1)" in designation_text:
        return "ETAGE 1"
    if "(ETAGE 2)" in designation_text:
        return "ETAGE 2"
    if "DUPLEX 1" in designation_text:
        return "DUPLEX 1"
    if "DUPLEX 2" in designation_text:
        return "DUPLEX 2"
    if "TERRASSE" in designation_text:
        return "TERRASSE"
    if "FONDATION" in designation_text:
        return "FONDATIONS"
    return "GLOBAL"


def infer_sous_lot_label(section_label: Any) -> str:
    """Transforme la section PDF en sous-lot metier."""
    section = normalize_text(section_label)
    if section in {"", "BATIMENT PRINCIPAL", "BATIMENT ANNEXE"}:
        return "GENERAL"
    return str(section_label).strip() if section_label else "GENERAL"


def require_mysql_engine(target_url: str) -> Engine:
    """Construit l'engine MySQL et retourne une erreur pedagogique si le driver manque."""
    try:
        return create_engine(target_url, future=True)
    except NoSuchModuleError as exc:
        raise RuntimeError(
            "Le driver MySQL SQLAlchemy est absent. "
            "Installez par exemple 'pymysql' puis relancez avec un URL "
            "de type mysql+pymysql://user:password@host:3306/base."
        ) from exc


def load_source_data(sqlite_path: Path) -> dict[str, pd.DataFrame]:
    """Charge les tables sources utiles depuis SQLite."""
    connection = sqlite3.connect(str(sqlite_path))
    try:
        dataframes = {
            "t_projet": pd.read_sql_query("SELECT * FROM t_projet", connection),
            "t_batiment": pd.read_sql_query("SELECT * FROM t_batiment", connection),
            "dim_niveau": pd.read_sql_query("SELECT * FROM dim_niveau", connection),
            "t_lot": pd.read_sql_query("SELECT * FROM t_lot", connection),
            "pdf_articles": pd.read_sql_query("SELECT * FROM source_dqe_pdf_articles", connection),
        }
    finally:
        connection.close()
    return dataframes


def prepare_pdf_articles(pdf_articles: pd.DataFrame) -> pd.DataFrame:
    """Enrichit les lignes PDF avec les dimensions deduites."""
    dataframe = pdf_articles.copy()
    dataframe["numero_lot"] = dataframe["lot_code"].str.extract(r"(\d+)").astype("Int64")
    dataframe["inferred_batiment_code"] = dataframe.apply(
        lambda row: infer_building_code(row.get("section_label"), row.get("designation")),
        axis=1,
    )
    dataframe["inferred_niveau_code"] = dataframe.apply(
        lambda row: infer_level_code(row.get("section_label"), row.get("designation")),
        axis=1,
    )
    dataframe["inferred_sous_lot_label"] = dataframe["section_label"].apply(infer_sous_lot_label)
    dataframe["sous_lot_code"] = dataframe.apply(
        lambda row: f"SL_{int(row['numero_lot']):02d}_{slugify(row['inferred_sous_lot_label'])}",
        axis=1,
    )
    dataframe["prestation_code"] = dataframe["id"].apply(lambda value: f"PDF-{value}")
    return dataframe


def fetch_scalar(connection: Connection, query: str, params: dict[str, Any]) -> Any:
    """Retourne une valeur scalaire pratique pour les helpers d'upsert."""
    return connection.execute(text(query), params).scalar_one()


def ensure_chantier(connection: Connection, project_code: str, project_name: str) -> int:
    connection.execute(
        text(
            """
            INSERT INTO chantier (nom, code, description)
            VALUES (:nom, :code, :description)
            ON DUPLICATE KEY UPDATE
                description = VALUES(description)
            """
        ),
        {
            "nom": project_name,
            "code": project_code,
            "description": "Chantier SP2I_BUILD alimente depuis le DQE PDF",
        },
    )
    return int(
        fetch_scalar(connection, "SELECT id FROM chantier WHERE code = :code", {"code": project_code})
    )


def ensure_projet(
    connection: Connection,
    chantier_id: int,
    source_project_row: pd.Series,
    project_code: str,
    project_name: str,
    dqe_version: str,
) -> int:
    connection.execute(
        text(
            """
            INSERT INTO projet (
                chantier_id, nom, code_chantier, version, date_creation, statut, devise
            )
            VALUES (
                :chantier_id, :nom, :code_chantier, :version, :date_creation, :statut, :devise
            )
            ON DUPLICATE KEY UPDATE
                nom = VALUES(nom),
                statut = VALUES(statut),
                devise = VALUES(devise)
            """
        ),
        {
            "chantier_id": chantier_id,
            "nom": source_project_row.get("nom_projet") or project_name,
            "code_chantier": project_code,
            "version": dqe_version,
            "date_creation": source_project_row.get("date_creation"),
            "statut": source_project_row.get("statut") or "ETUDE",
            "devise": source_project_row.get("devise") or "FCFA",
        },
    )
    return int(
        fetch_scalar(
            connection,
            """
            SELECT id
            FROM projet
            WHERE code_chantier = :code_chantier
              AND version = :version
            """,
            {"code_chantier": project_code, "version": dqe_version},
        )
    )


def ensure_dqe_version(connection: Connection, projet_id: int, dqe_version: str, source_file: str) -> int:
    connection.execute(
        text(
            """
            INSERT INTO dqe_version (
                projet_id, version_code, source_fichier, date_import, est_version_active, commentaire
            )
            VALUES (
                :projet_id, :version_code, :source_fichier, NOW(), 1, :commentaire
            )
            ON DUPLICATE KEY UPDATE
                source_fichier = VALUES(source_fichier),
                est_version_active = 1
            """
        ),
        {
            "projet_id": projet_id,
            "version_code": dqe_version,
            "source_fichier": source_file,
            "commentaire": "Version reconstruite depuis source_dqe_pdf_articles",
        },
    )
    connection.execute(
        text(
            """
            UPDATE dqe_version
            SET est_version_active = CASE WHEN version_code = :version_code THEN 1 ELSE 0 END
            WHERE projet_id = :projet_id
            """
        ),
        {"projet_id": projet_id, "version_code": dqe_version},
    )
    return int(
        fetch_scalar(
            connection,
            """
            SELECT id
            FROM dqe_version
            WHERE projet_id = :projet_id
              AND version_code = :version_code
            """,
            {"projet_id": projet_id, "version_code": dqe_version},
        )
    )


def ensure_default_user(connection: Connection) -> int:
    connection.execute(
        text(
            """
            INSERT INTO utilisateur (nom, role)
            VALUES (:nom, :role)
            ON DUPLICATE KEY UPDATE role = VALUES(role)
            """
        ),
        {"nom": "Systeme SP2I_BUILD", "role": "ADMIN"},
    )
    return int(
        fetch_scalar(connection, "SELECT id FROM utilisateur WHERE nom = :nom", {"nom": "Systeme SP2I_BUILD"})
    )


def sync_batiments(connection: Connection, projet_id: int, batiments_df: pd.DataFrame) -> None:
    for row in batiments_df.itertuples(index=False):
        connection.execute(
            text(
                """
                INSERT INTO batiment (projet_id, code_batiment, nom_batiment, ordre_affichage)
                VALUES (:projet_id, :code_batiment, :nom_batiment, :ordre_affichage)
                ON DUPLICATE KEY UPDATE
                    nom_batiment = VALUES(nom_batiment),
                    ordre_affichage = VALUES(ordre_affichage)
                """
            ),
            {
                "projet_id": projet_id,
                "code_batiment": row.batiment_id,
                "nom_batiment": row.nom_batiment,
                "ordre_affichage": row.ordre_affichage or 0,
            },
        )

    connection.execute(
        text(
            """
            INSERT INTO batiment (projet_id, code_batiment, nom_batiment, ordre_affichage)
            VALUES (:projet_id, 'BAT_GLOBAL', 'Batiment Global', 999)
            ON DUPLICATE KEY UPDATE nom_batiment = VALUES(nom_batiment)
            """
        ),
        {"projet_id": projet_id},
    )


def sync_niveaux(connection: Connection, projet_id: int, niveaux_df: pd.DataFrame) -> None:
    for row in niveaux_df.itertuples(index=False):
        batiment_id = fetch_scalar(
            connection,
            "SELECT id FROM batiment WHERE projet_id = :projet_id AND code_batiment = :code_batiment",
            {"projet_id": projet_id, "code_batiment": row.batiment_id},
        )
        if batiment_id is None:
            continue

        connection.execute(
            text(
                """
                INSERT INTO niveau (
                    projet_id, batiment_id, code_niveau, nom_niveau, ordre_niveau, surface_m2
                )
                VALUES (
                    :projet_id, :batiment_id, :code_niveau, :nom_niveau, :ordre_niveau, :surface_m2
                )
                ON DUPLICATE KEY UPDATE
                    nom_niveau = VALUES(nom_niveau),
                    ordre_niveau = VALUES(ordre_niveau)
                """
            ),
            {
                "projet_id": projet_id,
                "batiment_id": int(batiment_id),
                "code_niveau": row.niveau_id,
                "nom_niveau": row.niveau_id,
                "ordre_niveau": row.ordre_niveau or 0,
                "surface_m2": None,
            },
        )

    global_building_id = fetch_scalar(
        connection,
        "SELECT id FROM batiment WHERE projet_id = :projet_id AND code_batiment = 'BAT_GLOBAL'",
        {"projet_id": projet_id},
    )
    connection.execute(
        text(
            """
            INSERT INTO niveau (
                projet_id, batiment_id, code_niveau, nom_niveau, ordre_niveau, surface_m2
            )
            VALUES (:projet_id, :batiment_id, 'GLOBAL', 'GLOBAL', 999, NULL)
            ON DUPLICATE KEY UPDATE nom_niveau = VALUES(nom_niveau)
            """
        ),
        {"projet_id": projet_id, "batiment_id": int(global_building_id)},
    )


def sync_lots(connection: Connection, projet_id: int, lots_df: pd.DataFrame) -> None:
    for row in lots_df.itertuples(index=False):
        connection.execute(
            text(
                """
                INSERT INTO lot (
                    projet_id, numero_lot, code_lot, nom_lot, description_lot, type_lot, ordre_lot
                )
                VALUES (
                    :projet_id, :numero_lot, :code_lot, :nom_lot, :description_lot, :type_lot, :ordre_lot
                )
                ON DUPLICATE KEY UPDATE
                    nom_lot = VALUES(nom_lot),
                    description_lot = VALUES(description_lot),
                    type_lot = VALUES(type_lot),
                    ordre_lot = VALUES(ordre_lot)
                """
            ),
            {
                "projet_id": projet_id,
                "numero_lot": int(row.lot_id),
                "code_lot": row.code_lot,
                "nom_lot": row.nom_lot,
                "description_lot": row.description_lot,
                "type_lot": row.type_lot,
                "ordre_lot": row.ordre_lot or row.lot_id,
            },
        )


def build_id_maps(connection: Connection, projet_id: int) -> dict[str, dict[Any, int]]:
    batiment_map = {
        row[1]: int(row[0])
        for row in connection.execute(
            text("SELECT id, code_batiment FROM batiment WHERE projet_id = :projet_id"),
            {"projet_id": projet_id},
        ).fetchall()
    }
    niveau_map = {
        (row[1], row[2]): int(row[0])
        for row in connection.execute(
            text(
                """
                SELECT n.id, b.code_batiment, n.code_niveau
                FROM niveau n
                JOIN batiment b ON b.id = n.batiment_id
                WHERE n.projet_id = :projet_id
                """
            ),
            {"projet_id": projet_id},
        ).fetchall()
    }
    lot_map = {
        int(row[1]): int(row[0])
        for row in connection.execute(
            text("SELECT id, numero_lot FROM lot WHERE projet_id = :projet_id"),
            {"projet_id": projet_id},
        ).fetchall()
    }
    return {"batiment": batiment_map, "niveau": niveau_map, "lot": lot_map}


def sync_sous_lots(connection: Connection, projet_id: int, pdf_df: pd.DataFrame, lot_map: dict[int, int]) -> dict[tuple[int, str], int]:
    distinct_rows = (
        pdf_df[["numero_lot", "sous_lot_code", "inferred_sous_lot_label"]]
        .drop_duplicates()
        .sort_values(["numero_lot", "sous_lot_code"])
    )
    for row in distinct_rows.itertuples(index=False):
        if pd.isna(row.numero_lot):
            continue
        lot_id = lot_map.get(int(row.numero_lot))
        if not lot_id:
            continue
        connection.execute(
            text(
                """
                INSERT INTO sous_lot (
                    lot_id, code_sous_lot, nom_sous_lot, description_sous_lot, ordre_affichage
                )
                VALUES (
                    :lot_id, :code_sous_lot, :nom_sous_lot, :description_sous_lot, 0
                )
                ON DUPLICATE KEY UPDATE
                    nom_sous_lot = VALUES(nom_sous_lot),
                    description_sous_lot = VALUES(description_sous_lot)
                """
            ),
            {
                "lot_id": lot_id,
                "code_sous_lot": row.sous_lot_code,
                "nom_sous_lot": row.inferred_sous_lot_label,
                "description_sous_lot": f"Sous-lot issu du PDF pour le lot {int(row.numero_lot)}",
            },
        )

    sous_lot_rows = connection.execute(
        text(
            """
            SELECT sl.id, l.numero_lot, sl.code_sous_lot
            FROM sous_lot sl
            JOIN lot l ON l.id = sl.lot_id
            WHERE l.projet_id = :projet_id
            """
        ),
        {"projet_id": projet_id},
    ).fetchall()
    return {(int(numero_lot), code_sous_lot): int(identifier) for identifier, numero_lot, code_sous_lot in sous_lot_rows}


def ensure_budget_suivi(connection: Connection, projet_id: int, total_budget: float) -> None:
    connection.execute(
        text(
            """
            INSERT INTO budget_suivi (id_projet, budget_initial, budget_engage, budget_restant)
            VALUES (:id_projet, :budget_initial, 0, :budget_restant)
            ON DUPLICATE KEY UPDATE
                budget_initial = VALUES(budget_initial)
            """
        ),
        {
            "id_projet": projet_id,
            "budget_initial": round(total_budget, 2),
            "budget_restant": round(total_budget, 2),
        },
    )


def sync_prestations(
    connection: Connection,
    projet_id: int,
    version_id: int,
    responsable_id: int,
    pdf_df: pd.DataFrame,
    id_maps: dict[str, dict[Any, int]],
    sous_lot_map: dict[tuple[int, str], int],
) -> None:
    for row in pdf_df.itertuples(index=False):
        if pd.isna(row.numero_lot):
            continue
        lot_id = id_maps["lot"].get(int(row.numero_lot))
        if not lot_id:
            continue

        sous_lot_id = sous_lot_map.get((int(row.numero_lot), row.sous_lot_code))
        connection.execute(
            text(
                """
                INSERT INTO prestation (
                    projet_id, version_id, lot_id, sous_lot_id, code_bpu, designation,
                    unite, quantite, prix_unitaire, montant_total_ht, date_validation,
                    statut, phase, responsable_id
                )
                VALUES (
                    :projet_id, :version_id, :lot_id, :sous_lot_id, :code_bpu, :designation,
                    :unite, :quantite, :prix_unitaire, :montant_total_ht, NOW(),
                    'ACCEPTE', 'ETUDE', :responsable_id
                )
                ON DUPLICATE KEY UPDATE
                    designation = VALUES(designation),
                    unite = VALUES(unite),
                    quantite = VALUES(quantite),
                    prix_unitaire = VALUES(prix_unitaire),
                    montant_total_ht = VALUES(montant_total_ht),
                    sous_lot_id = VALUES(sous_lot_id)
                """
            ),
            {
                "projet_id": projet_id,
                "version_id": version_id,
                "lot_id": lot_id,
                "sous_lot_id": sous_lot_id,
                "code_bpu": row.prestation_code,
                "designation": row.designation,
                "unite": row.unite,
                "quantite": float(row.quantite),
                "prix_unitaire": float(row.pu_ht),
                "montant_total_ht": float(row.total_ht),
                "responsable_id": responsable_id,
            },
        )

        prestation_id = fetch_scalar(
            connection,
            """
            SELECT id
            FROM prestation
            WHERE projet_id = :projet_id
              AND version_id = :version_id
              AND code_bpu = :code_bpu
            """,
            {"projet_id": projet_id, "version_id": version_id, "code_bpu": row.prestation_code},
        )

        building_code = row.inferred_batiment_code
        level_code = row.inferred_niveau_code
        building_id = id_maps["batiment"].get(building_code) or id_maps["batiment"].get("BAT_GLOBAL")
        level_id = id_maps["niveau"].get((building_code, level_code))
        if not level_id and building_id == id_maps["batiment"].get("BAT_GLOBAL"):
            level_id = id_maps["niveau"].get(("BAT_GLOBAL", "GLOBAL"))
        if not level_id:
            level_id = id_maps["niveau"].get((building_code, "GLOBAL")) or id_maps["niveau"].get(("BAT_GLOBAL", "GLOBAL"))

        connection.execute(
            text(
                """
                INSERT INTO prestation_niveau (
                    prestation_id, niveau_id, batiment_id, quantite, montant
                )
                VALUES (
                    :prestation_id, :niveau_id, :batiment_id, :quantite, :montant
                )
                ON DUPLICATE KEY UPDATE
                    quantite = VALUES(quantite),
                    montant = VALUES(montant)
                """
            ),
            {
                "prestation_id": int(prestation_id),
                "niveau_id": int(level_id),
                "batiment_id": int(building_id),
                "quantite": float(row.quantite),
                "montant": float(row.total_ht),
            },
        )


def call_budget_refresh(connection: Connection) -> None:
    connection.execute(text("CALL mettre_a_jour_budget_restant()"))


def print_dry_run_summary(pdf_df: pd.DataFrame, source_data: dict[str, pd.DataFrame]) -> None:
    print("=== DRY RUN ETL SP2I_BUILD ===")
    print(f"Projet source        : {DEFAULT_PROJECT_SOURCE_ID}")
    print(f"Lignes PDF           : {len(pdf_df)}")
    print(f"Total PDF            : {pdf_df['total_ht'].sum():,.2f} FCFA")
    print(f"Lots source          : {source_data['t_lot']['lot_id'].nunique()}")
    print(f"Batiments deduits    : {pdf_df['inferred_batiment_code'].nunique()}")
    print(f"Niveaux deduits      : {pdf_df['inferred_niveau_code'].nunique()}")
    print(f"Sous-lots deduits    : {pdf_df['sous_lot_code'].nunique()}")
    print("\nRepartition batiment:")
    print(pdf_df["inferred_batiment_code"].value_counts().to_string())
    print("\nRepartition niveau:")
    print(pdf_df["inferred_niveau_code"].value_counts().to_string())


def run_migration(args: argparse.Namespace) -> None:
    source_data = load_source_data(Path(args.source_sqlite))
    pdf_df = prepare_pdf_articles(source_data["pdf_articles"])

    if args.dry_run:
        print_dry_run_summary(pdf_df, source_data)
        return

    if not args.target_url:
        raise RuntimeError("Le parametre --target-url est obligatoire hors mode --dry-run.")

    engine = require_mysql_engine(args.target_url)
    with engine.begin() as connection:
        project_rows = source_data["t_projet"]
        project_row = project_rows.loc[
            project_rows["projet_id"] == args.source_project_id
        ].iloc[0]

        chantier_id = ensure_chantier(connection, args.project_code, args.project_name)
        projet_id = ensure_projet(
            connection,
            chantier_id,
            project_row,
            args.project_code,
            args.project_name,
            args.dqe_version,
        )
        version_id = ensure_dqe_version(
            connection,
            projet_id,
            args.dqe_version,
            str(pdf_df["source_file"].dropna().iloc[0]) if not pdf_df.empty else "",
        )
        responsable_id = ensure_default_user(connection)
        context = MigrationContext(
            chantier_id=chantier_id,
            projet_id=projet_id,
            version_id=version_id,
            responsable_id=responsable_id,
        )

        batiments_df = source_data["t_batiment"].loc[
            source_data["t_batiment"]["projet_id"] == args.source_project_id
        ]
        niveaux_df = source_data["dim_niveau"].loc[
            source_data["dim_niveau"]["projet_id"] == args.source_project_id
        ]

        sync_batiments(connection, context.projet_id, batiments_df)
        sync_niveaux(connection, context.projet_id, niveaux_df)
        sync_lots(connection, context.projet_id, source_data["t_lot"])
        id_maps = build_id_maps(connection, context.projet_id)
        sous_lot_map = sync_sous_lots(connection, context.projet_id, pdf_df, id_maps["lot"])
        ensure_budget_suivi(connection, context.projet_id, float(pdf_df["total_ht"].sum()))
        sync_prestations(
            connection,
            context.projet_id,
            context.version_id,
            context.responsable_id,
            pdf_df,
            id_maps,
            sous_lot_map,
        )
        call_budget_refresh(connection)

    print("Migration terminee avec succes.")
    print(f"Projet migre  : {args.project_code} / {args.dqe_version}")
    print(f"Lignes chargees : {len(pdf_df)}")
    print(f"Total DQE       : {pdf_df['total_ht'].sum():,.2f} FCFA")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migre le DQE SP2I_BUILD depuis SQLite vers le modele MySQL cible."
    )
    parser.add_argument(
        "--source-sqlite",
        default=str(DEFAULT_SQLITE_PATH),
        help="Chemin vers la base SQLite source.",
    )
    parser.add_argument(
        "--target-url",
        default="",
        help="URL SQLAlchemy MySQL cible, ex. mysql+pymysql://user:pwd@localhost:3306/sp2i_build",
    )
    parser.add_argument(
        "--source-project-id",
        default=DEFAULT_PROJECT_SOURCE_ID,
        help="Identifiant projet source dans SQLite.",
    )
    parser.add_argument(
        "--project-code",
        default=DEFAULT_PROJECT_CODE,
        help="Code chantier/projet a creer dans MySQL.",
    )
    parser.add_argument(
        "--project-name",
        default=DEFAULT_PROJECT_NAME,
        help="Nom du chantier/projet cible.",
    )
    parser.add_argument(
        "--dqe-version",
        default=DEFAULT_DQE_VERSION,
        help="Code de version DQE a creer dans MySQL.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche les volumes et les deductions sans ecrire dans MySQL.",
    )
    return parser


if __name__ == "__main__":
    arguments = build_parser().parse_args()
    run_migration(arguments)
