"""
Service d'import intelligent DQE.

L'objectif est de prendre un fichier Excel ou CSV tres heterogene,
de detecter au mieux les colonnes utiles, puis de le transformer
vers le format standard du schema analytique.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.models.build_analytics import BuildFactMetre
from backend.schemas import DQEHierarchyItemPayload
from backend.services.dqe_hierarchy_service import DQEHierarchyService


class DQEImportService:
    """
    Service d'analyse, de preview et d'import de fichiers DQE.
    """

    COLUMN_ALIASES = {
        "batiment": [
            "batiment",
            "building",
            "bloc",
            "block",
            "bat",
        ],
        "niveau": [
            "niveau",
            "level",
            "floor",
            "etage",
            "r+",
            "rdc",
        ],
        "lot": [
            "lot",
            "poste",
            "trade",
        ],
        "sous_lot": [
            "sous_lot",
            "souslot",
            "sous lot",
            "sub_lot",
            "famille",
            "family",
            "section",
            "rubrique",
        ],
        "designation": [
            "designation",
            "design",
            "designation_article",
            "article",
            "libelle",
            "description",
            "ouvrage",
        ],
        "unite": [
            "unite",
            "unit",
            "u",
        ],
        "quantite": [
            "quantite",
            "qte",
            "qty",
            "quant",
        ],
        "pu_local": [
            "pu_local",
            "prix_local",
            "prix local",
            "pu",
            "prix_unitaire",
            "prix unitaire",
            "unit_price",
        ],
        "pu_chine": [
            "pu_chine",
            "prix_chine",
            "prix chine",
            "pu_import",
            "prix_import",
            "import_price",
            "china_price",
        ],
        "code_bpu": [
            "code_bpu",
            "code",
            "bpu",
            "reference",
            "ref",
        ],
    }

    REQUIRED_FIELDS = ["lot", "designation", "unite", "quantite", "pu_local"]

    def __init__(self) -> None:
        self.hierarchy_service = DQEHierarchyService()

    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(value))
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized.lower()).strip("_")
        return normalized

    def _load_raw_dataframe(
        self,
        file_path: str,
        sheet_name: str | None = None,
    ) -> tuple[pd.DataFrame, str | None]:
        """
        Charge un fichier CSV ou Excel.
        """
        path = Path(file_path)
        if not path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fichier introuvable : {file_path}",
            )

        suffix = path.suffix.lower()
        if suffix == ".csv":
            dataframe = pd.read_csv(path)
            return dataframe, None

        if suffix in {".xlsx", ".xls"}:
            excel_file = pd.ExcelFile(path)
            selected_sheet = sheet_name or excel_file.sheet_names[0]
            dataframe = pd.read_excel(path, sheet_name=selected_sheet)
            return dataframe, selected_sheet

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format non supporte. Utiliser un fichier CSV ou Excel.",
        )

    def _detect_mapping(self, columns: list[str]) -> dict[str, str | None]:
        """
        Detecte les colonnes les plus probables.
        """
        normalized_columns = {
            column: self._normalize_text(column)
            for column in columns
        }
        mapping: dict[str, str | None] = {field: None for field in self.COLUMN_ALIASES}

        for field_name, aliases in self.COLUMN_ALIASES.items():
            exact_match = next(
                (
                    original_column
                    for original_column, normalized_column in normalized_columns.items()
                    if normalized_column in {self._normalize_text(alias) for alias in aliases}
                ),
                None,
            )
            if exact_match is not None:
                mapping[field_name] = exact_match
                continue

            partial_match = next(
                (
                    original_column
                    for original_column, normalized_column in normalized_columns.items()
                    if any(self._normalize_text(alias) in normalized_column for alias in aliases)
                ),
                None,
            )
            mapping[field_name] = partial_match

        return mapping

    def _merge_mapping(
        self,
        detected_mapping: dict[str, str | None],
        custom_mapping: dict[str, str | None] | None,
        available_columns: list[str],
    ) -> dict[str, str | None]:
        """
        Applique un override utilisateur sur le mapping detecte.
        """
        if not custom_mapping:
            return detected_mapping

        merged_mapping = detected_mapping.copy()
        allowed_columns = set(available_columns)

        for field_name, column_name in custom_mapping.items():
            if field_name not in merged_mapping:
                continue
            if column_name in (None, "", "__NONE__"):
                merged_mapping[field_name] = None
                continue
            if column_name in allowed_columns:
                merged_mapping[field_name] = column_name

        return merged_mapping

    @staticmethod
    def _detect_level_from_text(value: str | None) -> str | None:
        """
        Essaie de reconnaitre un niveau metier dans un texte libre.
        """
        if not value:
            return None

        text = value.upper().strip()
        patterns = [
            (r"\bRDC\b", "RDC"),
            (r"\bR\+?(\d+)\b", None),
            (r"\bETAGE\s*(\d+)\b", None),
            (r"\bDUPLEX\s*(\d+)\b", None),
            (r"\bTERRASSE\b", "TERRASSE"),
            (r"\bGLOBAL\b", "GLOBAL"),
            (r"\bSOUS[\s_-]?SOL\b", "SOUS-SOL"),
        ]

        for pattern, fixed_value in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            if fixed_value is not None:
                return fixed_value
            captured_value = match.group(1)
            if "DUPLEX" in text:
                return f"DUPLEX {captured_value}"
            if "ETAGE" in text:
                return f"ETAGE {captured_value}"
            return f"R+{captured_value}"
        return None

    @staticmethod
    def _detect_building_from_text(value: str | None) -> str | None:
        """
        Essaie de reconnaitre un batiment dans un texte libre.
        """
        if not value:
            return None

        text = value.upper().strip()
        if "ANNEXE" in text:
            return "Annexe"
        if "PRINCIPAL" in text:
            return "Principal"

        match = re.search(r"BAT(?:IMENT)?\s*([A-Z0-9]+)", text)
        if match:
            return f"Batiment {match.group(1)}"
        return None

    @staticmethod
    def _safe_string(value: object, default_value: str) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default_value
        text = str(value).strip()
        return text or default_value

    @staticmethod
    def _safe_float(value: object, default_value: float = 0.0) -> float:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default_value
        if isinstance(value, str):
            normalized = value.replace("\xa0", "").replace(" ", "").replace(",", ".")
            return float(normalized) if normalized else default_value
        return float(value)

    def _build_standardized_rows(
        self,
        dataframe: pd.DataFrame,
        mapping: dict[str, str | None],
        source_prefix: str,
    ) -> list[dict]:
        """
        Construit les lignes standardisees a partir du DataFrame source.
        """
        standardized_rows: list[dict] = []

        for row_index, row in dataframe.fillna("").iterrows():
            designation = self._safe_string(
                row.get(mapping["designation"]) if mapping["designation"] else None,
                "",
            )
            if not designation:
                continue

            lot_value = self._safe_string(
                row.get(mapping["lot"]) if mapping["lot"] else None,
                "LOT GLOBAL",
            )
            sous_lot_value = self._safe_string(
                row.get(mapping["sous_lot"]) if mapping["sous_lot"] else None,
                "SOUS-LOT GLOBAL",
            )
            batiment_value = self._safe_string(
                row.get(mapping["batiment"]) if mapping["batiment"] else None,
                "",
            )
            niveau_value = self._safe_string(
                row.get(mapping["niveau"]) if mapping["niveau"] else None,
                "",
            )

            if not batiment_value:
                batiment_value = (
                    self._detect_building_from_text(designation)
                    or self._detect_building_from_text(lot_value)
                    or "Batiment Global"
                )

            if not niveau_value:
                niveau_value = (
                    self._detect_level_from_text(designation)
                    or self._detect_level_from_text(sous_lot_value)
                    or self._detect_level_from_text(lot_value)
                    or "GLOBAL"
                )

            quantite_value = self._safe_float(
                row.get(mapping["quantite"]) if mapping["quantite"] else None,
                0.0,
            )
            pu_local_value = self._safe_float(
                row.get(mapping["pu_local"]) if mapping["pu_local"] else None,
                0.0,
            )
            pu_chine_value = self._safe_float(
                row.get(mapping["pu_chine"]) if mapping["pu_chine"] else None,
                0.0,
            )

            if quantite_value <= 0:
                continue

            standardized_rows.append(
                {
                    "batiment": batiment_value,
                    "niveau": niveau_value,
                    "lot": lot_value,
                    "sous_lot": sous_lot_value,
                    "designation": designation,
                    "unite": self._safe_string(
                        row.get(mapping["unite"]) if mapping["unite"] else None,
                        "U",
                    ),
                    "quantite": quantite_value,
                    "pu_local": pu_local_value,
                    "pu_chine": pu_chine_value if pu_chine_value > 0 else None,
                    "code_bpu": self._safe_string(
                        row.get(mapping["code_bpu"]) if mapping["code_bpu"] else None,
                        "",
                    )
                    or None,
                    "famille": sous_lot_value,
                    "source_row_key": f"{source_prefix}_{row_index + 1}",
                }
            )

        return standardized_rows

    def preview_import(
        self,
        file_path: str,
        sheet_name: str | None = None,
        custom_mapping: dict[str, str | None] | None = None,
    ) -> dict:
        """
        Analyse un fichier et retourne un apercu standardise.
        """
        dataframe, resolved_sheet_name = self._load_raw_dataframe(file_path, sheet_name)
        detected_mapping = self._detect_mapping(dataframe.columns.tolist())
        mapping = self._merge_mapping(
            detected_mapping,
            custom_mapping,
            dataframe.columns.tolist(),
        )
        source_prefix = self._normalize_text(Path(file_path).stem or "import")
        standardized_rows = self._build_standardized_rows(dataframe, mapping, source_prefix)

        missing_required = [
            field_name
            for field_name in self.REQUIRED_FIELDS
            if mapping.get(field_name) is None
        ]
        defaults_applied = [
            field_name
            for field_name in ["batiment", "niveau", "sous_lot", "pu_chine", "code_bpu"]
            if mapping.get(field_name) is None
        ]

        return {
            "file_path": file_path,
            "sheet_name": resolved_sheet_name,
            "row_count_source": int(len(dataframe.index)),
            "row_count_standardized": int(len(standardized_rows)),
            "source_columns": dataframe.columns.tolist(),
            "detected_mapping_raw": detected_mapping,
            "detected_mapping": mapping,
            "missing_required_fields": missing_required,
            "defaults_applied": defaults_applied,
            "preview_rows": standardized_rows[:25],
        }

    def apply_import(
        self,
        db_session: Session,
        project_id: int,
        file_path: str,
        sheet_name: str | None = None,
        replace_existing: bool = False,
        custom_mapping: dict[str, str | None] | None = None,
    ) -> dict:
        """
        Importe les lignes standardisees dans le schema analytique.
        """
        dataframe, resolved_sheet_name = self._load_raw_dataframe(file_path, sheet_name)
        detected_mapping = self._detect_mapping(dataframe.columns.tolist())
        mapping = self._merge_mapping(
            detected_mapping,
            custom_mapping,
            dataframe.columns.tolist(),
        )
        source_prefix = self._normalize_text(Path(file_path).stem or "import")
        standardized_rows = self._build_standardized_rows(dataframe, mapping, source_prefix)

        if replace_existing:
            db_session.query(BuildFactMetre).filter(
                BuildFactMetre.project_id == project_id,
                BuildFactMetre.source_row_key.like(f"{source_prefix}_%"),
            ).delete(synchronize_session=False)
            db_session.commit()

        imported_count = 0
        for row in standardized_rows:
            payload = DQEHierarchyItemPayload(**row)
            self.hierarchy_service.save_hierarchy_item(db_session, project_id, payload)
            imported_count += 1

        return {
            "project_id": project_id,
            "file_path": file_path,
            "sheet_name": resolved_sheet_name,
            "imported_rows": imported_count,
            "replace_existing": replace_existing,
            "mapping_used": mapping,
        }
