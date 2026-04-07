"""
Fonctions utilitaires pour se connecter a SQLite.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from backend.config import (
    APP_DATABASE_PATH,
    EXCEL_SOURCE_PATH,
    SOURCE_DATABASE_PATH,
)
from backend.db.session import SessionLocal, engine, initialize_all_sqlalchemy_tables
from backend.models.build_analytics import BuildArticle, BuildFactMetre, BuildProject
from backend.models.project import Project
from backend.models.user import User


logger = logging.getLogger(__name__)


def _ensure_parent_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _collect_sqlite_stats(path: Path, tracked_tables: list[str]) -> dict:
    stats = {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "parent_exists": path.parent.exists(),
        "parent": str(path.parent),
        "writable_hint": str(path.parent),
        "tables": {},
    }

    if not path.exists():
        return stats

    try:
        with sqlite3.connect(path) as connection:
            connection.row_factory = sqlite3.Row
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            for table_name in tracked_tables:
                if table_name not in tables:
                    stats["tables"][table_name] = {"exists": False, "rows": 0}
                    continue
                row_count = connection.execute(
                    f"SELECT COUNT(*) AS count FROM {table_name}"
                ).fetchone()["count"]
                stats["tables"][table_name] = {"exists": True, "rows": int(row_count)}
    except sqlite3.Error as error:
        stats["error"] = str(error)

    return stats


def get_data_debug_stats() -> dict:
    """
    Retourne un etat synthetique des sources et bases de l'application.
    """
    payload = {
        "excel_source": {
            "path": str(EXCEL_SOURCE_PATH),
            "exists": EXCEL_SOURCE_PATH.exists(),
            "size_bytes": EXCEL_SOURCE_PATH.stat().st_size if EXCEL_SOURCE_PATH.exists() else 0,
        },
        "source_sqlite": _collect_sqlite_stats(
            SOURCE_DATABASE_PATH,
            tracked_tables=[
                "t_projet",
                "staging",
                "raw_bpu_local",
                "dim_fam_article",
            ],
        ),
        "app_sqlite": _collect_sqlite_stats(
            APP_DATABASE_PATH,
            tracked_tables=[
                "articles_dqe",
                "source_dqe_pdf_articles",
                "source_dqe_pdf_lots",
                "app_settings",
            ],
        ),
        "sqlalchemy": {
            "url": engine.url.render_as_string(hide_password=True),
            "dialect": engine.dialect.name,
        },
    }

    session = SessionLocal()
    try:
        payload["sqlalchemy"]["counts"] = {
            "build_projects": session.query(BuildProject).count(),
            "build_articles": session.query(BuildArticle).count(),
            "build_fact_rows": session.query(BuildFactMetre).count(),
            "saas_users": session.query(User).count(),
            "saas_projects": session.query(Project).count(),
        }
    except SQLAlchemyError as error:
        payload["sqlalchemy"]["error"] = str(error)
    finally:
        session.close()

    payload["runtime"] = {
        "app_db_same_as_source_db": APP_DATABASE_PATH == SOURCE_DATABASE_PATH,
        "sqlalchemy_database_url_env": engine.url.render_as_string(hide_password=True),
    }
    return payload


def get_connection() -> sqlite3.Connection:
    """
    Ouvre une connexion SQLite avec acces par nom de colonne.
    """
    _ensure_parent_directory(APP_DATABASE_PATH)
    connection = sqlite3.connect(APP_DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    """
    Cree les tables applicatives qui doivent exister pour l'application web.
    """
    _ensure_parent_directory(APP_DATABASE_PATH)

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
    logger.info(
        "Initialisation DB terminee | source_sqlite=%s | app_sqlite=%s | sqlalchemy=%s",
        SOURCE_DATABASE_PATH,
        APP_DATABASE_PATH,
        engine.url.render_as_string(hide_password=True),
    )
