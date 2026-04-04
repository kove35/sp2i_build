"""
Modele projet SaaS.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class Project(Base):
    """
    Projet immobilier pilote dans l'application.
    """

    __tablename__ = "saas_projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("saas_users.id"))

    owner = relationship("User", back_populates="projects")
    capex_items = relationship(
        "ProjectCapexItem",
        back_populates="project",
        cascade="all, delete-orphan",
    )
