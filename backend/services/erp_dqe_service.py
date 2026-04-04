"""
Service de lecture de la base ERP/DQE locale reconstruite.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pandas as pd

from backend.config import ERP_DATABASE_PATH


@dataclass
class ERPFilters:
    batiment: str | None = None
    niveau: str | None = None
    lot: int | None = None


class ERPDQEService:
    """
    Lit la base `sp2i_erp.db` et expose des jeux de donnees exploitables
    par l'API et le frontend Streamlit.
    """

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(ERP_DATABASE_PATH)
        connection.row_factory = sqlite3.Row
        return connection

    def is_available(self) -> bool:
        return ERP_DATABASE_PATH.exists()

    def _load_base_dataframe(self) -> pd.DataFrame:
        if not self.is_available():
            return pd.DataFrame()

        with self._connect() as connection:
            dataframe = pd.read_sql_query(
                """
                SELECT
                    p.id AS prestation_id,
                    pr.id AS project_id,
                    pr.nom AS projet_nom,
                    pr.code_chantier,
                    dv.version_code,
                    l.id AS lot_pk,
                    l.numero_lot,
                    l.nom_lot,
                    l.description_lot,
                    sl.id AS sous_lot_id,
                    sl.nom_sous_lot,
                    b.id AS batiment_pk,
                    b.code_batiment,
                    b.nom_batiment,
                    n.id AS niveau_pk,
                    n.code_niveau,
                    n.nom_niveau,
                    p.code_bpu,
                    p.designation,
                    p.unite,
                    p.quantite,
                    p.prix_unitaire,
                    p.montant_total_ht,
                    pn.montant AS montant_niveau
                FROM prestation p
                JOIN projet pr ON pr.id = p.projet_id
                LEFT JOIN dqe_version dv ON dv.id = p.version_id
                JOIN lot l ON l.id = p.lot_id
                LEFT JOIN sous_lot sl ON sl.id = p.sous_lot_id
                JOIN prestation_niveau pn ON pn.prestation_id = p.id
                JOIN batiment b ON b.id = pn.batiment_id
                JOIN niveau n ON n.id = pn.niveau_id
                ORDER BY l.numero_lot, b.nom_batiment, n.nom_niveau, p.designation
                """,
                connection,
            )

        if dataframe.empty:
            return dataframe

        dataframe["decision"] = dataframe.apply(
            lambda row: "IMPORT" if row["montant_total_ht"] > 0 else "LOCAL",
            axis=1,
        )
        dataframe["montant_import"] = None
        dataframe["economie"] = 0.0
        dataframe["lot_label"] = (
            "LOT "
            + dataframe["numero_lot"].astype(int).astype(str)
            + " - "
            + dataframe["description_lot"].fillna(dataframe["nom_lot"])
        )
        dataframe["batiment_label"] = dataframe["nom_batiment"]
        dataframe["niveau_label"] = dataframe["nom_niveau"]
        dataframe["sous_lot_label"] = dataframe["nom_sous_lot"].fillna("GENERAL")
        dataframe["montant_local"] = pd.to_numeric(dataframe["montant_niveau"], errors="coerce").fillna(0.0)
        return dataframe

    def _apply_filters(self, dataframe: pd.DataFrame, filters: ERPFilters) -> pd.DataFrame:
        filtered = dataframe.copy()
        if filtered.empty:
            return filtered
        if filters.batiment:
            filtered = filtered[filtered["code_batiment"] == filters.batiment]
        if filters.niveau:
            filtered = filtered[filtered["code_niveau"] == filters.niveau]
        if filters.lot is not None:
            filtered = filtered[filtered["numero_lot"] == int(filters.lot)]
        return filtered

    def get_filters(self) -> dict[str, list[dict]]:
        dataframe = self._load_base_dataframe()
        if dataframe.empty:
            return {"batiments": [], "niveaux": [], "lots": []}

        batiments = (
            dataframe[["code_batiment", "batiment_label"]]
            .drop_duplicates()
            .sort_values("batiment_label")
            .to_dict(orient="records")
        )
        niveaux = (
            dataframe[["code_niveau", "niveau_label"]]
            .drop_duplicates()
            .sort_values("niveau_label")
            .to_dict(orient="records")
        )
        lots = (
            dataframe[["numero_lot", "lot_label"]]
            .drop_duplicates()
            .sort_values("numero_lot")
            .rename(columns={"numero_lot": "value", "lot_label": "label"})
            .to_dict(orient="records")
        )
        return {
            "batiments": [
                {"value": row["code_batiment"], "label": row["batiment_label"]}
                for row in batiments
            ],
            "niveaux": [
                {"value": row["code_niveau"], "label": row["niveau_label"]}
                for row in niveaux
            ],
            "lots": lots,
        }

    def get_dashboard(self, filters: ERPFilters) -> dict:
        dataframe = self._apply_filters(self._load_base_dataframe(), filters)
        if dataframe.empty:
            return {
                "kpis": {
                    "montant_total_ht": 0.0,
                    "nb_prestations": 0,
                    "nb_batiments": 0,
                    "nb_niveaux": 0,
                },
                "charts": {
                    "budget_par_batiment": [],
                    "budget_par_niveau": [],
                    "budget_par_lot": [],
                    "budget_par_batiment_niveau_lot": [],
                },
                "items": [],
            }

        budget_par_batiment = (
            dataframe.groupby("batiment_label", as_index=False)
            .agg(montant_total_ht=("montant_local", "sum"))
            .sort_values("montant_total_ht", ascending=False)
            .to_dict(orient="records")
        )
        budget_par_niveau = (
            dataframe.groupby("niveau_label", as_index=False)
            .agg(montant_total_ht=("montant_local", "sum"))
            .sort_values("montant_total_ht", ascending=False)
            .to_dict(orient="records")
        )
        budget_par_lot = (
            dataframe.groupby(["numero_lot", "lot_label"], as_index=False)
            .agg(montant_total_ht=("montant_local", "sum"))
            .sort_values("numero_lot")
            .to_dict(orient="records")
        )
        budget_par_bnl = (
            dataframe.groupby(["batiment_label", "niveau_label", "lot_label"], as_index=False)
            .agg(montant_total_ht=("montant_local", "sum"))
            .sort_values(["batiment_label", "niveau_label", "lot_label"])
            .to_dict(orient="records")
        )

        items = (
            dataframe[
                [
                    "batiment_label",
                    "niveau_label",
                    "lot_label",
                    "sous_lot_label",
                    "designation",
                    "unite",
                    "quantite",
                    "prix_unitaire",
                    "montant_local",
                ]
            ]
            .sort_values(
                ["batiment_label", "niveau_label", "lot_label", "sous_lot_label", "designation"]
            )
            .to_dict(orient="records")
        )

        return {
            "kpis": {
                "montant_total_ht": float(dataframe["montant_local"].sum()),
                "nb_prestations": int(dataframe["prestation_id"].nunique()),
                "nb_batiments": int(dataframe["code_batiment"].nunique()),
                "nb_niveaux": int(dataframe["code_niveau"].nunique()),
            },
            "charts": {
                "budget_par_batiment": budget_par_batiment,
                "budget_par_niveau": budget_par_niveau,
                "budget_par_lot": budget_par_lot,
                "budget_par_batiment_niveau_lot": budget_par_bnl,
            },
            "items": items,
        }
