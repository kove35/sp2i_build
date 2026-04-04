"""Migration locale vers une base SQLite cible de type ERP/DQE.

But :
- offrir une cible exploitable tout de suite quand MySQL n'est pas disponible ;
- conserver le modele metier demande :
  chantier -> projet -> batiment -> niveau -> lot -> sous_lot -> prestation -> prestation_niveau

Ce script reutilise la logique d'inference du script MySQL pour reconstruire
les dimensions depuis ``sp2i_build.db`` et le PDF deja importe.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from migrate_sqlite_to_mysql_dqe import (
    DEFAULT_DQE_VERSION,
    DEFAULT_PROJECT_CODE,
    DEFAULT_PROJECT_NAME,
    DEFAULT_PROJECT_SOURCE_ID,
    DEFAULT_SQLITE_PATH,
    infer_building_code,
    infer_level_code,
    infer_sous_lot_label,
    load_source_data,
    normalize_text,
    slugify,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TARGET_SQLITE = ROOT_DIR / "sp2i_erp.db"


def prepare_pdf_articles(pdf_articles):
    dataframe = pdf_articles.copy()
    dataframe["quantite"] = dataframe["quantite"].astype(float)
    dataframe["pu_ht"] = dataframe["pu_ht"].astype(float)
    dataframe["total_ht"] = dataframe["total_ht"].astype(float)
    dataframe["total_ht"] = dataframe["total_ht"].fillna(dataframe["quantite"] * dataframe["pu_ht"])
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
    dataframe = dataframe.dropna(subset=["numero_lot", "designation", "unite", "quantite", "pu_ht", "total_ht"])
    dataframe = dataframe[(dataframe["quantite"] > 0) & (dataframe["pu_ht"] > 0) & (dataframe["total_ht"] > 0)]
    return dataframe


def create_target_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS chantier (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS projet (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chantier_id INTEGER,
            nom TEXT NOT NULL,
            code_chantier TEXT,
            version TEXT,
            date_creation TEXT,
            statut TEXT,
            devise TEXT DEFAULT 'FCFA',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(code_chantier, version),
            FOREIGN KEY (chantier_id) REFERENCES chantier(id)
        );

        CREATE TABLE IF NOT EXISTS utilisateur (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS dqe_version (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projet_id INTEGER NOT NULL,
            version_code TEXT NOT NULL,
            source_fichier TEXT,
            date_import TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            est_version_active INTEGER NOT NULL DEFAULT 0,
            commentaire TEXT,
            UNIQUE(projet_id, version_code),
            FOREIGN KEY (projet_id) REFERENCES projet(id)
        );

        CREATE TABLE IF NOT EXISTS batiment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projet_id INTEGER NOT NULL,
            code_batiment TEXT NOT NULL,
            nom_batiment TEXT NOT NULL,
            ordre_affichage INTEGER NOT NULL DEFAULT 0,
            UNIQUE(projet_id, code_batiment),
            FOREIGN KEY (projet_id) REFERENCES projet(id)
        );

        CREATE TABLE IF NOT EXISTS niveau (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projet_id INTEGER NOT NULL,
            batiment_id INTEGER NOT NULL,
            code_niveau TEXT NOT NULL,
            nom_niveau TEXT NOT NULL,
            ordre_niveau INTEGER NOT NULL DEFAULT 0,
            surface_m2 REAL,
            UNIQUE(batiment_id, code_niveau),
            FOREIGN KEY (projet_id) REFERENCES projet(id),
            FOREIGN KEY (batiment_id) REFERENCES batiment(id)
        );

        CREATE TABLE IF NOT EXISTS lot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projet_id INTEGER NOT NULL,
            numero_lot INTEGER NOT NULL,
            code_lot TEXT NOT NULL,
            nom_lot TEXT NOT NULL,
            description_lot TEXT,
            type_lot TEXT,
            ordre_lot INTEGER NOT NULL DEFAULT 0,
            UNIQUE(projet_id, numero_lot),
            UNIQUE(projet_id, code_lot),
            FOREIGN KEY (projet_id) REFERENCES projet(id)
        );

        CREATE TABLE IF NOT EXISTS sous_lot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_id INTEGER NOT NULL,
            code_sous_lot TEXT NOT NULL,
            nom_sous_lot TEXT NOT NULL,
            description_sous_lot TEXT,
            ordre_affichage INTEGER NOT NULL DEFAULT 0,
            UNIQUE(lot_id, code_sous_lot),
            FOREIGN KEY (lot_id) REFERENCES lot(id)
        );

        CREATE TABLE IF NOT EXISTS prestation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projet_id INTEGER NOT NULL,
            version_id INTEGER,
            lot_id INTEGER NOT NULL,
            sous_lot_id INTEGER,
            code_bpu TEXT,
            designation TEXT NOT NULL,
            unite TEXT NOT NULL,
            quantite REAL NOT NULL CHECK (quantite > 0),
            prix_unitaire REAL NOT NULL CHECK (prix_unitaire > 0),
            montant_total_ht REAL NOT NULL CHECK (montant_total_ht > 0),
            date_validation TEXT,
            statut TEXT NOT NULL DEFAULT 'REVISION',
            phase TEXT NOT NULL DEFAULT 'ETUDE',
            responsable_id INTEGER,
            UNIQUE(projet_id, version_id, code_bpu),
            FOREIGN KEY (projet_id) REFERENCES projet(id),
            FOREIGN KEY (version_id) REFERENCES dqe_version(id),
            FOREIGN KEY (lot_id) REFERENCES lot(id),
            FOREIGN KEY (sous_lot_id) REFERENCES sous_lot(id),
            FOREIGN KEY (responsable_id) REFERENCES utilisateur(id)
        );

        CREATE TABLE IF NOT EXISTS prestation_niveau (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prestation_id INTEGER NOT NULL,
            niveau_id INTEGER NOT NULL,
            batiment_id INTEGER NOT NULL,
            quantite REAL NOT NULL CHECK (quantite > 0),
            montant REAL NOT NULL CHECK (montant > 0),
            UNIQUE(prestation_id, niveau_id, batiment_id),
            FOREIGN KEY (prestation_id) REFERENCES prestation(id),
            FOREIGN KEY (niveau_id) REFERENCES niveau(id),
            FOREIGN KEY (batiment_id) REFERENCES batiment(id)
        );

        CREATE TABLE IF NOT EXISTS budget_suivi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_projet INTEGER NOT NULL UNIQUE,
            budget_initial REAL NOT NULL DEFAULT 0,
            budget_engage REAL NOT NULL DEFAULT 0,
            budget_restant REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (id_projet) REFERENCES projet(id)
        );

        CREATE TABLE IF NOT EXISTS audit_modification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom_table TEXT NOT NULL,
            id_ligne INTEGER NOT NULL,
            type_operation TEXT NOT NULL,
            detail_modification TEXT,
            utilisateur_id INTEGER,
            date_modification TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (utilisateur_id) REFERENCES utilisateur(id)
        );

        CREATE VIEW IF NOT EXISTS vue_budget_par_batiment_niveau_lot AS
        SELECT
            p.projet_id,
            b.nom_batiment,
            n.nom_niveau,
            l.numero_lot,
            l.nom_lot,
            SUM(pn.montant) AS montant_total_ht
        FROM prestation_niveau pn
        JOIN prestation p ON p.id = pn.prestation_id
        JOIN batiment b ON b.id = pn.batiment_id
        JOIN niveau n ON n.id = pn.niveau_id
        JOIN lot l ON l.id = p.lot_id
        GROUP BY p.projet_id, b.nom_batiment, n.nom_niveau, l.numero_lot, l.nom_lot;
        """
    )


def fetch_id(connection: sqlite3.Connection, query: str, params: tuple) -> int:
    row = connection.execute(query, params).fetchone()
    return int(row[0]) if row else 0


def run_migration(source_sqlite: Path, target_sqlite: Path) -> None:
    source_data = load_source_data(source_sqlite)
    pdf_df = prepare_pdf_articles(source_data["pdf_articles"])

    if target_sqlite.exists():
        target_sqlite.unlink()

    connection = sqlite3.connect(target_sqlite)
    connection.row_factory = sqlite3.Row
    try:
        create_target_schema(connection)

        project_df = source_data["t_projet"]
        project_row = project_df.loc[
            project_df["projet_id"] == DEFAULT_PROJECT_SOURCE_ID
        ].iloc[0]

        connection.execute(
            """
            INSERT INTO chantier (nom, code, description)
            VALUES (?, ?, ?)
            """,
            (
                DEFAULT_PROJECT_NAME,
                DEFAULT_PROJECT_CODE,
                "Chantier SP2I_BUILD alimente depuis le DQE PDF",
            ),
        )
        chantier_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

        connection.execute(
            """
            INSERT INTO projet (chantier_id, nom, code_chantier, version, date_creation, statut, devise)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chantier_id,
                project_row.get("nom_projet") or DEFAULT_PROJECT_NAME,
                DEFAULT_PROJECT_CODE,
                DEFAULT_DQE_VERSION,
                project_row.get("date_creation"),
                project_row.get("statut") or "ETUDE",
                project_row.get("devise") or "FCFA",
            ),
        )
        projet_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

        connection.execute(
            """
            INSERT INTO dqe_version (projet_id, version_code, source_fichier, est_version_active, commentaire)
            VALUES (?, ?, ?, 1, ?)
            """,
            (
                projet_id,
                DEFAULT_DQE_VERSION,
                str(pdf_df["source_file"].dropna().iloc[0]),
                "Version reconstruite depuis source_dqe_pdf_articles",
            ),
        )
        version_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

        connection.execute(
            "INSERT INTO utilisateur (nom, role) VALUES (?, ?)",
            ("Systeme SP2I_BUILD", "ADMIN"),
        )
        responsable_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

        for row in source_data["t_batiment"].itertuples(index=False):
            if row.projet_id != DEFAULT_PROJECT_SOURCE_ID:
                continue
            connection.execute(
                """
                INSERT OR IGNORE INTO batiment (projet_id, code_batiment, nom_batiment, ordre_affichage)
                VALUES (?, ?, ?, ?)
                """,
                (projet_id, row.batiment_id, row.nom_batiment, row.ordre_affichage or 0),
            )

        connection.execute(
            """
            INSERT OR IGNORE INTO batiment (projet_id, code_batiment, nom_batiment, ordre_affichage)
            VALUES (?, 'BAT_GLOBAL', 'Batiment Global', 999)
            """,
            (projet_id,),
        )

        batiment_map = {
            row["code_batiment"]: row["id"]
            for row in connection.execute("SELECT id, code_batiment FROM batiment WHERE projet_id = ?", (projet_id,))
        }

        for row in source_data["dim_niveau"].itertuples(index=False):
            if row.projet_id != DEFAULT_PROJECT_SOURCE_ID:
                continue
            batiment_id = batiment_map.get(row.batiment_id)
            if not batiment_id:
                continue
            connection.execute(
                """
                INSERT OR IGNORE INTO niveau (projet_id, batiment_id, code_niveau, nom_niveau, ordre_niveau, surface_m2)
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (projet_id, batiment_id, row.niveau_id, row.niveau_id, row.ordre_niveau or 0),
            )

        connection.execute(
            """
            INSERT OR IGNORE INTO niveau (projet_id, batiment_id, code_niveau, nom_niveau, ordre_niveau, surface_m2)
            VALUES (?, ?, 'GLOBAL', 'GLOBAL', 999, NULL)
            """,
            (projet_id, batiment_map["BAT_GLOBAL"]),
        )

        niveau_map = {
            (row["batiment_id"], row["code_niveau"]): row["id"]
            for row in connection.execute("SELECT id, batiment_id, code_niveau FROM niveau WHERE projet_id = ?", (projet_id,))
        }

        for row in source_data["t_lot"].itertuples(index=False):
            connection.execute(
                """
                INSERT OR IGNORE INTO lot (projet_id, numero_lot, code_lot, nom_lot, description_lot, type_lot, ordre_lot)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    projet_id,
                    int(row.lot_id),
                    row.code_lot,
                    row.nom_lot,
                    row.description_lot,
                    row.type_lot,
                    row.ordre_lot or row.lot_id,
                ),
            )

        lot_map = {
            row["numero_lot"]: row["id"]
            for row in connection.execute("SELECT id, numero_lot FROM lot WHERE projet_id = ?", (projet_id,))
        }

        for row in (
            pdf_df[["numero_lot", "sous_lot_code", "inferred_sous_lot_label"]]
            .drop_duplicates()
            .sort_values(["numero_lot", "sous_lot_code"])
            .itertuples(index=False)
        ):
            if row.numero_lot is None:
                continue
            lot_id = lot_map.get(int(row.numero_lot))
            if not lot_id:
                continue
            connection.execute(
                """
                INSERT OR IGNORE INTO sous_lot (lot_id, code_sous_lot, nom_sous_lot, description_sous_lot, ordre_affichage)
                VALUES (?, ?, ?, ?, 0)
                """,
                (
                    lot_id,
                    row.sous_lot_code,
                    row.inferred_sous_lot_label,
                    f"Sous-lot issu du PDF pour le lot {int(row.numero_lot)}",
                ),
            )

        sous_lot_map = {
            (row["lot_id"], row["code_sous_lot"]): row["id"]
            for row in connection.execute("SELECT id, lot_id, code_sous_lot FROM sous_lot")
        }

        for row in pdf_df.itertuples(index=False):
            if row.numero_lot is None:
                continue
            lot_id = lot_map.get(int(row.numero_lot))
            if not lot_id:
                continue
            sous_lot_id = sous_lot_map.get((lot_id, row.sous_lot_code))
            connection.execute(
                """
                INSERT INTO prestation (
                    projet_id, version_id, lot_id, sous_lot_id, code_bpu, designation, unite,
                    quantite, prix_unitaire, montant_total_ht, date_validation, statut, phase, responsable_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 'ACCEPTE', 'ETUDE', ?)
                """,
                (
                    projet_id,
                    version_id,
                    lot_id,
                    sous_lot_id,
                    row.prestation_code,
                    row.designation,
                    row.unite,
                    float(row.quantite),
                    float(row.pu_ht),
                    float(row.total_ht),
                    responsable_id,
                ),
            )
            prestation_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

            batiment_id = batiment_map.get(row.inferred_batiment_code, batiment_map["BAT_GLOBAL"])
            niveau_id = niveau_map.get((batiment_id, row.inferred_niveau_code))
            if not niveau_id:
                niveau_id = niveau_map.get((batiment_map["BAT_GLOBAL"], "GLOBAL"))

            connection.execute(
                """
                INSERT INTO prestation_niveau (prestation_id, niveau_id, batiment_id, quantite, montant)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    prestation_id,
                    niveau_id,
                    batiment_id,
                    float(row.quantite),
                    float(row.total_ht),
                ),
            )

        total_budget = float(pdf_df["total_ht"].sum())
        connection.execute(
            """
            INSERT INTO budget_suivi (id_projet, budget_initial, budget_engage, budget_restant)
            VALUES (?, ?, ?, ?)
            """,
            (projet_id, total_budget, total_budget, 0.0),
        )

        connection.commit()
    finally:
        connection.close()

    print("Migration SQLite locale terminee.")
    print(f"Base cible : {target_sqlite}")
    print(f"Total DQE  : {pdf_df['total_ht'].sum():,.2f} FCFA")
    print(f"Lignes PDF : {len(pdf_df)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migre les donnees DQE vers une base SQLite locale cible."
    )
    parser.add_argument(
        "--source-sqlite",
        default=str(DEFAULT_SQLITE_PATH),
        help="Chemin vers la base SQLite source.",
    )
    parser.add_argument(
        "--target-sqlite",
        default=str(DEFAULT_TARGET_SQLITE),
        help="Chemin vers la base SQLite cible.",
    )
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    run_migration(Path(args.source_sqlite), Path(args.target_sqlite))
