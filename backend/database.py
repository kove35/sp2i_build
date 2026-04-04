"""
Fonctions utilitaires pour se connecter a SQLite.
"""

import sqlite3

from backend.config import DATABASE_PATH
from backend.db.session import initialize_all_sqlalchemy_tables


def get_connection() -> sqlite3.Connection:
    """
    Ouvre une connexion SQLite avec acces par nom de colonne.
    """
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    """
    Cree les tables applicatives qui doivent exister pour l'application web.
    """
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS articles_dqe (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lot TEXT NOT NULL,
                sous_lot TEXT NOT NULL,
                designation TEXT NOT NULL,
                unite TEXT NOT NULL,
                quantite REAL NOT NULL,
                pu_local REAL NOT NULL,
                pu_chine REAL NOT NULL,
                total_local REAL NOT NULL,
                total_import REAL NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS source_dqe_pdf_lots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                lot_code TEXT NOT NULL,
                designation TEXT NOT NULL,
                total_ht REAL NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS source_dqe_pdf_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                lot_code TEXT NOT NULL,
                lot_label TEXT,
                section_code TEXT,
                section_label TEXT,
                item_number TEXT,
                designation TEXT NOT NULL,
                designation_normalized TEXT NOT NULL,
                unite TEXT NOT NULL,
                quantite REAL,
                pu_ht REAL,
                total_ht REAL,
                is_pm INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT
            )
            """
        )
        connection.commit()

    # Initialise toutes les tables SQLAlchemy :
    # - socle SaaS
    # - schema analytique pour dashboards
    initialize_all_sqlalchemy_tables()
