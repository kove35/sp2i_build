"""
Schemas simples pour centraliser les filtres.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, validator


class DashboardFilters(BaseModel):
    """
    Filtres disponibles pour les dashboards.
    """

    lot_id: int | None = None
    fam_article_id: str | None = None
    batiment_id: str | None = None
    niveau_id: str | None = None


class DQEArticlePayload(BaseModel):
    """
    Donnees envoyees par le formulaire de saisie DQE.
    """

    lot: str = Field(..., min_length=1)
    sous_lot: str = Field(..., min_length=1)
    designation: str = Field(..., min_length=1)
    unite: str = Field(..., min_length=1)
    quantite: float = Field(..., gt=0)
    pu_local: float = Field(..., ge=0)
    pu_chine: float = Field(..., ge=0)

    @validator("lot", "sous_lot", "designation", "unite")
    def strip_text_values(cls, value: str) -> str:
        """
        Nettoie les champs texte et evite les valeurs vides.
        """
        clean_value = value.strip()
        if not clean_value:
            raise ValueError("Ce champ ne peut pas etre vide.")
        return clean_value


class BuildAnalyticsProjectResponse(BaseModel):
    """
    Projet du nouveau schema analytique SQLAlchemy.
    """

    id: int
    code: str
    name: str
    description: str | None = None
    devise: str
    statut: str

    class Config:
        from_attributes = True


class BuildAnalyticsFiltersResponse(BaseModel):
    """
    Valeurs disponibles pour filtrer le dashboard analytique.
    """

    lots: list[str]
    familles: list[str]
    niveaux: list[str]
    batiments: list[str]


class BuildFactPayload(BaseModel):
    """
    Payload simple pour creer ou modifier une ligne de faits analytique.

    On travaille avec les codes metier pour rester compréhensible :
    - code_bpu
    - lot_code
    - famille_code
    - niveau_code
    - batiment_code
    """

    code_bpu: str = Field(..., min_length=1)
    lot_code: str | None = None
    famille_code: str | None = None
    niveau_code: str | None = None
    batiment_code: str | None = None
    quantite: float = Field(..., gt=0)
    pu_local: float = Field(..., ge=0)
    pu_chine: float | None = Field(default=None, ge=0)
    total_local: float | None = Field(default=None, ge=0)
    total_import: float | None = Field(default=None, ge=0)
    economie: float | None = None
    taux_economie: float | None = None
    decision: str = Field(default="LOCAL", min_length=1)
    source_row_key: str | None = None

    @validator(
        "code_bpu",
        "lot_code",
        "famille_code",
        "niveau_code",
        "batiment_code",
        "decision",
        "source_row_key",
        pre=True,
        always=False,
    )
    def strip_optional_text_values(cls, value: str | None) -> str | None:
        """
        Nettoie les champs texte et convertit les chaines vides en None.
        """
        if value is None:
            return None
        clean_value = value.strip()
        return clean_value or None


class BuildFactResponse(BaseModel):
    """
    Reponse detaillee pour une ligne de faits analytique.
    """

    id: int
    project_id: int
    article_id: int
    code_bpu: str
    designation: str
    lot: str
    famille: str | None = None
    niveau: str | None = None
    batiment: str | None = None
    quantite: float
    pu_local: float
    pu_chine: float | None = None
    total_local: float
    total_import: float | None = None
    economie: float
    taux_economie: float
    decision: str
    source_row_key: str | None = None


class BuildAnalyticsDashboardResponse(BaseModel):
    """
    Reponse agrégée pour le dashboard SQLAlchemy.
    """

    project: BuildAnalyticsProjectResponse
    kpis: dict
    charts: dict
    filters: BuildAnalyticsFiltersResponse


class DQEPdfImportPayload(BaseModel):
    """
    Payload pour importer un DQE PDF comme source.
    """

    pdf_path: str | None = None


class DQEPdfPromotePayload(BaseModel):
    """
    Payload pour promouvoir une source PDF vers un projet analytique.
    """

    source_file: str | None = None
    project_code: str | None = None
    project_name: str | None = None
    replace_existing: bool = False


class BuildAnalyticsProjectCreatePayload(BaseModel):
    """
    Payload simple pour creer un projet analytique manuellement.
    """

    code: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str | None = None
    devise: str = "FCFA"
    statut: str = "draft"


class DQEHierarchyItemPayload(BaseModel):
    """
    Payload standardise pour saisir une ligne DQE hierarchique.
    """

    batiment: str = Field(..., min_length=1)
    niveau: str = Field(..., min_length=1)
    lot: str = Field(..., min_length=1)
    sous_lot: str = Field(..., min_length=1)
    designation: str = Field(..., min_length=1)
    unite: str = Field(..., min_length=1)
    quantite: float = Field(..., gt=0)
    pu_local: float = Field(..., ge=0)
    pu_chine: float | None = Field(default=None, ge=0)
    code_bpu: str | None = None
    famille: str | None = None
    source_row_key: str | None = None

    @validator(
        "batiment",
        "niveau",
        "lot",
        "sous_lot",
        "designation",
        "unite",
        "code_bpu",
        "famille",
        "source_row_key",
        pre=True,
        always=False,
    )
    def strip_hierarchy_text_values(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean_value = value.strip()
        return clean_value or None


class DQEImportPreviewPayload(BaseModel):
    """
    Demande d'analyse d'un fichier DQE.
    """

    file_path: str = Field(..., min_length=1)
    sheet_name: str | None = None
    custom_mapping: dict[str, str | None] | None = None


class DQEImportApplyPayload(BaseModel):
    """
    Demande d'import d'un fichier DQE standardise vers le schema analytique.
    """

    file_path: str = Field(..., min_length=1)
    project_id: int
    sheet_name: str | None = None
    replace_existing: bool = False
    custom_mapping: dict[str, str | None] | None = None
