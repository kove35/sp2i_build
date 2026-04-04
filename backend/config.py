"""
Configuration commune du backend.
"""

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "sp2i_build.db"
ERP_DATABASE_PATH = BASE_DIR / "sp2i_erp.db"
