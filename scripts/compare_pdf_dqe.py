"""
Compare un DQE PDF avec le schema analytique SP2I_Build.

Ce script genere un rapport simple et relancable pour verifier si
les donnees du PDF de reference correspondent aux donnees chargees
dans build_fact_metre.

Sorties produites :
- artifacts/dqe_pdf_vs_analytics_lots.csv
- artifacts/dqe_pdf_vs_analytics_report.md
"""

from __future__ import annotations

import csv
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from sqlalchemy import func
from sqlalchemy.orm import Session

DEFAULT_PDF_PATH = Path(
    r"C:\Users\Geoffrey\Desktop\Services Construct\DQE_MEDICAL CENTER_13-08-2025.xlsx.pdf"
)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
CSV_OUTPUT_PATH = ARTIFACTS_DIR / "dqe_pdf_vs_analytics_lots.csv"
MARKDOWN_OUTPUT_PATH = ARTIFACTS_DIR / "dqe_pdf_vs_analytics_report.md"

from backend.db.session import SessionLocal
from backend.models.build_analytics import BuildFactMetre, BuildLot, BuildProject


@dataclass
class PdfLotTotal:
    """
    Total d'un lot extrait depuis le PDF.
    """

    lot_code: str
    designation: str
    total_ht: float


def normalize_text(value: str) -> str:
    """
    Normalise un texte pour comparer des libelles metier.
    """
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(normalized.upper().replace("’", "'").replace("Œ", "OE").split())


def parse_amount(value: str | None) -> float:
    """
    Convertit un montant texte du PDF en float.
    """
    if not value:
        return 0.0
    return float(value.replace(" ", "").replace("\xa0", ""))


def extract_pdf_lot_totals(pdf_path: Path) -> list[PdfLotTotal]:
    """
    Lit la page de recapitulatif et extrait les totaux par lot.
    """
    with pdfplumber.open(pdf_path) as pdf:
        recap_table = pdf.pages[0].extract_tables()[1]

    lot_totals: list[PdfLotTotal] = []
    for row in recap_table[1:]:
        designation = (row[1] or "").strip()
        amount_text = (row[2] or "").strip()

        if not designation.startswith("LOT "):
            continue

        lot_code, _, lot_label = designation.partition(":")
        lot_totals.append(
            PdfLotTotal(
                lot_code=lot_code.strip(),
                designation=lot_label.strip(),
                total_ht=parse_amount(amount_text),
            )
        )

    return lot_totals


def fetch_database_lot_totals(session: Session) -> tuple[str, list[dict]]:
    """
    Charge les totaux analytiques par lot depuis SQLAlchemy.

    Deux colonnes sont utiles :
    - base_ht_db : quantite * pu_local
    - total_local_db : total_local calcule par le modele
    """
    project = session.query(BuildProject).order_by(BuildProject.id.asc()).first()
    if project is None:
        raise RuntimeError("Aucun projet analytique n'est disponible.")

    rows = (
        session.query(
            BuildLot.name,
            BuildLot.description,
            func.sum(BuildFactMetre.quantite * BuildFactMetre.pu_local),
            func.sum(BuildFactMetre.total_local),
        )
        .join(BuildFactMetre, BuildFactMetre.lot_id == BuildLot.id)
        .filter(BuildLot.project_id == project.id)
        .group_by(BuildLot.id)
        .order_by(BuildLot.display_order.asc(), BuildLot.name.asc())
        .all()
    )

    payload = []
    for lot_name, lot_description, base_ht, total_local in rows:
        payload.append(
            {
                "lot_code": lot_name,
                "lot_label": lot_description or lot_name,
                "base_ht_db": float(base_ht or 0),
                "total_local_db": float(total_local or 0),
                "normalized_code": normalize_text(lot_name.replace("L0T", "LOT")),
            }
        )

    return project.name, payload


def build_comparison_rows(
    pdf_lot_totals: list[PdfLotTotal],
    database_lot_totals: list[dict],
) -> list[dict]:
    """
    Construit les lignes de comparaison PDF vs base analytique.
    """
    db_by_code = {
        lot_payload["normalized_code"]: lot_payload for lot_payload in database_lot_totals
    }

    comparison_rows = []
    for pdf_lot in pdf_lot_totals:
        db_lot = db_by_code.get(normalize_text(pdf_lot.lot_code))

        base_ht_db = db_lot["base_ht_db"] if db_lot else 0.0
        total_local_db = db_lot["total_local_db"] if db_lot else 0.0
        ecart_base_ht = base_ht_db - pdf_lot.total_ht
        ecart_total_local = total_local_db - pdf_lot.total_ht

        comparison_rows.append(
            {
                "lot_code": pdf_lot.lot_code,
                "designation_pdf": pdf_lot.designation,
                "total_ht_pdf": round(pdf_lot.total_ht, 2),
                "base_ht_db": round(base_ht_db, 2),
                "total_local_db": round(total_local_db, 2),
                "ecart_base_ht_vs_pdf": round(ecart_base_ht, 2),
                "ecart_total_local_vs_pdf": round(ecart_total_local, 2),
                "match_base_ht": abs(ecart_base_ht) < 1.0,
            }
        )

    return comparison_rows


def write_csv_report(rows: list[dict], output_path: Path) -> None:
    """
    Ecrit le rapport detaille par lot au format CSV.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "lot_code",
                "designation_pdf",
                "total_ht_pdf",
                "base_ht_db",
                "total_local_db",
                "ecart_base_ht_vs_pdf",
                "ecart_total_local_vs_pdf",
                "match_base_ht",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_markdown_report(
    project_name: str,
    pdf_path: Path,
    rows: list[dict],
    output_path: Path,
) -> None:
    """
    Ecrit une synthese lisible en Markdown.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_pdf = sum(row["total_ht_pdf"] for row in rows)
    total_base_ht = sum(row["base_ht_db"] for row in rows)
    total_model = sum(row["total_local_db"] for row in rows)
    matching_lots = sum(1 for row in rows if row["match_base_ht"])

    rows_sorted = sorted(
        rows,
        key=lambda row: abs(row["ecart_base_ht_vs_pdf"]),
        reverse=True,
    )

    lines = [
        "# Rapport de comparaison DQE PDF vs SP2I_Build",
        "",
        f"- Projet analytique teste : `{project_name}`",
        f"- PDF source : `{pdf_path}`",
        f"- Lots compares : `{len(rows)}`",
        f"- Lots identiques sur la base HT : `{matching_lots}/{len(rows)}`",
        "",
        "## Totaux globaux",
        "",
        f"- Total HT PDF : `{total_pdf:,.2f}`".replace(",", " "),
        f"- Total base HT en base : `{total_base_ht:,.2f}`".replace(",", " "),
        f"- Total `total_local` du modele : `{total_model:,.2f}`".replace(",", " "),
        "",
        "## Plus grands ecarts (base HT vs PDF)",
        "",
    ]

    for row in rows_sorted[:10]:
        lines.append(
            "- "
            f"{row['lot_code']} {row['designation_pdf']} : "
            f"PDF={row['total_ht_pdf']:,.2f} | "
            f"DB={row['base_ht_db']:,.2f} | "
            f"Ecart={row['ecart_base_ht_vs_pdf']:,.2f}".replace(",", " ")
        )

    lines.extend(
        [
            "",
            "## Lecture rapide",
            "",
            "- `base_ht_db` compare le PDF au calcul brut `quantite × pu_local`.",
            "- `total_local_db` inclut la logique metier du modele actuel, donc il peut etre plus eleve.",
            "- Si les ecarts sont importants, cela indique que la base actuelle ne correspond pas a cette version du DQE.",
            "",
        ]
    )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """
    Point d'entree du script.
    """
    if not DEFAULT_PDF_PATH.exists():
        raise FileNotFoundError(f"PDF introuvable : {DEFAULT_PDF_PATH}")

    pdf_lot_totals = extract_pdf_lot_totals(DEFAULT_PDF_PATH)

    session = SessionLocal()
    try:
        project_name, database_lot_totals = fetch_database_lot_totals(session)
    finally:
        session.close()

    comparison_rows = build_comparison_rows(pdf_lot_totals, database_lot_totals)
    write_csv_report(comparison_rows, CSV_OUTPUT_PATH)
    write_markdown_report(project_name, DEFAULT_PDF_PATH, comparison_rows, MARKDOWN_OUTPUT_PATH)

    print(f"Rapport CSV genere : {CSV_OUTPUT_PATH}")
    print(f"Rapport Markdown genere : {MARKDOWN_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
