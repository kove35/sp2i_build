"""
Services de calcul pour les dashboards SP2I_Build.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import unicodedata
from dataclasses import asdict, dataclass

import pandas as pd
import numpy as np

from backend.config import APP_DATABASE_PATH
from backend.schemas import DashboardFilters
from backend.db.session import SessionLocal
from backend.services.build_analytics_service import BuildAnalyticsService


logger = logging.getLogger(__name__)


@dataclass
class FilterOption:
    """
    Petit objet pour les listes deroulantes du frontend.
    """

    value: str | int
    label: str


class DashboardService:
    """
    Service principal pour fabriquer les donnees des 3 dashboards.
    """

    def __init__(self) -> None:
        self.analytics_service = BuildAnalyticsService()

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        if not value:
            return ""
        normalized = unicodedata.normalize("NFKD", str(value))
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        return " ".join(normalized.upper().split())

    def _extract_pdf_level(self, *values: str | None) -> str | None:
        combined = " ".join(self._normalize_text(value) for value in values if value)
        if not combined:
            return None

        if "RDC" in combined or "REZ DE CHAUSSEE" in combined:
            return "RDC"

        duplex_match = re.search(r"DUPLEX\s+(\d+)", combined)
        if duplex_match:
            return f"DUPLEX {duplex_match.group(1)}"

        etage_match = re.search(r"ETAGE\s+(\d+)", combined)
        if etage_match:
            return f"ETAGE {etage_match.group(1)}"

        r_match = re.search(r"R\+(\d+)", combined)
        if r_match:
            return f"R+{r_match.group(1)}"

        if "TERRASSE" in combined:
            return "TERRASSE"
        if "GLOBAL" in combined:
            return "GLOBAL"

        return None

    def _extract_pdf_building(self, *values: str | None) -> str | None:
        combined = " ".join(self._normalize_text(value) for value in values if value)
        if not combined:
            return None

        if "BATIMENT ANNEXE" in combined or "ANNEXE" in combined:
            return "Annexe"
        if "BATIMENT PRINCIPAL" in combined or "PRINCIPAL" in combined:
            return "Principal"
        return None

    def get_default_dashboard_project(self) -> dict | None:
        """
        Retourne le projet analytique actuellement utilise par les dashboards.
        """
        db_session = SessionLocal()
        try:
            project = self._resolve_dashboard_project(db_session)
            if project is None:
                return None
            return {
                "id": project.id,
                "code": project.code,
                "name": project.name,
                "description": project.description,
                "devise": project.devise,
                "statut": project.statut,
            }
        finally:
            db_session.close()

    def set_default_dashboard_project(self, project_id: int) -> dict:
        """
        Definit le projet analytique par defaut pour les dashboards historiques.
        """
        db_session = SessionLocal()
        try:
            project = self.analytics_service.get_project(db_session, project_id)
        finally:
            db_session.close()

        with sqlite3.connect(APP_DATABASE_PATH) as connection:
            connection.execute(
                """
                INSERT INTO app_settings(setting_key, setting_value)
                VALUES('default_dashboard_project_id', ?)
                ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value
                """,
                (str(project_id),),
            )
            connection.commit()

        return {
            "project_id": project.id,
            "project_code": project.code,
            "project_name": project.name,
            "status": "updated",
        }

    def get_filter_options(self) -> dict[str, list[dict[str, str | int]]]:
        """
        Retourne les valeurs disponibles pour les filtres.
        """
        dataframe = self._load_dashboard_dataframe(DashboardFilters())

        lot_options = (
            dataframe[["lot_number", "lot_label"]]
            .dropna()
            .drop_duplicates()
            .sort_values("lot_number")
        )
        family_options = (
            dataframe[["fam_article_id", "famille_label"]]
            .dropna()
            .drop_duplicates()
            .sort_values("famille_label")
        )
        building_options = (
            dataframe[["batiment_id", "batiment_label"]]
            .dropna()
            .drop_duplicates()
            .sort_values("batiment_label")
        )
        level_options = (
            dataframe[["niveau_id", "niveau_label"]]
            .dropna()
            .drop_duplicates()
            .sort_values("niveau_label")
        )

        return {
            "lots": [
                asdict(FilterOption(value=int(row["lot_number"]), label=row["lot_label"]))
                for _, row in lot_options.iterrows()
            ],
            "familles": [
                asdict(FilterOption(value=row["fam_article_id"], label=row["famille_label"]))
                for _, row in family_options.iterrows()
            ],
            "batiments": [
                asdict(FilterOption(value=row["batiment_id"], label=row["batiment_label"]))
                for _, row in building_options.iterrows()
            ],
            "niveaux": [
                asdict(FilterOption(value=row["niveau_id"], label=row["niveau_label"]))
                for _, row in level_options.iterrows()
            ],
        }

    def get_direction_dataset(self) -> dict:
        """
        Retourne les lignes detaillees du dashboard Direction.
        Le frontend peut ensuite appliquer ses propres filtres interactifs.
        """
        dataframe = self._load_direction_kpi_dataframe(DashboardFilters())
        clean_dataframe = dataframe.copy()
        clean_dataframe = clean_dataframe.replace([np.inf, -np.inf], None)
        clean_dataframe = clean_dataframe.where(pd.notna(clean_dataframe), None)
        return {"items": json.loads(clean_dataframe.to_json(orient="records"))}

    def get_direction_kpi_dataset(self) -> dict:
        """
        Retourne le dataset detaille du dashboard Direction ancre sur la source DQE.
        """
        dataframe = self._load_direction_kpi_dataframe(DashboardFilters())
        clean_dataframe = dataframe.copy()
        clean_dataframe = clean_dataframe.replace([np.inf, -np.inf], None)
        clean_dataframe = clean_dataframe.where(pd.notna(clean_dataframe), None)
        return {"items": json.loads(clean_dataframe.to_json(orient="records"))}

    def get_direction_dashboard(self, filters: DashboardFilters) -> dict:
        dataframe = self._load_direction_kpi_dataframe(filters)

        return {
            "dashboard": "direction",
            "filters": self._filters_to_dict(filters),
            "kpis": self._build_common_kpis(dataframe),
            "charts": {
                "repartition_local_import": self._group_sum(
                    dataframe,
                    group_column="decision_label",
                    value_column="montant_local",
                    label_column="decision",
                    value_label="value",
                ),
                "capex_brut_par_famille": self._group_sum(
                    dataframe,
                    group_column="famille_label",
                    value_column="montant_local",
                    label_column="famille",
                    value_label="capex",
                ),
                "capex_par_lot": self._group_sum(
                    dataframe,
                    group_column="lot_label",
                    value_column="montant_local",
                    label_column="lot",
                    value_label="capex",
                ),
                "top_articles_source": (
                    dataframe
                    .groupby(["code_bpu", "designation"], as_index=False)
                    .agg(
                        capex_brut=("montant_local", "sum"),
                        capex_optimise=("capex_optimise_line", "sum"),
                        economie=("economie_line", "sum"),
                    )
                    .sort_values("capex_brut", ascending=False)
                    .head(10)
                    .to_dict(orient="records")
                ),
            },
        }

    def get_chantier_dashboard(self, filters: DashboardFilters) -> dict:
        dataframe = self._load_dashboard_dataframe(filters)
        ventilated_dataframe = self._build_chantier_ventilated_dataframe(dataframe)

        return {
            "dashboard": "chantier",
            "filters": self._filters_to_dict(filters),
            "kpis": self._build_common_kpis(dataframe),
            "audit": {
                "global_rows_before_ventilation": int((dataframe["niveau_label"] == "GLOBAL").sum())
                if not dataframe.empty
                else 0,
                "global_rows_after_ventilation": int((ventilated_dataframe["niveau_label"] == "GLOBAL").sum())
                if not ventilated_dataframe.empty
                else 0,
                "ventilation_mode": "proportionnelle_par_lot_et_batiment",
            },
            "charts": {
                "cout_par_lot": self._group_sum(
                    dataframe,
                    group_column="lot_label",
                    value_column="capex_optimise_line",
                    label_column="lot",
                    value_label="capex",
                ),
                "cout_par_batiment": self._group_sum(
                    dataframe,
                    group_column="batiment_label",
                    value_column="capex_optimise_line",
                    label_column="batiment",
                    value_label="capex",
                ),
                "cout_par_niveau": self._group_sum(
                    ventilated_dataframe,
                    group_column="niveau_label",
                    value_column="capex_optimise_line",
                    label_column="niveau",
                    value_label="capex",
                ),
                "repartition_lot_niveau": (
                    ventilated_dataframe.groupby(["lot_label", "niveau_label"], as_index=False)
                    .agg(capex=("capex_optimise_line", "sum"))
                    .sort_values(["lot_label", "niveau_label"])
                    .to_dict(orient="records")
                ),
            },
        }

    def get_import_dashboard(self, filters: DashboardFilters) -> dict:
        dataframe = self._load_dashboard_dataframe(filters)
        import_ventilated_dataframe = self._build_import_ventilated_dataframe(dataframe)

        capex_fob = float(dataframe["capex_fob_line"].sum())
        capex_import_ttc = float(dataframe["capex_import_ttc_line"].sum())
        capex_importable = float(dataframe["capex_importable_line"].sum())
        articles_sans_prix_chine = int(dataframe["missing_china_price_flag"].sum())
        capex_couvert = float(dataframe["capex_couvert_line"].sum())
        taux_couverture = capex_couvert / capex_importable if capex_importable else 0.0

        matrice_audit = (
            dataframe.groupby("famille_label", as_index=False)
            .agg(
                capex_importable=("capex_importable_line", "sum"),
                capex_import_ttc=("capex_import_ttc_line", "sum"),
                couverture=("capex_couvert_line", "sum"),
                articles_sans_prix=("missing_china_price_flag", "sum"),
            )
            .assign(
                taux_couverture=lambda frame: frame.apply(
                    lambda row: (
                        row["couverture"] / row["capex_importable"]
                        if row["capex_importable"]
                        else 0.0
                    ),
                    axis=1,
                )
            )
            .sort_values("capex_importable", ascending=False)
            .to_dict(orient="records")
        )

        capex_sans_prix_chine = (
            dataframe[dataframe["missing_china_price_flag"] == 1]
            .groupby("famille_label", as_index=False)
            .agg(capex=("montant_local", "sum"))
            .sort_values("capex", ascending=False)
            .to_dict(orient="records")
        )

        taux_import_par_famille = (
            dataframe.groupby("famille_label", as_index=False)
            .agg(
                capex_importe=("capex_import_decide_line", "sum"),
                capex_importable=("capex_importable_line", "sum"),
            )
            .assign(
                taux_import=lambda frame: frame.apply(
                    lambda row: (
                        row["capex_importe"] / row["capex_importable"]
                        if row["capex_importable"]
                        else 0.0
                    ),
                    axis=1,
                )
            )
            .sort_values("taux_import", ascending=False)
            .to_dict(orient="records")
        )

        return {
            "dashboard": "import",
            "filters": self._filters_to_dict(filters),
            "kpis": {
                "capex_fob": capex_fob,
                "capex_import_ttc": capex_import_ttc,
                "capex_importable": capex_importable,
                "articles_sans_prix_chine": articles_sans_prix_chine,
                "taux_couverture_sourcing": taux_couverture,
            },
            "audit": {
                "importable_rows": int(dataframe["importable"].sum()) if not dataframe.empty else 0,
                "global_importable_rows_before_ventilation": int(
                    ((dataframe["importable"] == 1) & (dataframe["niveau_label"] == "GLOBAL")).sum()
                )
                if not dataframe.empty
                else 0,
                "global_importable_rows_after_ventilation": int(
                    ((import_ventilated_dataframe["importable"] == 1) & (import_ventilated_dataframe["niveau_label"] == "GLOBAL")).sum()
                )
                if not import_ventilated_dataframe.empty
                else 0,
                "ventilation_mode": "proportionnelle_par_lot_et_batiment_sur_lignes_importables",
            },
            "charts": {
                "matrice_audit_sourcing": matrice_audit,
                "capex_sans_prix_chine": capex_sans_prix_chine,
                "taux_import_par_famille": taux_import_par_famille,
                "structure_decision": self._group_sum(
                    dataframe,
                    group_column="decision_label",
                    value_column="capex_optimise_line",
                    label_column="decision",
                    value_label="value",
                ),
                "importable_par_batiment": self._group_sum(
                    import_ventilated_dataframe,
                    group_column="batiment_label",
                    value_column="capex_importable_line",
                    label_column="batiment",
                    value_label="capex_importable",
                ),
                "importable_par_niveau": self._group_sum(
                    import_ventilated_dataframe,
                    group_column="niveau_label",
                    value_column="capex_importable_line",
                    label_column="niveau",
                    value_label="capex_importable",
                ),
            },
        }

    def _load_dashboard_dataframe(self, filters: DashboardFilters) -> pd.DataFrame:
        db_session = SessionLocal()
        try:
            project = self._resolve_dashboard_project(db_session)
            if project is None:
                logger.warning("Aucun projet analytique resolu pour les dashboards.")
                return pd.DataFrame()
            dataframe = self.analytics_service.build_project_dataframe(db_session, project.id)
        finally:
            db_session.close()

        if dataframe.empty:
            return dataframe

        dataframe = dataframe.copy()
        dataframe["projet_id"] = project.code
        dataframe["designation"] = dataframe["designation"].fillna("Article sans designation")
        dataframe["qte"] = pd.to_numeric(dataframe["quantity"], errors="coerce").fillna(0.0)
        dataframe["montant_local"] = pd.to_numeric(dataframe["montant_local"], errors="coerce").fillna(0.0)
        dataframe["montant_import"] = pd.to_numeric(dataframe["montant_import"], errors="coerce")
        dataframe["pu_chine_fob_reference"] = pd.to_numeric(dataframe["pu_chine"], errors="coerce").fillna(0.0)
        dataframe["pu_import_net"] = pd.to_numeric(dataframe["pu_chine"], errors="coerce").fillna(0.0)
        dataframe["importable"] = dataframe["importable"].fillna(False).astype(int)
        dataframe["statut_prix"] = np.where(
            dataframe["pu_chine_fob_reference"] > 0,
            "PRIX_OK",
            "A_COMPLETER",
        )
        dataframe["decision_label"] = dataframe["decision"].fillna("LOCAL")
        dataframe["fam_article_id"] = dataframe["family_code"]
        dataframe["famille_label"] = dataframe["family_article"].fillna("Famille non renseignee")
        dataframe["batiment_id"] = dataframe["batiment_code"]
        dataframe["batiment_label"] = dataframe["batiment"].fillna("Batiment non renseigne")
        dataframe["niveau_id"] = dataframe["niveau_code"]
        dataframe["niveau_label"] = dataframe["niveau"].fillna("Niveau non renseigne")
        dataframe["lot_id"] = dataframe["lot_code"]
        dataframe["lot_label"] = dataframe["lot_label"].fillna("Lot non renseigne")
        dataframe["lot_number"] = (
            dataframe["lot_code"]
            .astype(str)
            .str.extract(r"(\d+)")
            .fillna(0)
            .astype(int)
        )

        dataframe["capex_optimise_line"] = np.where(
            (dataframe["decision_label"] == "IMPORT") & dataframe["montant_import"].notna(),
            dataframe["montant_import"],
            dataframe["montant_local"],
        )
        dataframe["economie_line"] = np.where(
            (dataframe["decision_label"] == "IMPORT") & dataframe["montant_import"].notna(),
            dataframe["montant_local"] - dataframe["montant_import"],
            0.0,
        )
        dataframe["capex_fob_line"] = np.where(
            (dataframe["importable"] == 1) & (dataframe["pu_chine_fob_reference"] > 0),
            dataframe["qte"] * dataframe["pu_chine_fob_reference"],
            0.0,
        )
        dataframe["capex_import_ttc_line"] = np.where(
            (dataframe["importable"] == 1) & dataframe["montant_import"].fillna(0).gt(0),
            dataframe["montant_import"].fillna(0.0),
            0.0,
        )
        dataframe["capex_importable_line"] = np.where(
            dataframe["importable"] == 1,
            dataframe["montant_local"],
            0.0,
        )
        dataframe["missing_china_price_flag"] = np.where(
            (dataframe["importable"] == 1) & (dataframe["pu_chine_fob_reference"] <= 0),
            1,
            0,
        )
        dataframe["capex_couvert_line"] = np.where(
            (dataframe["importable"] == 1) & (dataframe["pu_chine_fob_reference"] > 0),
            dataframe["montant_local"],
            0.0,
        )
        dataframe["capex_import_decide_line"] = np.where(
            dataframe["decision_label"] == "IMPORT",
            dataframe["montant_local"],
            0.0,
        )

        return self._apply_filters_to_dataframe(dataframe, filters)

    def _resolve_dashboard_project(self, db_session) -> object | None:
        """
        Choisit le projet analytique par defaut pour les dashboards.
        """
        from backend.models.build_analytics import BuildProject

        default_project_id: int | None = None
        if APP_DATABASE_PATH.exists():
            with sqlite3.connect(APP_DATABASE_PATH) as connection:
                row = connection.execute(
                    """
                    SELECT setting_value
                    FROM app_settings
                    WHERE setting_key = 'default_dashboard_project_id'
                    LIMIT 1
                    """
                ).fetchone()
                if row and row[0]:
                    try:
                        default_project_id = int(row[0])
                    except (TypeError, ValueError):
                        default_project_id = None

        if default_project_id is not None:
            project = (
                db_session.query(BuildProject)
                .filter(BuildProject.id == default_project_id)
                .one_or_none()
            )
            if project is not None:
                return project

        logger.info(
            "Aucun default_dashboard_project_id exploitable dans %s, fallback sur le premier projet.",
            APP_DATABASE_PATH,
        )
        return (
            db_session.query(BuildProject)
            .order_by(BuildProject.id.asc())
            .first()
        )

    def _load_direction_kpi_dataframe(
        self,
        filters: DashboardFilters | None = None,
    ) -> pd.DataFrame:
        """
        Construit un dataset KPI dont la base CAPEX brut vient du PDF source.

        Logique choisie :
        - le montant local de reference vient de `source_dqe_pdf_articles.total_ht`
        - le ratio d'optimisation vient du detail analytique actuel, au niveau LOT
        - le KPI final reste donc ancre sur le PDF, mais garde la logique metier
          IMPORT / LOCAL du projet analytique
        """
        filters = filters or DashboardFilters()
        analytics_dataframe = self._load_dashboard_dataframe(DashboardFilters())
        if analytics_dataframe.empty:
            return analytics_dataframe

        source_file = self._resolve_direction_pdf_source_file()
        if source_file is None:
            # Fallback de securite : si aucun PDF n'est importe, on retombe sur
            # la source analytique existante.
            logger.info(
                "Aucune source PDF direction detectee dans %s, fallback sur les donnees analytiques.",
                APP_DATABASE_PATH,
            )
            return self._apply_filters_to_dataframe(analytics_dataframe, filters)

        with sqlite3.connect(APP_DATABASE_PATH) as connection:
            pdf_dataframe = pd.read_sql_query(
                """
                SELECT
                    source_file,
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
                    total_ht
                FROM source_dqe_pdf_articles
                WHERE source_file = ?
                  AND total_ht IS NOT NULL
                """,
                connection,
                params=(source_file,),
            )

        if pdf_dataframe.empty:
            return self._apply_filters_to_dataframe(analytics_dataframe, filters)

        lot_metadata = (
            analytics_dataframe.assign(
                lot_pdf_code=lambda frame: "LOT " + frame["lot_number"].astype(str)
            )[["lot_pdf_code", "lot_label", "lot_number"]]
            .dropna()
            .drop_duplicates()
        )

        family_by_lot = (
            analytics_dataframe.assign(
                lot_pdf_code=lambda frame: "LOT " + frame["lot_number"].astype(str)
            )
            .groupby(["lot_pdf_code", "famille_label"], as_index=False)
            .size()
            .sort_values(["lot_pdf_code", "size"], ascending=[True, False])
            .drop_duplicates(subset=["lot_pdf_code"])
            [["lot_pdf_code", "famille_label"]]
        )

        optimization_ratio_by_lot = (
            analytics_dataframe.assign(
                lot_pdf_code=lambda frame: "LOT " + frame["lot_number"].astype(str)
            )
            .groupby("lot_pdf_code", as_index=False)
            .agg(
                montant_local=("montant_local", "sum"),
                capex_optimise=("capex_optimise_line", "sum"),
            )
        )
        optimization_ratio_by_lot["optimization_ratio"] = optimization_ratio_by_lot.apply(
            lambda row: (
                row["capex_optimise"] / row["montant_local"] if row["montant_local"] else 1.0
            ),
            axis=1,
        )

        pdf_dataframe = pdf_dataframe.merge(
            lot_metadata,
            left_on="lot_code",
            right_on="lot_pdf_code",
            how="left",
            suffixes=("_pdf", "_analytics"),
        )
        pdf_dataframe = pdf_dataframe.merge(
            family_by_lot,
            left_on="lot_code",
            right_on="lot_pdf_code",
            how="left",
        )
        pdf_dataframe = pdf_dataframe.merge(
            optimization_ratio_by_lot[["lot_pdf_code", "optimization_ratio"]],
            left_on="lot_code",
            right_on="lot_pdf_code",
            how="left",
        )

        pdf_dataframe["lot_number"] = (
            pdf_dataframe["lot_code"]
            .astype(str)
            .str.extract(r"(\d+)")
            .fillna(0)
            .astype(int)
        )
        if "lot_label_analytics" in pdf_dataframe.columns:
            pdf_dataframe["lot_label"] = pdf_dataframe["lot_label_analytics"]
            if "lot_label_pdf" in pdf_dataframe.columns:
                pdf_dataframe["lot_label"] = pdf_dataframe["lot_label"].fillna(
                    pdf_dataframe["lot_label_pdf"]
                )
        elif "lot_label_pdf" in pdf_dataframe.columns:
            pdf_dataframe["lot_label"] = pdf_dataframe["lot_label_pdf"]
        else:
            pdf_dataframe["lot_label"] = pdf_dataframe["lot_code"]

        pdf_dataframe["lot_label"] = pdf_dataframe["lot_label"].fillna(pdf_dataframe["lot_code"])
        pdf_dataframe["famille_label"] = pdf_dataframe["famille_label"].fillna(
            pdf_dataframe["section_label"].fillna("Famille PDF")
        )
        pdf_dataframe["montant_local"] = pd.to_numeric(
            pdf_dataframe["total_ht"], errors="coerce"
        ).fillna(0.0)
        pdf_dataframe["optimization_ratio"] = pd.to_numeric(
            pdf_dataframe["optimization_ratio"], errors="coerce"
        ).fillna(1.0)
        pdf_dataframe["capex_optimise_line"] = (
            pdf_dataframe["montant_local"] * pdf_dataframe["optimization_ratio"]
        )
        pdf_dataframe["economie_line"] = (
            pdf_dataframe["montant_local"] - pdf_dataframe["capex_optimise_line"]
        )
        pdf_dataframe["decision_label"] = np.where(
            pdf_dataframe["optimization_ratio"] < 0.9999,
            "IMPORT",
            "LOCAL",
        )
        pdf_dataframe["designation"] = pdf_dataframe["designation"].fillna("Article PDF")
        pdf_dataframe["fam_article_id"] = pdf_dataframe["section_code"]
        pdf_dataframe["code_bpu"] = pdf_dataframe["item_number"].fillna(pdf_dataframe["designation"])
        pdf_dataframe["niveau_label"] = pdf_dataframe.apply(
            lambda row: self._extract_pdf_level(
                row.get("section_label"),
                row.get("designation"),
                row.get("lot_label_pdf"),
                row.get("lot_label_analytics"),
            ),
            axis=1,
        )
        pdf_dataframe["batiment_label"] = pdf_dataframe.apply(
            lambda row: self._extract_pdf_building(
                row.get("section_label"),
                row.get("designation"),
                row.get("lot_label_pdf"),
                row.get("lot_label_analytics"),
            ),
            axis=1,
        )
        pdf_dataframe["niveau_label"] = pdf_dataframe["niveau_label"].fillna("GLOBAL")
        pdf_dataframe["batiment_label"] = pdf_dataframe.apply(
            lambda row: (
                row["batiment_label"]
                if pd.notna(row["batiment_label"]) and row["batiment_label"]
                else ("Principal" if row["niveau_label"] != "GLOBAL" else "Global")
            ),
            axis=1,
        )
        pdf_dataframe["niveau_id"] = (
            "NIV_"
            + pdf_dataframe["niveau_label"]
            .astype(str)
            .str.upper()
            .str.replace(r"[^A-Z0-9]+", "_", regex=True)
            .str.strip("_")
        )
        pdf_dataframe["batiment_id"] = (
            "BAT_"
            + pdf_dataframe["batiment_label"]
            .astype(str)
            .str.upper()
            .str.replace(r"[^A-Z0-9]+", "_", regex=True)
            .str.strip("_")
        )

        if filters.lot_id is not None:
            pdf_dataframe = pdf_dataframe[
                pdf_dataframe["lot_number"] == int(filters.lot_id)
            ]

        if filters.fam_article_id:
            matching_family_labels = (
                analytics_dataframe.loc[
                    analytics_dataframe["fam_article_id"] == filters.fam_article_id,
                    "famille_label",
                ]
                .dropna()
                .unique()
                .tolist()
            )
            if matching_family_labels:
                pdf_dataframe = pdf_dataframe[
                    pdf_dataframe["famille_label"].isin(matching_family_labels)
                ]

        if filters.batiment_id:
            pdf_dataframe = pdf_dataframe[
                pdf_dataframe["batiment_id"] == filters.batiment_id
            ]

        if filters.niveau_id:
            pdf_dataframe = pdf_dataframe[
                pdf_dataframe["niveau_id"] == filters.niveau_id
            ]

        return pdf_dataframe

    def _resolve_direction_pdf_source_file(self) -> str | None:
        """
        Choisit la source PDF de reference pour les KPI Direction.
        """
        if not APP_DATABASE_PATH.exists():
            return None

        with sqlite3.connect(APP_DATABASE_PATH) as connection:
            preferred = connection.execute(
                """
                SELECT source_file
                FROM source_dqe_pdf_articles
                WHERE source_file = 'DQE_MEDICAL CENTER_13-08-2025.xlsx.pdf'
                LIMIT 1
                """
            ).fetchone()
            if preferred:
                return str(preferred[0])

            fallback = connection.execute(
                """
                SELECT source_file
                FROM source_dqe_pdf_articles
                GROUP BY source_file
                ORDER BY source_file DESC
                LIMIT 1
                """
            ).fetchone()
            if fallback:
                return str(fallback[0])

        return None

    def _build_common_kpis(self, dataframe: pd.DataFrame) -> dict[str, float]:
        capex_brut = float(dataframe["montant_local"].sum())
        capex_optimise = float(dataframe["capex_optimise_line"].sum())
        economie = capex_brut - capex_optimise
        taux_optimisation = economie / capex_brut if capex_brut else 0.0

        return {
            "capex_brut": capex_brut,
            "capex_optimise": capex_optimise,
            "economie": economie,
            "taux_optimisation": taux_optimisation,
        }

    def _build_chantier_ventilated_dataframe(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """
        Ventile analytiquement les lignes `GLOBAL` sur les niveaux détaillés.

        Règle :
        - on répartit d'abord par couple (bâtiment, lot) selon le poids CAPEX des
          niveaux non-GLOBAL déjà présents ;
        - s'il n'existe pas de détail pour ce lot, on retombe sur le poids des
          niveaux du bâtiment ;
        - en dernier recours, la ligne reste en GLOBAL.
        """
        if dataframe.empty or "niveau_label" not in dataframe.columns:
            return dataframe.copy()

        working_dataframe = dataframe.copy()
        non_global = working_dataframe[working_dataframe["niveau_label"] != "GLOBAL"].copy()
        global_rows = working_dataframe[working_dataframe["niveau_label"] == "GLOBAL"].copy()

        if global_rows.empty or non_global.empty:
            return working_dataframe

        lot_level_weights = (
            non_global.groupby(["batiment_id", "lot_label", "niveau_id", "niveau_label"], as_index=False)
            .agg(weight=("capex_optimise_line", "sum"))
        )
        building_level_weights = (
            non_global.groupby(["batiment_id", "niveau_id", "niveau_label"], as_index=False)
            .agg(weight=("capex_optimise_line", "sum"))
        )

        ventilated_rows: list[dict] = []

        for _, row in global_rows.iterrows():
            row_dict = row.to_dict()

            exact_weights = lot_level_weights[
                (lot_level_weights["batiment_id"] == row_dict["batiment_id"])
                & (lot_level_weights["lot_label"] == row_dict["lot_label"])
            ].copy()

            fallback_weights = building_level_weights[
                building_level_weights["batiment_id"] == row_dict["batiment_id"]
            ].copy()

            candidate_weights = exact_weights if not exact_weights.empty else fallback_weights

            total_weight = float(candidate_weights["weight"].sum()) if not candidate_weights.empty else 0.0
            if total_weight <= 0:
                ventilated_rows.append(row_dict)
                continue

            for _, weight_row in candidate_weights.iterrows():
                ratio = float(weight_row["weight"]) / total_weight
                new_row = row_dict.copy()
                new_row["niveau_id"] = weight_row["niveau_id"]
                new_row["niveau_label"] = weight_row["niveau_label"]
                new_row["capex_optimise_line"] = float(row_dict["capex_optimise_line"]) * ratio
                new_row["montant_local"] = float(row_dict["montant_local"]) * ratio
                new_row["economie_line"] = float(row_dict["economie_line"]) * ratio
                new_row["capex_fob_line"] = float(row_dict.get("capex_fob_line", 0.0) or 0.0) * ratio
                new_row["capex_import_ttc_line"] = float(row_dict.get("capex_import_ttc_line", 0.0) or 0.0) * ratio
                new_row["capex_importable_line"] = float(row_dict.get("capex_importable_line", 0.0) or 0.0) * ratio
                new_row["capex_couvert_line"] = float(row_dict.get("capex_couvert_line", 0.0) or 0.0) * ratio
                new_row["capex_import_decide_line"] = float(row_dict.get("capex_import_decide_line", 0.0) or 0.0) * ratio
                ventilated_rows.append(new_row)

        ventilated_dataframe = pd.concat(
            [
                non_global,
                pd.DataFrame(ventilated_rows),
            ],
            ignore_index=True,
        )
        return ventilated_dataframe

    def _build_import_ventilated_dataframe(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """
        Ventile analytiquement les lignes importables encore au niveau `GLOBAL`.

        On s'appuie sur la meme logique que le dashboard Chantier, mais on ne
        redistribue que les lignes importables afin d'ameliorer les analyses
        sourcing par batiment et niveau sans modifier les totaux.
        """
        if dataframe.empty:
            return dataframe.copy()

        working_dataframe = dataframe.copy()
        importable_mask = working_dataframe["importable"] == 1
        global_mask = working_dataframe["niveau_label"] == "GLOBAL"
        rows_to_ventilate = working_dataframe[importable_mask & global_mask].copy()

        if rows_to_ventilate.empty:
            return working_dataframe

        detailed_importable = working_dataframe[
            importable_mask & (working_dataframe["niveau_label"] != "GLOBAL")
        ].copy()
        if detailed_importable.empty:
            return working_dataframe

        lot_level_weights = (
            detailed_importable.groupby(
                ["batiment_id", "lot_label", "niveau_id", "niveau_label"], as_index=False
            )
            .agg(weight=("capex_importable_line", "sum"))
        )
        building_level_weights = (
            detailed_importable.groupby(["batiment_id", "niveau_id", "niveau_label"], as_index=False)
            .agg(weight=("capex_importable_line", "sum"))
        )

        kept_rows = working_dataframe[~(importable_mask & global_mask)].copy()
        ventilated_rows: list[dict] = []

        for _, row in rows_to_ventilate.iterrows():
            row_dict = row.to_dict()

            exact_weights = lot_level_weights[
                (lot_level_weights["batiment_id"] == row_dict["batiment_id"])
                & (lot_level_weights["lot_label"] == row_dict["lot_label"])
            ].copy()
            fallback_weights = building_level_weights[
                building_level_weights["batiment_id"] == row_dict["batiment_id"]
            ].copy()
            candidate_weights = exact_weights if not exact_weights.empty else fallback_weights

            total_weight = float(candidate_weights["weight"].sum()) if not candidate_weights.empty else 0.0
            if total_weight <= 0:
                ventilated_rows.append(row_dict)
                continue

            for _, weight_row in candidate_weights.iterrows():
                ratio = float(weight_row["weight"]) / total_weight
                new_row = row_dict.copy()
                new_row["niveau_id"] = weight_row["niveau_id"]
                new_row["niveau_label"] = weight_row["niveau_label"]
                new_row["capex_optimise_line"] = float(row_dict["capex_optimise_line"]) * ratio
                new_row["montant_local"] = float(row_dict["montant_local"]) * ratio
                new_row["montant_import"] = (
                    float(row_dict["montant_import"]) * ratio
                    if pd.notna(row_dict.get("montant_import"))
                    else row_dict.get("montant_import")
                )
                new_row["economie_line"] = float(row_dict["economie_line"]) * ratio
                new_row["capex_fob_line"] = float(row_dict.get("capex_fob_line", 0.0) or 0.0) * ratio
                new_row["capex_import_ttc_line"] = float(row_dict.get("capex_import_ttc_line", 0.0) or 0.0) * ratio
                new_row["capex_importable_line"] = float(row_dict.get("capex_importable_line", 0.0) or 0.0) * ratio
                new_row["capex_couvert_line"] = float(row_dict.get("capex_couvert_line", 0.0) or 0.0) * ratio
                new_row["capex_import_decide_line"] = float(row_dict.get("capex_import_decide_line", 0.0) or 0.0) * ratio
                new_row["missing_china_price_flag"] = 0
                if float(row_dict.get("capex_importable_line", 0.0) or 0.0) > 0 and float(
                    row_dict.get("capex_couvert_line", 0.0) or 0.0
                ) == 0.0:
                    new_row["missing_china_price_flag"] = ratio
                ventilated_rows.append(new_row)

        return pd.concat([kept_rows, pd.DataFrame(ventilated_rows)], ignore_index=True)

    def _apply_filters_to_dataframe(
        self,
        dataframe: pd.DataFrame,
        filters: DashboardFilters,
    ) -> pd.DataFrame:
        """
        Applique les filtres du frontend sur le DataFrame analytique.
        """
        filtered_dataframe = dataframe.copy()

        if filters.lot_id is not None:
            filtered_dataframe = filtered_dataframe[
                filtered_dataframe["lot_number"] == int(filters.lot_id)
            ]

        if filters.fam_article_id:
            filtered_dataframe = filtered_dataframe[
                filtered_dataframe["fam_article_id"] == filters.fam_article_id
            ]

        if filters.batiment_id:
            filtered_dataframe = filtered_dataframe[
                filtered_dataframe["batiment_id"] == filters.batiment_id
            ]

        if filters.niveau_id:
            filtered_dataframe = filtered_dataframe[
                filtered_dataframe["niveau_id"] == filters.niveau_id
            ]

        return filtered_dataframe

    def _filters_to_dict(self, filters: DashboardFilters) -> dict:
        """
        Compatible Pydantic v1 et v2.
        """
        if hasattr(filters, "model_dump"):
            return filters.model_dump()
        return filters.dict()

    def _group_sum(
        self,
        dataframe: pd.DataFrame,
        group_column: str,
        value_column: str,
        label_column: str,
        value_label: str,
    ) -> list[dict]:
        grouped = (
            dataframe.groupby(group_column, as_index=False)
            .agg(**{value_label: (value_column, "sum")})
            .sort_values(value_label, ascending=False)
            .rename(columns={group_column: label_column})
        )
        return grouped.to_dict(orient="records")
