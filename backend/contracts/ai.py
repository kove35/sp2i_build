"""
Schemas pour les recommandations IA d'import.
"""

from __future__ import annotations

from pydantic import BaseModel


class ImportRecommendation(BaseModel):
    """
    Recommandation lisible pour un article ou une famille.
    """

    scope: str
    label: str
    recommendation: str
    confidence: float
    explanation: str


class ImportRecommendationResponse(BaseModel):
    """
    Liste des recommandations d'import.
    """

    project_id: int
    recommendations: list[ImportRecommendation]
