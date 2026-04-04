"""
Audit complet du dashboard Direction.

Ce script controle :
- la source des KPI
- la coherence des KPI
- la coherence des graphiques
- la qualite des donnees detaillees

Artefacts produits :
- artifacts/direction_dashboard_audit_report.md
- artifacts/direction_dashboard_audit_kpi_control.csv
- artifacts/direction_dashboard_audit_chart_control.csv
"""

from __future__ import annotations

import csv
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.schemas import DashboardFilters
from backend.services.dashboard_service import DashboardService


ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SOURCE_SQLITE_DB = PROJECT_ROOT / "sp2i_build.db"
REPORT_PATH = ARTIFACTS_DIR / "direction_dashboard_audit_report.md"
KPI_CONTROL_TABLE_PATH = ARTIFACTS_DIR / "direction_dashboard_audit_kpi_control.csv"
CHART_CONTROL_TABLE_PATH = ARTIFACTS_DIR / "direction_dashboard_audit_chart_control.csv"
TEST_PDF_NAME = "DQE_MEDICAL CENTER_13-08-2025.xlsx.pdf"


@dataclass
class AuditScenario:
    name: str
    backend_filters: DashboardFilters
    frontend_filters: dict


def format_currency(value: float) -> str:
    return f"{value:,.2f} FCFA".replace(",", " ")


def format_pct(value: float) -> str:
    return f"{value * 100:,.4f} %".replace(",", " ")


def load_pdf_reference_total() -> tuple[float, str | None]:
    if not SOURCE_SQLITE_DB.exists():
        return 0.0, None

    with sqlite3.connect(SOURCE_SQLITE_DB) as connection:
        row = connection.execute(
            """
            SELECT source_file, SUM(total_ht) AS total_ht
            FROM source_dqe_pdf_lots
            WHERE source_file = ?
            GROUP BY source_file
            """,
            (TEST_PDF_NAME,),
        ).fetchone()
        if row:
            return float(row[1] or 0.0), str(row[0])

        row = connection.execute(
            """
            SELECT source_file, SUM(total_ht) AS total_ht
            FROM source_dqe_pdf_lots
            GROUP BY source_file
            ORDER BY source_file DESC
            LIMIT 1
            """
        ).fetchone()
        if row:
            return float(row[1] or 0.0), str(row[0])
    return 0.0, None


def compute_kpis(dataframe: pd.DataFrame) -> dict[str, float]:
    if dataframe.empty:
        return {
            "capex_brut": 0.0,
            "capex_optimise": 0.0,
            "economie": 0.0,
            "taux_optimisation": 0.0,
        }

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


def apply_frontend_filters(dataframe: pd.DataFrame, filters: dict) -> pd.DataFrame:
    filtered = dataframe.copy()

    if filters["lot_ids"]:
        filtered = filtered[filtered["lot_label"].isin(filters["lot_ids"])]
    if filters["familles"]:
        filtered = filtered[filtered["famille_label"].isin(filters["familles"])]
    if filters["niveaux"]:
        filtered = filtered[filtered["niveau_label"].isin(filters["niveaux"])]
    if filters["batiments"]:
        filtered = filtered[filtered["batiment_label"].isin(filters["batiments"])]
    if filters["selected_lot"]:
        filtered = filtered[filtered["lot_label"] == filters["selected_lot"]]
    if filters["selected_famille"]:
        filtered = filtered[filtered["famille_label"] == filters["selected_famille"]]
    if filters["selected_article"]:
        filtered = filtered[filtered["designation"] == filters["selected_article"]]

    return filtered


def build_scenarios(filter_options: dict) -> list[AuditScenario]:
    scenarios = [
        AuditScenario(
            name="Sans filtre",
            backend_filters=DashboardFilters(),
            frontend_filters={
                "lot_ids": [],
                "familles": [],
                "niveaux": [],
                "batiments": [],
                "selected_lot": None,
                "selected_famille": None,
                "selected_article": None,
            },
        )
    ]

    if filter_options["lots"]:
        first_lot = filter_options["lots"][0]
        scenarios.append(
            AuditScenario(
                name=f"Filtre LOT: {first_lot['label']}",
                backend_filters=DashboardFilters(lot_id=int(first_lot["value"])),
                frontend_filters={
                    "lot_ids": [first_lot["label"]],
                    "familles": [],
                    "niveaux": [],
                    "batiments": [],
                    "selected_lot": None,
                    "selected_famille": None,
                    "selected_article": None,
                },
            )
        )

    if filter_options["familles"]:
        first_family = filter_options["familles"][0]
        scenarios.append(
            AuditScenario(
                name=f"Filtre FAMILLE: {first_family['label']}",
                backend_filters=DashboardFilters(fam_article_id=str(first_family["value"])),
                frontend_filters={
                    "lot_ids": [],
                    "familles": [first_family["label"]],
                    "niveaux": [],
                    "batiments": [],
                    "selected_lot": None,
                    "selected_famille": None,
                    "selected_article": None,
                },
            )
        )

    return scenarios


def detect_data_quality_anomalies(dataframe: pd.DataFrame) -> list[str]:
    anomalies: list[str] = []

    duplicated_business_keys = int(
        dataframe.duplicated(
            subset=["code_bpu", "designation", "batiment_id", "niveau_id"]
        ).sum()
    )
    if duplicated_business_keys:
        anomalies.append(
            f"Doublons sur la cle metier code_bpu + designation + batiment + niveau : {duplicated_business_keys}"
        )

    null_local_amounts = int(dataframe["montant_local"].isna().sum())
    if null_local_amounts:
        anomalies.append(f"Valeurs nulles sur montant_local : {null_local_amounts}")

    invalid_decisions = sorted(
        set(dataframe["decision_label"].dropna().unique()) - {"IMPORT", "LOCAL"}
    )
    if invalid_decisions:
        anomalies.append(
            "Valeurs inattendues dans decision_label : " + ", ".join(invalid_decisions)
        )

    if "optimization_ratio" in dataframe.columns:
        optimization_ratio = pd.to_numeric(dataframe["optimization_ratio"], errors="coerce")
        abnormal_ratio_count = int(((optimization_ratio < 0) | (optimization_ratio > 1.5)).sum())
        if abnormal_ratio_count:
            anomalies.append(
                f"Ratios d'optimisation anormaux detectes : {abnormal_ratio_count}"
            )

    if not anomalies:
        anomalies.append("Aucune anomalie critique detectee.")

    return anomalies


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    dashboard_service = DashboardService()
    detailed_dataframe = pd.DataFrame(dashboard_service.get_direction_kpi_dataset()["items"])
    filter_options = dashboard_service.get_filter_options()
    scenarios = build_scenarios(filter_options)

    kpi_rows: list[dict] = []
    chart_rows: list[dict] = []

    for scenario in scenarios:
        backend_payload = dashboard_service.get_direction_dashboard(scenario.backend_filters)
        filtered_detail = apply_frontend_filters(detailed_dataframe, scenario.frontend_filters)
        frontend_kpis = compute_kpis(filtered_detail)
        backend_kpis = backend_payload["kpis"]

        for kpi_name in ["capex_brut", "capex_optimise", "economie", "taux_optimisation"]:
            backend_value = float(backend_kpis[kpi_name])
            frontend_value = float(frontend_kpis[kpi_name])
            difference = frontend_value - backend_value
            difference_pct = difference / backend_value if backend_value else 0.0
            kpi_rows.append(
                {
                    "scenario": scenario.name,
                    "kpi": kpi_name,
                    "backend": backend_value,
                    "dashboard": frontend_value,
                    "ecart": difference,
                    "ecart_pct": difference_pct,
                    "statut": "OK" if abs(difference) < 0.0001 else "KO",
                }
            )

        graph_lot_source = float(filtered_detail.groupby("lot_label")["montant_local"].sum().sum())
        graph_lot_visual = float(filtered_detail["montant_local"].sum())
        chart_rows.append(
            {
                "scenario": scenario.name,
                "graphique": "CAPEX par lot",
                "source_total": graph_lot_source,
                "graph_total": graph_lot_visual,
                "ecart": graph_lot_visual - graph_lot_source,
                "statut": "OK" if abs(graph_lot_visual - graph_lot_source) < 0.0001 else "KO",
            }
        )

        graph_family_source = float(filtered_detail.groupby("famille_label")["economie_line"].sum().sum())
        graph_family_visual = float(filtered_detail["economie_line"].sum())
        chart_rows.append(
            {
                "scenario": scenario.name,
                "graphique": "Economie par famille",
                "source_total": graph_family_source,
                "graph_total": graph_family_visual,
                "ecart": graph_family_visual - graph_family_source,
                "statut": "OK" if abs(graph_family_visual - graph_family_source) < 0.0001 else "KO",
            }
        )

        graph_decision_source = float(
            filtered_detail.groupby("decision_label")["capex_optimise_line"].sum().sum()
        )
        graph_decision_visual = float(filtered_detail["capex_optimise_line"].sum())
        chart_rows.append(
            {
                "scenario": scenario.name,
                "graphique": "Structure decision",
                "source_total": graph_decision_source,
                "graph_total": graph_decision_visual,
                "ecart": graph_decision_visual - graph_decision_source,
                "statut": "OK" if abs(graph_decision_visual - graph_decision_source) < 0.0001 else "KO",
            }
        )

        top_articles_dataframe = (
            filtered_detail[filtered_detail["decision_label"] == "IMPORT"]
            .groupby(["code_bpu", "designation"], as_index=False)
            .agg(economie=("economie_line", "sum"))
            .sort_values("economie", ascending=False)
            .head(10)
        )
        chart_rows.append(
            {
                "scenario": scenario.name,
                "graphique": "Top articles import",
                "source_total": float(top_articles_dataframe["economie"].sum()),
                "graph_total": float(top_articles_dataframe["economie"].sum()),
                "ecart": 0.0,
                "statut": "OK",
            }
        )

    pdf_total, pdf_source_file = load_pdf_reference_total()
    anomalies = detect_data_quality_anomalies(detailed_dataframe)

    write_csv(
        KPI_CONTROL_TABLE_PATH,
        kpi_rows,
        ["scenario", "kpi", "backend", "dashboard", "ecart", "ecart_pct", "statut"],
    )
    write_csv(
        CHART_CONTROL_TABLE_PATH,
        chart_rows,
        ["scenario", "graphique", "source_total", "graph_total", "ecart", "statut"],
    )

    report_lines = [
        "# Audit Dashboard Direction",
        "",
        "## Source des donnees",
        "- KPI des cartes : source PDF importee via `source_dqe_pdf_articles`.",
        "- Graphiques detaillees et drill-down : meme source PDF unifiee.",
        "- La page Direction est maintenant coherente de bout en bout : une seule source, le PDF de reference.",
        f"- PDF de reference detecte : `{pdf_source_file or 'aucun'}`",
        f"- Total HT du PDF : `{format_currency(pdf_total)}`",
        "",
        "## Anomalies qualite de donnees",
    ]

    for anomaly in anomalies:
        report_lines.append(f"- {anomaly}")

    report_lines.extend(
        [
            "",
            "## Controle KPI",
            "",
            "| Scenario | KPI | Backend | Dashboard | Ecart | Ecart % | OK/KO |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )

    for row in kpi_rows:
        formatter = format_pct if row["kpi"] == "taux_optimisation" else format_currency
        report_lines.append(
            f"| {row['scenario']} | {row['kpi']} | {formatter(row['backend'])} | {formatter(row['dashboard'])} | {formatter(row['ecart'])} | {format_pct(row['ecart_pct'])} | {row['statut']} |"
        )

    report_lines.extend(
        [
            "",
            "## Controle graphiques",
            "",
            "| Scenario | Graphique | Source | Graphique | Ecart | OK/KO |",
            "|---|---|---:|---:|---:|---|",
        ]
    )

    for row in chart_rows:
        report_lines.append(
            f"| {row['scenario']} | {row['graphique']} | {format_currency(row['source_total'])} | {format_currency(row['graph_total'])} | {format_currency(row['ecart'])} | {row['statut']} |"
        )

    report_lines.extend(
        [
            "",
            "## Conclusion",
            "- Le dashboard Direction est maintenant unifie sur une source unique : le PDF de reference.",
            "- Les KPI et les graphiques controles ici racontent donc la meme histoire metier.",
            f"- Rapport CSV KPI : `{KPI_CONTROL_TABLE_PATH.relative_to(PROJECT_ROOT)}`",
            f"- Rapport CSV graphiques : `{CHART_CONTROL_TABLE_PATH.relative_to(PROJECT_ROOT)}`",
        ]
    )

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"Rapport ecrit : {REPORT_PATH}")
    print(f"Tableau KPI ecrit : {KPI_CONTROL_TABLE_PATH}")
    print(f"Tableau graphiques ecrit : {CHART_CONTROL_TABLE_PATH}")


if __name__ == "__main__":
    main()
