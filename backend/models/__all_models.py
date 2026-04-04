"""
Importe tous les modeles pour que Base.metadata voie bien l'ensemble.
"""

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

__all__ = [
    "User",
    "Project",
    "ProjectCapexItem",
    "BuildProject",
    "BuildLot",
    "BuildSousLot",
    "BuildFamilyDimension",
    "BuildLevelDimension",
    "BuildBuildingDimension",
    "BuildArticle",
    "BuildFactMetre",
]
