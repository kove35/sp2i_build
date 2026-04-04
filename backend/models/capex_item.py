"""
Ligne de calcul CAPEX rattachee a un projet.
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class ProjectCapexItem(Base):
    """
    Unite de travail pour les dashboards SaaS.
    """

    __tablename__ = "saas_project_capex_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("saas_projects.id"), index=True)
    lot_id: Mapped[str] = mapped_column(String(120), index=True)
    family_article: Mapped[str] = mapped_column(String(255), index=True)
    code_bpu: Mapped[str] = mapped_column(String(255), index=True)
    batiment: Mapped[str] = mapped_column(String(120), index=True)
    niveau: Mapped[str] = mapped_column(String(120), index=True)
    decision: Mapped[str] = mapped_column(String(30), index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    montant_local: Mapped[float] = mapped_column(Float, default=0)
    montant_import: Mapped[float] = mapped_column(Float, default=0)
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    import_score: Mapped[float] = mapped_column(Float, default=0)
    source_index: Mapped[int] = mapped_column(Integer, default=0)

    project = relationship("Project", back_populates="capex_items")
