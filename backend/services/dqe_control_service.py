"""
Services de controle entre les DQE PDF sources et le schema analytique.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from collections import defaultdict
from pathlib import Path

from fastapi import HTTPException, status

from backend.config import DATABASE_PATH
from backend.db.session import SessionLocal, initialize_all_sqlalchemy_tables
from backend.models.build_analytics import (
    BuildArticle,
    BuildFactMetre,
    BuildFamilyDimension,
    BuildLot,
    BuildProject,
)
from scripts.compare_pdf_dqe import (
    CSV_OUTPUT_PATH as LOT_CSV_OUTPUT_PATH,
    MARKDOWN_OUTPUT_PATH as LOT_MARKDOWN_OUTPUT_PATH,
    PdfLotTotal,
    build_comparison_rows,
    fetch_database_lot_totals,
    write_csv_report,
    write_markdown_report,
)
from scripts.compare_pdf_dqe_articles import (
    CSV_OUTPUT_PATH as ARTICLE_CSV_OUTPUT_PATH,
    MARKDOWN_OUTPUT_PATH as ARTICLE_MARKDOWN_OUTPUT_PATH,
    write_csv as write_article_csv,
    write_markdown as write_article_markdown,
)


class DQEControlService:
    """
    Service applicatif pour piloter les controles DQE PDF.
    """

    def __init__(self, pdf_path: Path | None = None) -> None:
        self.pdf_path = pdf_path

    def _load_pdf_import_module(self):
        """
        Charge paresseusement le module d'import PDF.

        Cela permet au backend de demarrer meme si `pdfplumber`
        n'est pas encore installe dans l'environnement Python actif.
        """
        try:
            from data.import_pdf_dqe import DEFAULT_PDF_PATH, import_pdf_to_sqlite
        except ModuleNotFoundError as error:
            if getattr(error, "name", "") == "pdfplumber":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "Le module pdfplumber n'est pas installe dans cet environnement Python. "
                        "Installe-le avec : python -m pip install pdfplumber"
                    ),
                ) from error
            raise
        return DEFAULT_PDF_PATH, import_pdf_to_sqlite

    def _get_default_pdf_path(self) -> Path:
        default_pdf_path, _ = self._load_pdf_import_module()
        return default_pdf_path

    def _normalize_text(self, value: str | None) -> str:
        if not value:
            return ""
        normalized = unicodedata.normalize("NFKD", value)
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = normalized.replace("’", "'").replace("Œ", "OE")
        return " ".join(normalized.upper().split())

    def _slugify(self, value: str) -> str:
        normalized = self._normalize_text(value)
        normalized = re.sub(r"[^A-Z0-9]+", "_", normalized)
        return normalized.strip("_") or "DQE"

    def _resolve_pdf_path(self, pdf_path: str | None) -> Path:
        if pdf_path:
            return Path(pdf_path).expanduser().resolve()
        return self.pdf_path or self._get_default_pdf_path()

    def _resolve_source_file(self, source_file: str | None) -> str:
        if source_file:
            return source_file

        source_files = self.list_source_files()
        if source_files:
            return source_files[0]

        return (self.pdf_path or self._get_default_pdf_path()).name

    def list_source_files(self) -> list[str]:
        """
        Retourne la liste des DQE PDF deja importes.
        """
        with sqlite3.connect(DATABASE_PATH) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT source_file, MAX(id) AS max_id
                FROM source_dqe_pdf_articles
                GROUP BY source_file
                ORDER BY max_id DESC, source_file DESC
                """
            ).fetchall()
        return [row["source_file"] for row in rows]

    def _fetch_source_counts(self, source_file: str) -> dict[str, int]:
        with sqlite3.connect(DATABASE_PATH) as connection:
            connection.row_factory = sqlite3.Row
            lot_count = connection.execute(
                "SELECT COUNT(*) AS count FROM source_dqe_pdf_lots WHERE source_file = ?",
                (source_file,),
            ).fetchone()["count"]
            article_count = connection.execute(
                "SELECT COUNT(*) AS count FROM source_dqe_pdf_articles WHERE source_file = ?",
                (source_file,),
            ).fetchone()["count"]
        return {
            "lots_imported": int(lot_count),
            "articles_imported": int(article_count),
        }

    def _load_source_lot_totals(self, source_file: str) -> list[PdfLotTotal]:
        with sqlite3.connect(DATABASE_PATH) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT lot_code, designation, total_ht
                FROM source_dqe_pdf_lots
                WHERE source_file = ?
                ORDER BY id
                """,
                (source_file,),
            ).fetchall()

        return [
            PdfLotTotal(
                lot_code=row["lot_code"],
                designation=row["designation"],
                total_ht=float(row["total_ht"] or 0),
            )
            for row in rows
        ]

    def _load_source_article_groups(self, source_file: str) -> dict[tuple[str, str], dict]:
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
                (source_file,),
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

    def _load_db_article_groups(self) -> dict[tuple[str, str], dict]:
        aggregated: dict[tuple[str, str], dict] = {}
        session = SessionLocal()
        try:
            rows = (
                session.query(BuildFactMetre)
                .all()
            )
            for row in rows:
                if not row.article or not row.lot:
                    continue

                lot_code = row.lot.name.replace("L0T", "LOT")
                normalized_designation = self._normalize_text(row.article.designation)
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

    def _lot_total_mismatches(self, source_file: str) -> set[str]:
        pdf_rows = self._load_source_lot_totals(source_file)

        session = SessionLocal()
        try:
            db_totals: dict[str, float] = defaultdict(float)
            rows = session.query(BuildFactMetre).all()
            for row in rows:
                if not row.lot:
                    continue
                lot_code = row.lot.name.replace("L0T", "LOT")
                db_totals[lot_code] += float(row.quantite or 0) * float(row.pu_local or 0)
        finally:
            session.close()

        mismatches: set[str] = set()
        for row in pdf_rows:
            db_total = db_totals.get(row.lot_code, 0.0)
            if abs(row.total_ht - db_total) >= 1.0:
                mismatches.add(row.lot_code)
        return mismatches

    def import_source_pdf(self, pdf_path: str | None = None) -> dict[str, int | str]:
        """
        Importe un nouveau PDF DQE dans les tables sources SQLite.
        """
        _, import_pdf_to_sqlite = self._load_pdf_import_module()
        resolved_pdf_path = self._resolve_pdf_path(pdf_path)
        if not resolved_pdf_path.exists():
            raise FileNotFoundError(f"PDF introuvable : {resolved_pdf_path}")

        return import_pdf_to_sqlite(resolved_pdf_path)

    def refresh_source_and_reports(
        self,
        pdf_path: str | None = None,
        source_file: str | None = None,
    ) -> dict[str, int | str]:
        """
        Reimporte un PDF si besoin puis regenere les rapports de controle.
        """
        import_result: dict[str, int | str] = {}
        if pdf_path is not None or source_file is None:
            import_result = self.import_source_pdf(pdf_path)
            source_file = str(import_result["source_file"])

        resolved_source_file = self._resolve_source_file(source_file)

        session = SessionLocal()
        try:
            project_name, database_lot_totals = fetch_database_lot_totals(session)
        finally:
            session.close()

        pdf_lot_totals = self._load_source_lot_totals(resolved_source_file)
        lot_rows = build_comparison_rows(pdf_lot_totals, database_lot_totals)
        write_csv_report(lot_rows, LOT_CSV_OUTPUT_PATH)
        write_markdown_report(
            project_name,
            Path(resolved_source_file),
            lot_rows,
            LOT_MARKDOWN_OUTPUT_PATH,
        )

        article_rows = self.get_article_comparison(source_file=resolved_source_file)
        write_article_csv(article_rows)
        write_article_markdown(article_rows)

        matching_lots = sum(1 for row in lot_rows if row["match_base_ht"])
        source_counts = self._fetch_source_counts(resolved_source_file)
        return {
            **source_counts,
            **import_result,
            "source_file": resolved_source_file,
            "matching_lots": matching_lots,
            "compared_lots": len(lot_rows),
            "compared_article_rows": len(article_rows),
        }

    def get_summary(self, source_file: str | None = None) -> dict[str, int | str | bool]:
        """
        Retourne une synthese du controle courant.
        """
        resolved_source_file = self._resolve_source_file(source_file)
        source_counts = self._fetch_source_counts(resolved_source_file)
        lot_rows = self.get_lot_comparison(source_file=resolved_source_file)
        article_rows = self.get_article_comparison(source_file=resolved_source_file)

        matching_lots = sum(1 for row in lot_rows if row["match_base_ht"])
        lots_with_gap = len(lot_rows) - matching_lots
        missing_pdf_rows = sum(
            1 for row in article_rows if row["present_db"] and not row["present_pdf"]
        )
        missing_db_rows = sum(
            1 for row in article_rows if row["present_pdf"] and not row["present_db"]
        )

        return {
            "source_file": resolved_source_file,
            "pdf_exists": True,
            "available_sources": self.list_source_files(),
            "lots_imported": source_counts["lots_imported"],
            "articles_imported": source_counts["articles_imported"],
            "matching_lots": matching_lots,
            "lots_with_gap": lots_with_gap,
            "article_rows_compared": len(article_rows),
            "missing_in_pdf": missing_pdf_rows,
            "missing_in_db": missing_db_rows,
        }

    def get_lot_comparison(self, source_file: str | None = None) -> list[dict]:
        """
        Retourne la comparaison lot par lot.
        """
        resolved_source_file = self._resolve_source_file(source_file)
        session = SessionLocal()
        try:
            _, database_lot_totals = fetch_database_lot_totals(session)
        finally:
            session.close()

        pdf_lot_totals = self._load_source_lot_totals(resolved_source_file)
        return build_comparison_rows(pdf_lot_totals, database_lot_totals)

    def get_article_comparison(
        self,
        source_file: str | None = None,
        lot_code: str | None = None,
    ) -> list[dict]:
        """
        Retourne la comparaison article par article.
        """
        resolved_source_file = self._resolve_source_file(source_file)
        mismatching_lots = self._lot_total_mismatches(resolved_source_file)
        pdf_groups = self._load_source_article_groups(resolved_source_file)
        db_groups = self._load_db_article_groups()

        rows: list[dict] = []
        all_keys = set(pdf_groups) | set(db_groups)
        for row_lot_code, designation_key in sorted(all_keys):
            if row_lot_code not in mismatching_lots:
                continue
            if lot_code and row_lot_code != lot_code:
                continue

            pdf_row = pdf_groups.get((row_lot_code, designation_key), {})
            db_row = db_groups.get((row_lot_code, designation_key), {})

            total_ht_pdf = float(pdf_row.get("total_ht_pdf", 0))
            base_ht_db = float(db_row.get("base_ht_db", 0))
            ecart = base_ht_db - total_ht_pdf

            rows.append(
                {
                    "lot_code": row_lot_code,
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

    def promote_source_to_analytics(
        self,
        source_file: str | None = None,
        project_code: str | None = None,
        project_name: str | None = None,
        replace_existing: bool = False,
    ) -> dict[str, int | str]:
        """
        Promeut une source PDF importee en nouveau projet analytique SQLAlchemy.
        """
        resolved_source_file = self._resolve_source_file(source_file)
        initialize_all_sqlalchemy_tables()

        with sqlite3.connect(DATABASE_PATH) as connection:
            connection.row_factory = sqlite3.Row
            lot_rows = connection.execute(
                """
                SELECT lot_code, designation, total_ht
                FROM source_dqe_pdf_lots
                WHERE source_file = ?
                ORDER BY id
                """,
                (resolved_source_file,),
            ).fetchall()
            article_rows = connection.execute(
                """
                SELECT *
                FROM source_dqe_pdf_articles
                WHERE source_file = ?
                ORDER BY id
                """,
                (resolved_source_file,),
            ).fetchall()

        if not lot_rows or not article_rows:
            raise ValueError(f"Aucune source PDF importee pour {resolved_source_file}.")

        resolved_project_code = project_code or self._slugify(Path(resolved_source_file).stem)
        resolved_project_name = project_name or f"DQE PDF - {Path(resolved_source_file).stem}"

        session = SessionLocal()
        try:
            existing_project = (
                session.query(BuildProject)
                .filter(BuildProject.code == resolved_project_code)
                .one_or_none()
            )
            if existing_project and not replace_existing:
                raise ValueError(
                    f"Le projet analytique {resolved_project_code} existe deja. "
                    "Active replace_existing pour l'ecraser."
                )
            if existing_project and replace_existing:
                session.delete(existing_project)
                session.flush()

            project = BuildProject(
                code=resolved_project_code,
                name=resolved_project_name,
                description=f"Projet analytique promu depuis {resolved_source_file}.",
                devise="FCFA",
                statut="pdf_import",
            )
            session.add(project)
            session.flush()

            lot_map: dict[str, BuildLot] = {}
            for index, row in enumerate(lot_rows, start=1):
                lot_number_match = re.search(r"(\d+)", row["lot_code"])
                lot_number = int(lot_number_match.group(1)) if lot_number_match else index
                lot = BuildLot(
                    project_id=project.id,
                    code=f"L{lot_number:02d}",
                    name=row["lot_code"],
                    description=row["designation"],
                    display_order=lot_number,
                )
                session.add(lot)
                session.flush()
                lot_map[row["lot_code"]] = lot

            family_map: dict[tuple[str, str], BuildFamilyDimension] = {}
            for row in article_rows:
                section_code = (row["section_code"] or "SANS_SECTION").strip()
                family_key = (row["lot_code"], section_code)
                if family_key in family_map:
                    continue
                family = BuildFamilyDimension(
                    project_id=project.id,
                    code=f"{lot_map[row['lot_code']].code}_{self._slugify(section_code)}",
                    label=(row["section_label"] or section_code).strip(),
                    category=row["lot_code"],
                    importable=False,
                    risk_score=0.0,
                )
                session.add(family)
                session.flush()
                family_map[family_key] = family

            article_count = 0
            fact_count = 0
            for row in article_rows:
                lot = lot_map.get(row["lot_code"])
                if lot is None:
                    continue

                family = family_map.get((row["lot_code"], (row["section_code"] or "SANS_SECTION").strip()))
                article_code = f"PDF-{project.id}-{row['id']}"

                article = BuildArticle(
                    project_id=project.id,
                    lot_id=lot.id,
                    sous_lot_id=None,
                    famille_id=family.id if family else None,
                    code_bpu=article_code,
                    designation=row["designation"],
                    unite=row["unite"],
                    type_cout=row["section_label"],
                    pu_local_reference=float(row["pu_ht"] or 0),
                    pu_chine_reference=None,
                )
                session.add(article)
                session.flush()
                article_count += 1

                quantite = float(row["quantite"] or 1.0)
                pu_local = float(row["pu_ht"] or 0.0)
                total_local = float(row["total_ht"] or (quantite * pu_local))
                source_key = f"pdf:{resolved_source_file}:{row['id']}"

                fact_row = BuildFactMetre(
                    project_id=project.id,
                    article_id=article.id,
                    lot_id=lot.id,
                    sous_lot_id=None,
                    famille_id=family.id if family else None,
                    niveau_id=None,
                    batiment_id=None,
                    quantite=quantite,
                    pu_local=pu_local,
                    pu_chine=None,
                    total_local=total_local,
                    total_import=None,
                    economie=0.0,
                    taux_economie=0.0,
                    decision="LOCAL",
                    source_row_key=source_key,
                )
                session.add(fact_row)
                fact_count += 1

            session.commit()
            return {
                "source_file": resolved_source_file,
                "project_id": project.id,
                "project_code": project.code,
                "project_name": project.name,
                "lots": len(lot_map),
                "families": len(family_map),
                "articles": article_count,
                "fact_rows": fact_count,
            }
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
