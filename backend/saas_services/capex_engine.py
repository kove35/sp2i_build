"""
Moteur metier CAPEX du mode SaaS.
"""

from __future__ import annotations

import pandas as pd


class CapexEngine:
    """
    Centralise les calculs analytiques du dashboard premium.
    """

    @staticmethod
    def filter_data(dataframe: pd.DataFrame, filters: dict | None = None) -> pd.DataFrame:
        """
        Applique les filtres globaux de facon centrale.
        """
        filters = filters or {}
        filtered_dataframe = dataframe.copy()

        if filtered_dataframe.empty:
            return filtered_dataframe

        if filters.get("lot_ids"):
            filtered_dataframe = filtered_dataframe[
                filtered_dataframe["lot_id"].isin(filters["lot_ids"])
            ]

        if filters.get("families"):
            filtered_dataframe = filtered_dataframe[
                filtered_dataframe["family_article"].isin(filters["families"])
            ]

        if filters.get("niveaux"):
            filtered_dataframe = filtered_dataframe[
                filtered_dataframe["niveau"].isin(filters["niveaux"])
            ]

        if filters.get("batiments"):
            filtered_dataframe = filtered_dataframe[
                filtered_dataframe["batiment"].isin(filters["batiments"])
            ]

        return filtered_dataframe

    @staticmethod
    def enrich_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
        """
        Ajoute les colonnes metier derivees.
        """
        enriched_dataframe = dataframe.copy()
        if enriched_dataframe.empty:
            return enriched_dataframe

        enriched_dataframe["capex_optimise"] = enriched_dataframe.apply(
            lambda row: row["montant_import"]
            if row["decision"] == "IMPORT"
            else row["montant_local"],
            axis=1,
        )
        enriched_dataframe["economie"] = (
            enriched_dataframe["montant_local"] - enriched_dataframe["capex_optimise"]
        )
        enriched_dataframe["is_missing_china_price"] = (
            enriched_dataframe["montant_import"] <= 0
        )
        return enriched_dataframe

    def build_dashboard_payload(
        self,
        dataframe: pd.DataFrame,
        filters: dict | None = None,
    ) -> dict:
        """
        Produit KPI, filtres disponibles et series de graphiques.
        """
        filtered_dataframe = self.enrich_dataframe(self.filter_data(dataframe, filters))

        capex_brut = (
            float(filtered_dataframe["montant_local"].sum())
            if not filtered_dataframe.empty
            else 0.0
        )
        capex_optimise = (
            float(filtered_dataframe["capex_optimise"].sum())
            if not filtered_dataframe.empty
            else 0.0
        )
        economie = capex_brut - capex_optimise
        taux_optimisation = economie / capex_brut if capex_brut else 0.0

        if filtered_dataframe.empty:
            return {
                "kpis": {
                    "capex_brut": 0.0,
                    "capex_optimise": 0.0,
                    "economie": 0.0,
                    "taux_optimisation": 0.0,
                },
                "charts": {
                    "capex_by_lot": [],
                    "economy_by_family": [],
                    "decision_mix": [],
                    "top_articles": [],
                },
                "filters": {
                    "lots": [],
                    "families": [],
                    "niveaux": [],
                    "batiments": [],
                },
            }

        capex_by_lot = (
            filtered_dataframe.groupby("lot_id", as_index=False)["montant_local"]
            .sum()
            .rename(columns={"montant_local": "value"})
            .sort_values("value", ascending=False)
            .to_dict(orient="records")
        )
        economy_by_family = (
            filtered_dataframe.groupby("family_article", as_index=False)["economie"]
            .sum()
            .sort_values("economie", ascending=False)
            .rename(columns={"family_article": "label", "economie": "value"})
            .to_dict(orient="records")
        )
        decision_mix = (
            filtered_dataframe.groupby("decision", as_index=False)["capex_optimise"]
            .sum()
            .rename(columns={"decision": "label", "capex_optimise": "value"})
            .sort_values("value", ascending=False)
            .to_dict(orient="records")
        )
        top_articles = (
            filtered_dataframe.sort_values("economie", ascending=False)[
                ["code_bpu", "family_article", "lot_id", "economie", "decision"]
            ]
            .head(10)
            .to_dict(orient="records")
        )

        return {
            "kpis": {
                "capex_brut": capex_brut,
                "capex_optimise": capex_optimise,
                "economie": economie,
                "taux_optimisation": taux_optimisation,
            },
            "charts": {
                "capex_by_lot": capex_by_lot,
                "economy_by_family": economy_by_family,
                "decision_mix": decision_mix,
                "top_articles": top_articles,
            },
            "filters": {
                "lots": sorted(filtered_dataframe["lot_id"].dropna().unique().tolist()),
                "families": sorted(
                    filtered_dataframe["family_article"].dropna().unique().tolist()
                ),
                "niveaux": sorted(filtered_dataframe["niveau"].dropna().unique().tolist()),
                "batiments": sorted(
                    filtered_dataframe["batiment"].dropna().unique().tolist()
                ),
            },
        }

