"""
Session SQLAlchemy du socle SaaS.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.saas_config import saas_settings
from backend.db.base import Base
from backend.models import __all_models  # noqa: F401
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
from backend.models.capex_item import ProjectCapexItem
from backend.models.project import Project
from backend.models.user import User


engine_kwargs = {}
if saas_settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(saas_settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# Tables du socle SaaS existant : auth, projet SaaS et items CAPEX.
SAAS_CORE_TABLES = [
    User.__table__,
    Project.__table__,
    ProjectCapexItem.__table__,
]

# Tables analytiques ajoutees pour un schema dashboard propre.
BUILD_ANALYTICS_TABLES = [
    BuildProject.__table__,
    BuildLot.__table__,
    BuildSousLot.__table__,
    BuildFamilyDimension.__table__,
    BuildLevelDimension.__table__,
    BuildBuildingDimension.__table__,
    BuildArticle.__table__,
    BuildFactMetre.__table__,
]


def get_db_session():
    """
    Dependency FastAPI pour injecter une session SQLAlchemy.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def initialize_saas_core_database() -> None:
    """
    Cree uniquement les tables SQLAlchemy du socle SaaS.

    Cette fonction couvre :
    - les utilisateurs
    - les projets SaaS
    - les lignes CAPEX SaaS
    """
    Base.metadata.create_all(bind=engine, tables=SAAS_CORE_TABLES)


def initialize_build_analytics_database() -> None:
    """
    Cree les tables SQLAlchemy du schema analytique SP2I_Build.

    Ce schema est pense pour les dashboards type Power BI :
    - dimensions
    - catalogue article
    - table de faits
    """
    Base.metadata.create_all(bind=engine, tables=BUILD_ANALYTICS_TABLES)


def initialize_all_sqlalchemy_tables() -> None:
    """
    Cree toutes les tables SQLAlchemy connues de l'application.

    On garde cette fonction comme point d'entree principal
    pour les futurs scripts d'initialisation ou de seed.
    """
    initialize_saas_core_database()
    initialize_build_analytics_database()


def initialize_saas_database() -> None:
    """
    Alias de compatibilite avec l'ancien nom.

    Historiquement, l'application n'avait que le socle SaaS.
    Maintenant, on initialise aussi le schema analytique.
    """
    initialize_all_sqlalchemy_tables()


def get_sqlalchemy_table_names() -> list[str]:
    """
    Retourne la liste des tables SQLAlchemy gerees par l'application.

    Utile pour le debug ou pour afficher clairement ce que create_all()
    va materialiser dans la base.
    """
    return [table.name for table in SAAS_CORE_TABLES + BUILD_ANALYTICS_TABLES]
