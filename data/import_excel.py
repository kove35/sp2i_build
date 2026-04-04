"""
Script d'import Excel vers SQLite pour le projet SP2I_Build.

Objectif :
- lire un fichier Excel (.xlsx)
- creer la base SQLite sp2i_build.db si elle n'existe pas
- creer les tables SQL automatiquement
- importer les donnees du fichier Excel dans la base

Exemples :
    python data/import_excel.py
    python data/import_excel.py "BE_MONOPROJET_V2_0 _05_03.xlsx"

Si aucun fichier n'est passe en argument, le script cherche d'abord
un fichier .xlsx a la racine du projet, puis dans le dossier data/.
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd


# Dossier racine du projet : .../sp2i_build
PROJECT_DIR = Path(__file__).resolve().parent.parent

# Emplacement de la base SQLite
DATABASE_PATH = PROJECT_DIR / "sp2i_build.db"

# Dossier de travail pour les donnees
DATA_DIR = PROJECT_DIR / "data"


def clean_sql_name(name: str) -> str:
    """
    Nettoie un nom pour qu'il soit compatible avec SQL.

    Exemple :
    "Biens immobiliers" devient "biens_immobiliers"
    """
    cleaned_name = name.strip().lower()
    cleaned_name = re.sub(r"[^a-zA-Z0-9_]+", "_", cleaned_name)
    cleaned_name = re.sub(r"_+", "_", cleaned_name).strip("_")

    if not cleaned_name:
        return "colonne_sans_nom"

    if cleaned_name[0].isdigit():
        cleaned_name = f"col_{cleaned_name}"

    return cleaned_name


def build_clean_column_names(columns: list[object]) -> list[str]:
    """
    Cree des noms de colonnes propres et uniques pour SQLite.
    """
    clean_columns: list[str] = []
    used_names: set[str] = set()

    for column in columns:
        cleaned_column = clean_sql_name(str(column))
        original_name = cleaned_column
        index = 2

        while cleaned_column in used_names:
            cleaned_column = f"{original_name}_{index}"
            index += 1

        used_names.add(cleaned_column)
        clean_columns.append(cleaned_column)

    return clean_columns


def build_unique_sql_name(name: str, used_names: set[str]) -> str:
    """
    Cree un nom SQL propre et unique pour une table ou une colonne.
    """
    clean_name = clean_sql_name(name)
    original_name = clean_name
    index = 2

    while clean_name in used_names:
        clean_name = f"{original_name}_{index}"
        index += 1

    used_names.add(clean_name)
    return clean_name


def find_excel_file() -> Path:
    """
    Determine quel fichier Excel importer.

    Priorite :
    1. le chemin passe en argument
    2. le premier fichier .xlsx trouve a la racine du projet
    3. le premier fichier .xlsx trouve dans le dossier data/
    """
    if len(sys.argv) > 1:
        excel_path = Path(sys.argv[1]).expanduser().resolve()
        if not excel_path.exists():
            raise FileNotFoundError(
                f"Le fichier Excel indique est introuvable : {excel_path}"
            )
        return excel_path

    root_excel_files = sorted(PROJECT_DIR.glob("*.xlsx"))
    if root_excel_files:
        return root_excel_files[0]

    data_excel_files = sorted(DATA_DIR.glob("*.xlsx"))
    if data_excel_files:
        return data_excel_files[0]

    raise FileNotFoundError(
        "Aucun fichier .xlsx trouve. Placez votre fichier Excel a la racine "
        'du projet ou dans le dossier data/, ou lancez : '
        'python data/import_excel.py "mon_fichier.xlsx"'
    )


def guess_sqlite_type(series: pd.Series) -> str:
    """
    Devine le type SQL d'une colonne.

    Regles simples :
    - INTEGER si toutes les valeurs sont entieres
    - REAL si les valeurs sont numeriques
    - TEXT sinon
    """
    values = series.dropna()

    if values.empty:
        return "TEXT"

    numeric_values = pd.to_numeric(values, errors="coerce")

    if numeric_values.notna().all():
        if (numeric_values % 1 == 0).all():
            return "INTEGER"
        return "REAL"

    return "TEXT"


def create_metadata_table(connection: sqlite3.Connection) -> None:
    """
    Cree une table de suivi des imports.
    """
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS import_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL,
            sheet_name TEXT NOT NULL,
            imported_rows INTEGER NOT NULL,
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def create_table_for_sheet(
    connection: sqlite3.Connection,
    table_name: str,
    dataframe: pd.DataFrame,
) -> list[str]:
    """
    Cree une table SQLite a partir d'une feuille Excel.

    Retour :
    - la liste finale des colonnes SQL creees
    """
    clean_columns = build_clean_column_names(list(dataframe.columns))
    sql_columns: list[str] = []

    for original_column, clean_column in zip(dataframe.columns, clean_columns):
        column_type = guess_sqlite_type(dataframe[original_column])
        sql_columns.append(f'"{clean_column}" {column_type}')

    connection.execute(f'DROP TABLE IF EXISTS "{table_name}"')

    create_table_sql = f'''
        CREATE TABLE "{table_name}" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {", ".join(sql_columns)}
        )
    '''
    connection.execute(create_table_sql)

    return clean_columns


def insert_sheet_data(
    connection: sqlite3.Connection,
    table_name: str,
    dataframe: pd.DataFrame,
    clean_columns: list[str],
) -> int:
    """
    Insere les lignes d'une feuille Excel dans la table SQL.
    """
    dataframe_to_insert = dataframe.copy()
    dataframe_to_insert.columns = clean_columns

    def normalize_sqlite_value(value: object) -> object:
        """
        Convertit une valeur pandas en valeur compatible SQLite.
        """
        if pd.isna(value):
            return None

        if isinstance(value, pd.Timestamp):
            return value.isoformat()

        return value

    # SQLite sait bien stocker le texte, les nombres et None.
    # On convertit donc les valeurs pandas avant insertion.
    dataframe_to_insert = dataframe_to_insert.map(normalize_sqlite_value)

    placeholders = ", ".join(["?"] * len(clean_columns))
    quoted_columns = ", ".join(f'"{column}"' for column in clean_columns)
    insert_sql = (
        f'INSERT INTO "{table_name}" ({quoted_columns}) VALUES ({placeholders})'
    )

    rows = list(dataframe_to_insert.itertuples(index=False, name=None))
    if rows:
        connection.executemany(insert_sql, rows)

    return len(rows)


def import_excel_to_sqlite(excel_path: Path) -> None:
    """
    Fonction principale :
    - ouvre le fichier Excel
    - cree la base SQLite
    - cree une table par feuille Excel
    - importe les donnees
    """
    print(f"Fichier Excel selectionne : {excel_path}")
    print(f"Base SQLite cible : {DATABASE_PATH}")

    excel_file = pd.ExcelFile(excel_path)

    with sqlite3.connect(DATABASE_PATH) as connection:
        create_metadata_table(connection)
        used_table_names: set[str] = set()

        for sheet_name in excel_file.sheet_names:
            print(f"\nImport de la feuille : {sheet_name}")

            dataframe = pd.read_excel(excel_path, sheet_name=sheet_name)
            dataframe = dataframe.dropna(how="all")

            # Certains onglets du fichier servent juste de separateur visuel.
            # Exemple : '---01_CONFIGURATION ---'
            # Dans ce cas, pandas ne trouve aucune colonne exploitable.
            if len(dataframe.columns) == 0:
                print("Feuille ignoree : aucune colonne exploitable.")
                connection.execute(
                    """
                    INSERT INTO import_logs (source_file, sheet_name, imported_rows)
                    VALUES (?, ?, ?)
                    """,
                    (excel_path.name, sheet_name, 0),
                )
                continue

            table_name = build_unique_sql_name(sheet_name, used_table_names)
            clean_columns = create_table_for_sheet(connection, table_name, dataframe)
            inserted_rows = insert_sheet_data(
                connection,
                table_name,
                dataframe,
                clean_columns,
            )

            connection.execute(
                """
                INSERT INTO import_logs (source_file, sheet_name, imported_rows)
                VALUES (?, ?, ?)
                """,
                (excel_path.name, sheet_name, inserted_rows),
            )

            print(
                f"Table creee : {table_name} | "
                f"Lignes importees : {inserted_rows}"
            )

        connection.commit()

    print("\nImport termine avec succes.")


def main() -> None:
    """
    Point d'entree du script.
    """
    try:
        excel_path = find_excel_file()
        import_excel_to_sqlite(excel_path)
    except Exception as error:
        print(f"Erreur : {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
