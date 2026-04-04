"""
Moteur de recommandation import "IA" explicable.
"""

from __future__ import annotations

import pandas as pd


class ImportAdvisor:
    """
    Produit des recommandations import a partir des lignes CAPEX.
    """

    def build_recommendations(self, project_id: int, dataframe: pd.DataFrame) -> dict:
        """
        Retourne les meilleures opportunites d'import avec une logique simple.
        """
        if dataframe.empty:
            return {"project_id": project_id, "recommendations": []}

        working_dataframe = dataframe.copy()
        working_dataframe["potential_gain"] = (
            working_dataframe["montant_local"] - working_dataframe["montant_import"]
        )

        recommendations = []
        top_candidates = working_dataframe.sort_values(
            ["potential_gain", "import_score"],
            ascending=[False, False],
        ).head(5)

        for _, row in top_candidates.iterrows():
            recommendation = "CONSERVER LOCAL"
            confidence = 0.45

            if row["montant_import"] > 0 and row["potential_gain"] > 0:
                if row["risk_score"] <= 2:
                    recommendation = "IMPORT PRIORITAIRE"
                    confidence = 0.88
                elif row["risk_score"] <= 3.5:
                    recommendation = "IMPORT AVEC CONTROLE"
                    confidence = 0.72
                else:
                    recommendation = "IMPORT A ETUDIER"
                    confidence = 0.60

            recommendations.append(
                {
                    "scope": "ARTICLE",
                    "label": row["code_bpu"],
                    "recommendation": recommendation,
                    "confidence": round(confidence, 2),
                    "explanation": (
                        f"Economie potentielle {row['potential_gain']:.2f}, "
                        f"risque {row['risk_score']:.2f}/5, "
                        f"score import {row['import_score']:.2f}."
                    ),
                }
            )

        return {"project_id": project_id, "recommendations": recommendations}
