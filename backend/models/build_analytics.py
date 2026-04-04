"""
Modeles SQLAlchemy analytiques pour SP2I_Build.

Ce fichier propose une structure "propre" pour une application
de type ERP / BI :

- une table projet
- des dimensions de navigation
- un catalogue d'articles
- une table de faits pour les mesures CAPEX

L'objectif est de supporter facilement des dashboards dynamiques
proches de Power BI avec un schema en etoile simple a comprendre.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class BuildProject(Base):
    """
    Projet principal suivi dans l'application.

    Cette table joue le role de "racine" fonctionnelle :
    toutes les dimensions, tous les articles et tous les faits
    sont rattaches a un projet.
    """

    __tablename__ = "build_projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    devise: Mapped[str] = mapped_column(String(10), default="FCFA")
    statut: Mapped[str] = mapped_column(String(50), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=datetime.utcnow)

    lots = relationship("BuildLot", back_populates="project", cascade="all, delete-orphan")
    sous_lots = relationship(
        "BuildSousLot",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    famille_dimensions = relationship(
        "BuildFamilyDimension",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    niveau_dimensions = relationship(
        "BuildLevelDimension",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    batiment_dimensions = relationship(
        "BuildBuildingDimension",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    articles = relationship("BuildArticle", back_populates="project", cascade="all, delete-orphan")
    fact_rows = relationship("BuildFactMetre", back_populates="project", cascade="all, delete-orphan")


class BuildLot(Base):
    """
    Dimension LOT.

    Un lot appartient a un projet et peut contenir plusieurs sous-lots.
    """

    __tablename__ = "build_lots"
    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_build_lot_project_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("build_projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    project = relationship("BuildProject", back_populates="lots")
    sous_lots = relationship("BuildSousLot", back_populates="lot", cascade="all, delete-orphan")
    articles = relationship("BuildArticle", back_populates="lot")
    fact_rows = relationship("BuildFactMetre", back_populates="lot")


class BuildSousLot(Base):
    """
    Sous-lot rattache a un lot.

    Ce niveau est utile pour des analyses plus fines dans le DQE
    sans surcharger directement la table article.
    """

    __tablename__ = "build_sous_lots"
    __table_args__ = (
        UniqueConstraint("lot_id", "code", name="uq_build_sous_lot_lot_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("build_projects.id"), index=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("build_lots.id"), index=True)
    code: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    project = relationship("BuildProject", back_populates="sous_lots")
    lot = relationship("BuildLot", back_populates="sous_lots")
    articles = relationship("BuildArticle", back_populates="sous_lot")
    fact_rows = relationship("BuildFactMetre", back_populates="sous_lot")


class BuildFamilyDimension(Base):
    """
    Dimension FAMILLE ARTICLE.

    On la separe de la table article pour faciliter les filtres,
    les regroupements et les KPI par famille.
    """

    __tablename__ = "build_dim_familles"
    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_build_famille_project_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("build_projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(50), index=True)
    label: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    importable: Mapped[bool] = mapped_column(default=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)

    project = relationship("BuildProject", back_populates="famille_dimensions")
    articles = relationship("BuildArticle", back_populates="famille")
    fact_rows = relationship("BuildFactMetre", back_populates="famille")


class BuildLevelDimension(Base):
    """
    Dimension NIVEAU.

    Exemples : RDC, ETAGE 1, DUPLEX 1, TERRASSE.
    """

    __tablename__ = "build_dim_niveaux"
    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_build_niveau_project_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("build_projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    label: Mapped[str] = mapped_column(String(255), index=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    project = relationship("BuildProject", back_populates="niveau_dimensions")
    fact_rows = relationship("BuildFactMetre", back_populates="niveau")


class BuildBuildingDimension(Base):
    """
    Dimension BATIMENT.

    Exemples : Principal, Annexe.
    """

    __tablename__ = "build_dim_batiments"
    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_build_batiment_project_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("build_projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    label: Mapped[str] = mapped_column(String(255), index=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    project = relationship("BuildProject", back_populates="batiment_dimensions")
    fact_rows = relationship("BuildFactMetre", back_populates="batiment")


class BuildArticle(Base):
    """
    Catalogue article / BPU.

    Un article decrit la reference metier :
    designation, unite, lot, sous-lot et famille.

    Cette table ne porte pas les quantites chantier.
    Les quantites et montants vivent dans la table de faits.
    """

    __tablename__ = "build_articles"
    __table_args__ = (
        UniqueConstraint("project_id", "code_bpu", name="uq_build_article_project_bpu"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("build_projects.id"), index=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("build_lots.id"), index=True)
    sous_lot_id: Mapped[int | None] = mapped_column(
        ForeignKey("build_sous_lots.id"),
        nullable=True,
        index=True,
    )
    famille_id: Mapped[int | None] = mapped_column(
        ForeignKey("build_dim_familles.id"),
        nullable=True,
        index=True,
    )
    code_bpu: Mapped[str] = mapped_column(String(255), index=True)
    designation: Mapped[str] = mapped_column(Text())
    unite: Mapped[str] = mapped_column(String(30))
    type_cout: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pu_local_reference: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    pu_chine_reference: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)

    project = relationship("BuildProject", back_populates="articles")
    lot = relationship("BuildLot", back_populates="articles")
    sous_lot = relationship("BuildSousLot", back_populates="articles")
    famille = relationship("BuildFamilyDimension", back_populates="articles")
    fact_rows = relationship("BuildFactMetre", back_populates="article")


class BuildFactMetre(Base):
    """
    Table de faits principale pour les dashboards.

    Une ligne = une mesure chantier exploitable dans les KPI :
    quantite, prix, montants, economie et decision.

    Les dimensions rattachees permettent les filtres globaux
    et les drill-down :
    LOT -> FAMILLE -> ARTICLE, plus BATIMENT et NIVEAU.
    """

    __tablename__ = "build_fact_metre"
    __table_args__ = (
        UniqueConstraint("project_id", "source_row_key", name="uq_build_fact_project_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("build_projects.id"), index=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("build_articles.id"), index=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("build_lots.id"), index=True)
    sous_lot_id: Mapped[int | None] = mapped_column(
        ForeignKey("build_sous_lots.id"),
        nullable=True,
        index=True,
    )
    famille_id: Mapped[int | None] = mapped_column(
        ForeignKey("build_dim_familles.id"),
        nullable=True,
        index=True,
    )
    niveau_id: Mapped[int | None] = mapped_column(
        ForeignKey("build_dim_niveaux.id"),
        nullable=True,
        index=True,
    )
    batiment_id: Mapped[int | None] = mapped_column(
        ForeignKey("build_dim_batiments.id"),
        nullable=True,
        index=True,
    )

    quantite: Mapped[float] = mapped_column(Float, default=0.0)
    pu_local: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    pu_chine: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_local: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    total_import: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    economie: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    taux_economie: Mapped[float] = mapped_column(Float, default=0.0)
    decision: Mapped[str] = mapped_column(String(30), default="LOCAL", index=True)
    source_row_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    project = relationship("BuildProject", back_populates="fact_rows")
    article = relationship("BuildArticle", back_populates="fact_rows")
    lot = relationship("BuildLot", back_populates="fact_rows")
    sous_lot = relationship("BuildSousLot", back_populates="fact_rows")
    famille = relationship("BuildFamilyDimension", back_populates="fact_rows")
    niveau = relationship("BuildLevelDimension", back_populates="fact_rows")
    batiment = relationship("BuildBuildingDimension", back_populates="fact_rows")
