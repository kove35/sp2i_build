"""
Routes FastAPI pour exposer la base ERP/DQE locale.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from backend.services.erp_dqe_service import ERPDQEService, ERPFilters


router = APIRouter(prefix="/erp", tags=["ERP DQE"])
erp_service = ERPDQEService()


@router.get("/status")
def get_erp_status() -> dict:
    return {"available": erp_service.is_available()}


@router.get("/filters")
def get_erp_filters() -> dict:
    return erp_service.get_filters()


@router.get("/dashboard")
def get_erp_dashboard(
    batiment: str | None = Query(default=None),
    niveau: str | None = Query(default=None),
    lot: int | None = Query(default=None),
) -> dict:
    return erp_service.get_dashboard(ERPFilters(batiment=batiment, niveau=niveau, lot=lot))
