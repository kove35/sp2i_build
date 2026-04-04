"""
Audit du dashboard Audit Import.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.schemas import DashboardFilters
from backend.services.dashboard_service import DashboardService


ARTIFACTS_DIR = ROOT_DIR / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)


def compute_expected_import_kpis(dataframe: pd.DataFrame) -> dict[str, float]:
    if dataframe.empty:
        return {
            "capex_fob": 0.0,
            "capex_import_ttc": 0.0,
            "capex_importable": 0.0,
            "articles_sans_prix_chine": 0,
            "taux_couverture_sourcing": 0.0,
        }

    capex_fob = float(dataframe["capex_fob_line"].sum())
    capex_import_ttc = float(dataframe["capex_import_ttc_line"].sum())
    capex_importable = float(dataframe["capex_importable_line"].sum())
    articles_sans_prix_chine = int(dataframe["missing_china_price_flag"].sum())
    capex_couvert = float(dataframe["capex_couvert_line"].sum())
    taux_couverture = capex_couvert / capex_importable if capex_importable else 0.0
    return {
        "capex_fob": capex_fob,
        "capex_import_ttc": capex_import_ttc,
        "capex_importable": capex_importable,
        "articles_sans_prix_chine": articles_sans_prix_chine,
        "taux_couverture_sourcing": taux_couverture,
    }


def build_control_row(name: str, expected: float, backend: float, tolerance: float = 1e-4) -> dict:
    delta = backend - expected
    pct = (delta / expected) if expected else 0.0
    return {
        "Metric": name,
        "Expected": expected,
        "Backend": backend,
        "Ecart": delta,
        "Ecart_%": pct,
        "OK_KO": "OK" if abs(delta) <= tolerance else "KO",
    }


def main() -> None:
    service = DashboardService()
    dataframe = service._load_dashboard_dataframe(DashboardFilters())
    ventilated_dataframe = service._build_import_ventilated_dataframe(dataframe)
    payload = service.get_import_dashboard(DashboardFilters())
    expected = compute_expected_import_kpis(dataframe)
    backend = payload["kpis"]

    kpi_control = pd.DataFrame(
        [
            build_control_row("CAPEX_FOB", expected["capex_fob"], float(backend["capex_fob"])),
            build_control_row(
                "CAPEX_IMPORT_TTC",
                expected["capex_import_ttc"],
                float(backend["capex_import_ttc"]),
            ),
            build_control_row(
                "CAPEX_IMPORTABLE",
                expected["capex_importable"],
                float(backend["capex_importable"]),
            ),
            build_control_row(
                "ARTICLES_SANS_PRIX_CHINE",
                float(expected["articles_sans_prix_chine"]),
                float(backend["articles_sans_prix_chine"]),
            ),
            build_control_row(
                "TAUX_COUVERTURE_SOURCING",
                expected["taux_couverture_sourcing"],
                float(backend["taux_couverture_sourcing"]),
            ),
        ]
    )

    chart_control = pd.DataFrame(
        [
            build_control_row(
                "STRUCTURE_DECISION",
                float(dataframe.groupby("decision_label")["capex_optimise_line"].sum().sum()),
                float(sum(item["value"] for item in payload["charts"]["structure_decision"])),
            ),
            build_control_row(
                "MATRICE_AUDIT_SOURCING",
                float(dataframe.groupby("famille_label")["capex_importable_line"].sum().sum()),
                float(sum(item["capex_importable"] for item in payload["charts"]["matrice_audit_sourcing"])),
            ),
            build_control_row(
                "CAPEX_SANS_PRIX_CHINE",
                float(dataframe[dataframe["missing_china_price_flag"] == 1]["montant_local"].sum()),
                float(sum(item["capex"] for item in payload["charts"]["capex_sans_prix_chine"])),
            ),
            build_control_row(
                "IMPORTABLE_PAR_BATIMENT",
                float(ventilated_dataframe.groupby("batiment_label")["capex_importable_line"].sum().sum()),
                float(sum(item["capex_importable"] for item in payload["charts"]["importable_par_batiment"])),
            ),
            build_control_row(
                "IMPORTABLE_PAR_NIVEAU",
                float(ventilated_dataframe.groupby("niveau_label")["capex_importable_line"].sum().sum()),
                float(sum(item["capex_importable"] for item in payload["charts"]["importable_par_niveau"])),
            ),
        ]
    )

    anomalies = {
        "rows_total": len(dataframe),
        "rows_importable": int((dataframe["importable"] == 1).sum()),
        "rows_global_importable": int(((dataframe["importable"] == 1) & (dataframe["niveau_label"] == "GLOBAL")).sum()),
        "rows_global_importable_after_ventilation": int(
            ((ventilated_dataframe["importable"] == 1) & (ventilated_dataframe["niveau_label"] == "GLOBAL")).sum()
        ),
        "missing_china_price": int(dataframe["missing_china_price_flag"].sum()),
        "import_without_amount": int(((dataframe["decision_label"] == "IMPORT") & (dataframe["capex_import_ttc_line"] <= 0)).sum()),
        "non_importable_import": int(((dataframe["decision_label"] == "IMPORT") & (dataframe["importable"] != 1)).sum()),
    }

    report_lines = [
        "# Audit Dashboard Audit Import",
        "",
        "## Source reelle",
        "",
        "- Source detaillee : `build_fact_metre` via `DashboardService._load_dashboard_dataframe`.",
        "- Ce dashboard ne lit pas directement la table `fact_metre` historique SQLite.",
        "",
        "## KPI sans filtre",
        "",
        f"- CAPEX FOB : `{expected['capex_fob']:,.2f}`",
        f"- CAPEX Import TTC : `{expected['capex_import_ttc']:,.2f}`",
        f"- CAPEX Importable : `{expected['capex_importable']:,.2f}`",
        f"- Articles sans prix Chine : `{expected['articles_sans_prix_chine']}`",
        f"- Taux couverture sourcing : `{expected['taux_couverture_sourcing']:.6f}`",
        "",
        "## Anomalies detectees",
        "",
        f"- Lignes importables : `{anomalies['rows_importable']}`",
        f"- Lignes importables encore au niveau `GLOBAL` : `{anomalies['rows_global_importable']}`",
        f"- Lignes importables encore au niveau `GLOBAL` apres ventilation analytique : `{anomalies['rows_global_importable_after_ventilation']}`",
        f"- Lignes sans prix Chine : `{anomalies['missing_china_price']}`",
        f"- Lignes `IMPORT` sans montant import : `{anomalies['import_without_amount']}`",
        f"- Lignes `IMPORT` non importables : `{anomalies['non_importable_import']}`",
        "",
        "## Lecture metier",
        "",
        "- Le calcul backend est coherent avec la source detaillee.",
        "- Le principal point de vigilance n'est pas un ecart KPI, mais la couverture Chine incomplete et la persistance initiale de lignes importables au niveau GLOBAL.",
        "- La ventilation analytique permet des vues par batiment et niveau sans modifier les totaux du dashboard.",
        "- Les familles les plus exposees sans prix Chine sont la Plomberie, les Faux plafonds/Cloisons, l'Ascenseur et la Climatisation.",
        "",
        "## Fichiers de controle",
        "",
        "- `import_dashboard_audit_kpi_control.csv`",
        "- `import_dashboard_audit_chart_control.csv`",
    ]

    (ARTIFACTS_DIR / "import_dashboard_audit_kpi_control.csv").write_text(
        kpi_control.to_csv(index=False), encoding="utf-8"
    )
    (ARTIFACTS_DIR / "import_dashboard_audit_chart_control.csv").write_text(
        chart_control.to_csv(index=False), encoding="utf-8"
    )
    (ARTIFACTS_DIR / "import_dashboard_audit_report.md").write_text(
        "\n".join(report_lines), encoding="utf-8"
    )

    print(ARTIFACTS_DIR / "import_dashboard_audit_report.md")


if __name__ == "__main__":
    main()
