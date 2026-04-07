"""
Configuration du socle SaaS.

Le point important :
- en production, on vise PostgreSQL
- en local, on peut utiliser SQLite pour demarrer vite
"""

from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


def _normalize_database_url(database_url: str) -> str:
    """
    Normalise l'URL de base pour SQLAlchemy.
    """
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return database_url


class SaaSSettings:
    """
    Parametres centralises de l'application SaaS.
    """

    project_name: str = "SP2I_Build SaaS"
    api_prefix: str = "/saas"
    jwt_secret_key: str = os.getenv("SP2I_JWT_SECRET", "change-me-in-production")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = int(
        os.getenv("SP2I_ACCESS_TOKEN_EXPIRE_MINUTES", "120")
    )

    # PostgreSQL-ready :
    # exemple :
    # postgresql+psycopg://postgres:postgres@localhost:5432/sp2i_build
    database_url: str = _normalize_database_url(
        os.getenv(
            "SP2I_DATABASE_URL",
            f"sqlite:///{(BASE_DIR / 'sp2i_saas.db').as_posix()}",
        )
    )


saas_settings = SaaSSettings()
