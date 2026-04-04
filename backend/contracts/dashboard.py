"""
Schemas de restitution dashboard SaaS.
"""

from __future__ import annotations

from pydantic import BaseModel


class DashboardFiltersRequest(BaseModel):
    """
    Filtres globaux proches d'un SaaS analytique.
    """

    lot_ids: list[str] = []
    families: list[str] = []
    niveaux: list[str] = []
    batiments: list[str] = []


class PremiumDashboardResponse(BaseModel):
    """
    Reponse agregée du dashboard premium.
    """

    kpis: dict
    charts: dict
    filters: dict

