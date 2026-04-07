"""
Configuration commune du backend.
"""

from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DATABASE_PATH = Path(
    os.getenv("SP2I_SOURCE_DB_PATH", str(BASE_DIR / "sp2i_build.db"))
).expanduser().resolve()

# Base SQLite applicative pour les tables mutables :
# - articles_dqe
# - source_dqe_pdf_lots / source_dqe_pdf_articles
# - app_settings
#
# En local, on conserve le comportement historique en pointant par defaut
# vers la meme base que la source. En production, il est recommande de
# definir SP2I_APP_DB_PATH vers un disque persistant Render.
APP_DATABASE_PATH = Path(
    os.getenv("SP2I_APP_DB_PATH", str(SOURCE_DATABASE_PATH))
).expanduser().resolve()

# Alias de compatibilite avec le code historique.
DATABASE_PATH = SOURCE_DATABASE_PATH

ERP_DATABASE_PATH = Path(
    os.getenv("SP2I_ERP_DB_PATH", str(BASE_DIR / "sp2i_erp.db"))
).expanduser().resolve()

EXCEL_SOURCE_PATH = Path(
    os.getenv("SP2I_EXCEL_PATH", str(BASE_DIR / "BE_MONOPROJET_V2_0 _05_03.xlsx"))
).expanduser().resolve()

AUTO_SEED_ANALYTICS = os.getenv("SP2I_AUTO_SEED_ANALYTICS", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
