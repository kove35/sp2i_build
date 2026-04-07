"""
Import d'un DQE PDF dans les tables sources SQLite.

Objectif :
- conserver une source officielle issue du PDF
- rendre le DQE testable et comparable au modele analytique
- preparer de futurs rapprochements ou imports vers le schema analytique

Usage :
    python data/import_pdf_dqe.py
    python data/import_pdf_dqe.py "C:\\chemin\\mon_dqe.pdf"
"""

from __future__ import annotations

import re
import sqlite3
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pdfplumber


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import APP_DATABASE_PATH
from backend.database import initialize_database


DEFAULT_PDF_PATH = Path(
    r"C:\Users\Geoffrey\Desktop\Services Construct\DQE_MEDICAL CENTER_13-08-2025.xlsx.pdf"
)
VALID_UNITS = {
    "ENS",
    "FF",
    "M2",
    "M3",
    "ML",
    "KG",
    "U",
    "UN",
    "FORFAIT",
}


@dataclass
class PdfLotRow:
    source_file: str
    page_number: int
    lot_code: str
    designation: str
    total_ht: float


@dataclass
class PdfArticleRow:
    source_file: str
    page_number: int
    lot_code: str
    lot_label: str | None
    section_code: str | None
    section_label: str | None
    item_number: str | None
    designation: str
    designation_normalized: str
    unite: str
    quantite: float | None
    pu_ht: float | None
    total_ht: float | None
    is_pm: int


def normalize_text(value: str | None) -> str:
    """
    Normalise un texte pour faciliter les rapprochements.
    """
    if not value:
        return ""

    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace("’", "'").replace("Œ", "OE")
    return " ".join(normalized.upper().split())


def clean_cell(value: object) -> str:
    """
    Nettoie une cellule extraite du PDF.
    """
    if value is None:
        return ""
    return " ".join(str(value).replace("\n", " ").split())


def parse_float(value: str) -> float | None:
    """
    Convertit une valeur numerique PDF en float.
    """
    cleaned = value.replace(" ", "").replace("\xa0", "").replace(",", ".").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_amount(value: str) -> float | None:
    """
    Convertit un montant PDF en float.
    """
    cleaned = value.replace(" ", "").replace("\xa0", "").strip()
    if not cleaned or cleaned.upper() == "PM":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def detect_lot_header(value: str) -> tuple[str, str] | None:
    """
    Detecte un libelle de lot du type 'LOT 1 : GROS OEUVRE'.
    """
    match = re.match(r"^(LOT\s+\d+)\s*:\s*(.+)$", normalize_text(value))
    if not match:
        return None
    return match.group(1), match.group(2)


def is_section_header(first_cell: str, second_cell: str) -> bool:
    """
    Detecte les lignes de section metier comme 'A INSTALLATION...'.
    """
    combined = normalize_text(f"{first_cell} {second_cell}")
    return bool(re.match(r"^[A-Z]\s+[A-Z]", combined))


def is_subtotal_or_total(value: str) -> bool:
    """
    Ignore les lignes de totalisation.
    """
    normalized = normalize_text(value)
    return normalized.startswith("SOUS TOTAL") or normalized.startswith("TOTAL LOT")


def extract_recap_lots(pdf_path: Path) -> list[PdfLotRow]:
    """
    Extrait le recapitulatif des lots depuis la premiere page.
    """
    rows: list[PdfLotRow] = []

    with pdfplumber.open(pdf_path) as pdf:
        tables = pdf.pages[0].extract_tables()
        if len(tables) < 2:
            return rows

        recap_table = tables[1]
        for row in recap_table[1:]:
            designation = clean_cell(row[1] if len(row) > 1 else "")
            total_text = clean_cell(row[2] if len(row) > 2 else "")
            lot_header = detect_lot_header(designation)
            if not lot_header:
                continue

            lot_code, lot_label = lot_header
            total_ht = parse_amount(total_text)
            if total_ht is None:
                continue

            rows.append(
                PdfLotRow(
                    source_file=pdf_path.name,
                    page_number=1,
                    lot_code=lot_code,
                    designation=lot_label,
                    total_ht=total_ht,
                )
            )

    return rows


def extract_article_rows(pdf_path: Path) -> list[PdfArticleRow]:
    """
    Extrait les lignes d'articles detaillees depuis les tableaux du PDF.
    """
    article_rows: list[PdfArticleRow] = []
    current_lot_code: str | None = None
    current_lot_label: str | None = None
    current_section_code: str | None = None
    current_section_label: str | None = None

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            lot_matches = re.findall(r"(LOT\s+\d+\s*:\s*[^\n]+)", page_text, flags=re.IGNORECASE)
            if lot_matches:
                lot_header = detect_lot_header(lot_matches[0])
                if lot_header:
                    current_lot_code, current_lot_label = lot_header
                    current_section_code = None
                    current_section_label = None

            for table in page.extract_tables():
                for row in table:
                    cells = [clean_cell(cell) for cell in row]
                    while len(cells) < 6:
                        cells.append("")

                    first_cell, second_cell, unite, quantite, pu_ht, total_ht = cells[:6]

                    lot_header = detect_lot_header(second_cell or first_cell)
                    if lot_header:
                        current_lot_code, current_lot_label = lot_header
                        current_section_code = None
                        current_section_label = None
                        continue

                    if not current_lot_code:
                        continue

                    if is_section_header(first_cell, second_cell):
                        current_section_code = first_cell.strip() or None
                        current_section_label = second_cell.strip() or None
                        continue

                    if is_subtotal_or_total(second_cell or first_cell):
                        continue

                    designation = second_cell.strip()
                    unit_value = unite.strip().upper()
                    if unit_value not in VALID_UNITS:
                        continue

                    if normalize_text(designation) in {"Nº", "DESIGNATION DES PRESTATIONS"}:
                        continue

                    article_rows.append(
                        PdfArticleRow(
                            source_file=pdf_path.name,
                            page_number=page_index,
                            lot_code=current_lot_code,
                            lot_label=current_lot_label,
                            section_code=current_section_code,
                            section_label=current_section_label,
                            item_number=first_cell.strip() or None,
                            designation=designation,
                            designation_normalized=normalize_text(designation),
                            unite=unit_value,
                            quantite=parse_float(quantite),
                            pu_ht=parse_amount(pu_ht),
                            total_ht=parse_amount(total_ht),
                            is_pm=1 if total_ht.strip().upper() == "PM" else 0,
                        )
                    )

    return article_rows


def import_pdf_to_sqlite(pdf_path: Path) -> dict[str, int | str]:
    """
    Importe le PDF dans les tables sources SQLite.
    """
    initialize_database()

    lot_rows = extract_recap_lots(pdf_path)
    article_rows = extract_article_rows(pdf_path)

    with sqlite3.connect(APP_DATABASE_PATH) as connection:
        connection.execute(
            "DELETE FROM source_dqe_pdf_lots WHERE source_file = ?",
            (pdf_path.name,),
        )
        connection.execute(
            "DELETE FROM source_dqe_pdf_articles WHERE source_file = ?",
            (pdf_path.name,),
        )

        connection.executemany(
            """
            INSERT INTO source_dqe_pdf_lots (
                source_file, page_number, lot_code, designation, total_ht
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    row.source_file,
                    row.page_number,
                    row.lot_code,
                    row.designation,
                    row.total_ht,
                )
                for row in lot_rows
            ],
        )

        connection.executemany(
            """
            INSERT INTO source_dqe_pdf_articles (
                source_file,
                page_number,
                lot_code,
                lot_label,
                section_code,
                section_label,
                item_number,
                designation,
                designation_normalized,
                unite,
                quantite,
                pu_ht,
                total_ht,
                is_pm
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.source_file,
                    row.page_number,
                    row.lot_code,
                    row.lot_label,
                    row.section_code,
                    row.section_label,
                    row.item_number,
                    row.designation,
                    row.designation_normalized,
                    row.unite,
                    row.quantite,
                    row.pu_ht,
                    row.total_ht,
                    row.is_pm,
                )
                for row in article_rows
            ],
        )

        connection.commit()

    return {
        "source_file": pdf_path.name,
        "lots_imported": len(lot_rows),
        "articles_imported": len(article_rows),
        "database": APP_DATABASE_PATH.name,
    }


def resolve_pdf_path() -> Path:
    """
    Determine le PDF a importer.
    """
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).expanduser().resolve()
    return DEFAULT_PDF_PATH


def main() -> None:
    """
    Point d'entree CLI.
    """
    pdf_path = resolve_pdf_path()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF introuvable : {pdf_path}")

    result = import_pdf_to_sqlite(pdf_path)
    print("Import PDF DQE termine :")
    for key, value in result.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
