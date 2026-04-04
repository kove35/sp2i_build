"""
Rapport detaille article par article entre le DQE PDF source et build_fact_metre.

Prerequis :
- le PDF a ete importe via `python data/import_pdf_dqe.py`
- le schema analytique a ete seed dans sp2i_saas.db

Sorties :
- artifacts/dqe_pdf_vs_analytics_articles.csv
- artifacts/dqe_pdf_vs_analytics_articles_report.md
"""

from __future__ import annotations

import csv
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

from sqlalchemy.orm import joinedload


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import DATABASE_PATH
from backend.db.session import SessionLocal
from backend.models.build_analytics import BuildFactMetre, BuildLot


DEFAULT_SOURCE_FILE = "DQE_MEDICAL CENTER_13-08-2025.xlsx.pdf"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
CSV_OUTPUT_PATH = ARTIFACTS_DIR / "dqe_pdf_vs_analytics_articles.csv"
MARKDOWN_OUTPUT_PATH = ARTIFACTS_DIR / "dqe_pdf_vs_analytics_articles_report.md"


def normalize_text(value: str | None) -> str:
    """
    Normalise un texte pour permettre un rapprochement souple.
    """
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace("’", "'").replace("Œ", "OE")
    return " ".join(normalized.upper().split())


def lot_total_mismatches() -> set[str]:
    """
    Identifie les lots dont le total PDF differe du total analytique brut.
    """
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        pdf_rows = connection.execute(
            """
            SELECT lot_code, total_ht
            FROM source_dqe_pdf_lots
            WHERE source_file = ?
            """,
            (DEFAULT_SOURCE_FILE,),
        ).fetchall()

    session = SessionLocal()
    try:
        db_totals: dict[str, float] = defaultdict(float)
        rows = (
            session.query(BuildFactMetre)
            .options(joinedload(BuildFactMetre.lot))
            .all()
        )
        for row in rows:
            if not row.lot:
                continue
            lot_code = row.lot.name.replace("L0T", "LOT")
            db_totals[lot_code] += float(row.quantite or 0) * float(row.pu_local or 0)
    finally:
        session.close()

    mismatches: set[str] = set()
    for row in pdf_rows:
        lot_code = row["lot_code"]
        pdf_total = float(row["total_ht"] or 0)
        db_total = db_totals.get(lot_code, 0.0)
        if abs(pdf_total - db_total) >= 1.0:
            mismatches.add(lot_code)
    return mismatches


def load_pdf_article_groups() -> dict[tuple[str, str], dict]:
    """
    Charge et agrege les articles issus du PDF.
    """
    aggregated: dict[tuple[str, str], dict] = {}

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                lot_code,
                lot_label,
                designation,
                designation_normalized,
                unite,
                quantite,
                pu_ht,
                total_ht,
                is_pm
            FROM source_dqe_pdf_articles
            WHERE source_file = ?
            ORDER BY lot_code, designation_normalized
            """,
            (DEFAULT_SOURCE_FILE,),
        ).fetchall()

    for row in rows:
        key = (row["lot_code"], row["designation_normalized"])
        if key not in aggregated:
            aggregated[key] = {
                "lot_code": row["lot_code"],
                "lot_label": row["lot_label"],
                "designation_pdf": row["designation"],
                "designation_normalized": row["designation_normalized"],
                "unite_pdf": row["unite"],
                "quantite_pdf": 0.0,
                "total_ht_pdf": 0.0,
                "line_count_pdf": 0,
                "is_pm": 0,
            }

        aggregated[key]["quantite_pdf"] += float(row["quantite"] or 0)
        aggregated[key]["total_ht_pdf"] += float(row["total_ht"] or 0)
        aggregated[key]["line_count_pdf"] += 1
        aggregated[key]["is_pm"] = max(aggregated[key]["is_pm"], int(row["is_pm"] or 0))

    return aggregated


def load_db_article_groups() -> dict[tuple[str, str], dict]:
    """
    Charge et agrege les lignes analytiques par lot + designation normalisee.
    """
    aggregated: dict[tuple[str, str], dict] = {}
    session = SessionLocal()

    try:
        rows = (
            session.query(BuildFactMetre)
            .options(
                joinedload(BuildFactMetre.article),
                joinedload(BuildFactMetre.lot),
            )
            .all()
        )

        for row in rows:
            if not row.article or not row.lot:
                continue

            lot_code = row.lot.name.replace("L0T", "LOT")
            normalized_designation = normalize_text(row.article.designation)
            key = (lot_code, normalized_designation)

            if key not in aggregated:
                aggregated[key] = {
                    "lot_code": lot_code,
                    "designation_db": row.article.designation,
                    "unite_db": row.article.unite,
                    "quantite_db": 0.0,
                    "base_ht_db": 0.0,
                    "line_count_db": 0,
                }

            aggregated[key]["quantite_db"] += float(row.quantite or 0)
            aggregated[key]["base_ht_db"] += float(row.quantite or 0) * float(row.pu_local or 0)
            aggregated[key]["line_count_db"] += 1
    finally:
        session.close()

    return aggregated


def build_article_comparison_rows() -> list[dict]:
    """
    Construit les lignes de comparaison article/article.
    """
    mismatching_lots = lot_total_mismatches()
    pdf_groups = load_pdf_article_groups()
    db_groups = load_db_article_groups()

    rows: list[dict] = []
    all_keys = set(pdf_groups) | set(db_groups)

    for lot_code, designation_key in sorted(all_keys):
        if lot_code not in mismatching_lots:
            continue

        pdf_row = pdf_groups.get((lot_code, designation_key), {})
        db_row = db_groups.get((lot_code, designation_key), {})

        total_ht_pdf = float(pdf_row.get("total_ht_pdf", 0))
        base_ht_db = float(db_row.get("base_ht_db", 0))
        ecart = base_ht_db - total_ht_pdf

        rows.append(
            {
                "lot_code": lot_code,
                "designation_normalized": designation_key,
                "designation_pdf": pdf_row.get("designation_pdf"),
                "designation_db": db_row.get("designation_db"),
                "unite_pdf": pdf_row.get("unite_pdf"),
                "unite_db": db_row.get("unite_db"),
                "quantite_pdf": round(float(pdf_row.get("quantite_pdf", 0)), 4),
                "quantite_db": round(float(db_row.get("quantite_db", 0)), 4),
                "total_ht_pdf": round(total_ht_pdf, 2),
                "base_ht_db": round(base_ht_db, 2),
                "ecart_base_ht": round(ecart, 2),
                "present_pdf": bool(pdf_row),
                "present_db": bool(db_row),
                "is_pm": int(pdf_row.get("is_pm", 0)),
            }
        )

    return rows


def write_csv(rows: list[dict]) -> None:
    """
    Ecrit le detail article/article au format CSV.
    """
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_OUTPUT_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "lot_code",
                "designation_normalized",
                "designation_pdf",
                "designation_db",
                "unite_pdf",
                "unite_db",
                "quantite_pdf",
                "quantite_db",
                "total_ht_pdf",
                "base_ht_db",
                "ecart_base_ht",
                "present_pdf",
                "present_db",
                "is_pm",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict]) -> None:
    """
    Ecrit une synthese des ecarts article/article.
    """
    grouped_rows: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped_rows[row["lot_code"]].append(row)

    lines = [
        "# Rapport detaille article par article",
        "",
        f"- Source PDF : `{DEFAULT_SOURCE_FILE}`",
        f"- Lignes comparees : `{len(rows)}`",
        "",
        "## Resume",
        "",
    ]

    for lot_code, lot_rows in sorted(grouped_rows.items()):
        missing_in_db = sum(1 for row in lot_rows if row["present_pdf"] and not row["present_db"])
        missing_in_pdf = sum(1 for row in lot_rows if row["present_db"] and not row["present_pdf"])
        biggest_gap = max(lot_rows, key=lambda row: abs(row["ecart_base_ht"]))
        lines.append(
            f"- `{lot_code}` : "
            f"{missing_in_db} designations du PDF absentes en base, "
            f"{missing_in_pdf} designations base absentes du PDF, "
            f"plus grand ecart = `{biggest_gap['ecart_base_ht']:,.2f}`".replace(",", " ")
        )

    lines.extend(["", "## Plus grands ecarts article/article", ""])

    for row in sorted(rows, key=lambda item: abs(item["ecart_base_ht"]), reverse=True)[:20]:
        lines.append(
            "- "
            f"{row['lot_code']} | "
            f"PDF=`{row['designation_pdf']}` | "
            f"DB=`{row['designation_db']}` | "
            f"PDF HT=`{row['total_ht_pdf']:,.2f}` | "
            f"DB HT=`{row['base_ht_db']:,.2f}` | "
            f"Ecart=`{row['ecart_base_ht']:,.2f}`".replace(",", " ")
        )

    MARKDOWN_OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """
    Point d'entree principal.
    """
    rows = build_article_comparison_rows()
    write_csv(rows)
    write_markdown(rows)
    print(f"Rapport CSV genere : {CSV_OUTPUT_PATH}")
    print(f"Rapport Markdown genere : {MARKDOWN_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
