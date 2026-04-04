"""
Script simple pour initialiser les tables SQLAlchemy de SP2I_Build.

Usage :
    python -m backend.db.init_sqlalchemy_tables

Ce script cree :
- les tables du socle SaaS
- les tables analytiques pour les dashboards
"""

from backend.db.session import (
    get_sqlalchemy_table_names,
    initialize_all_sqlalchemy_tables,
)


def main() -> None:
    """
    Point d'entree du script.
    """
    initialize_all_sqlalchemy_tables()
    print("Tables SQLAlchemy initialisees :")
    for table_name in get_sqlalchemy_table_names():
        print(f"- {table_name}")


if __name__ == "__main__":
    main()
