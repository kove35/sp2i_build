"""
Schemas metier pour les projets et les lignes CAPEX SaaS.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    """
    Creation d'un projet.
    """

    name: str = Field(min_length=2, max_length=255)
    code: str = Field(min_length=2, max_length=100)
    description: str | None = None


class ProjectResponse(BaseModel):
    """
    Representation d'un projet.
    """

    id: int
    name: str
    code: str
    description: str | None = None
    owner_id: int

    class Config:
        from_attributes = True


class CapexItemCreateRequest(BaseModel):
    """
    Ligne CAPEX d'un projet.
    """

    lot_id: str = Field(min_length=1, max_length=120)
    family_article: str = Field(min_length=1, max_length=255)
    code_bpu: str = Field(min_length=1, max_length=255)
    batiment: str = Field(min_length=1, max_length=120)
    niveau: str = Field(min_length=1, max_length=120)
    decision: str = Field(min_length=1, max_length=30)
    quantity: float = Field(ge=0)
    montant_local: float = Field(ge=0)
    montant_import: float = Field(ge=0)
    risk_score: float = Field(ge=0, le=5, default=0)
    import_score: float = Field(ge=0, le=1, default=0)
    source_index: int = Field(ge=0, default=0)


class CapexItemResponse(BaseModel):
    """
    Representation publique d'une ligne CAPEX.
    """

    id: int
    project_id: int
    lot_id: str
    family_article: str
    code_bpu: str
    batiment: str
    niveau: str
    decision: str
    quantity: float
    montant_local: float
    montant_import: float
    risk_score: float
    import_score: float
    source_index: int

    class Config:
        from_attributes = True

