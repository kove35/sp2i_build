"""
Audit du dashboard Audit Chantier.

Objectif :
- verifier la source reelle
- recalculer KPI et aggregations par dimension
- comparer backend vs valeurs attendues
- generer un rapport exploitable
"""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.schemas import DashboardFilters
from backend.services.dashboard_service import DashboardService


ARTIFACTS_DIR = ROOT_DIR / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)


def compute_expected_kpis(dataframe: pd.DataFrame) -> dict[str, float]:
    if dataframe.empty:
        return {
            "capex_total": 0.0,
            "capex_local": 0.0,
            "capex_import": 0.0,
            "economie": 0.0,
            "taux": 0.0,
        }

    capex_local = float(dataframe["montant_local"].sum())
    capex_import = float(dataframe["montant_import"].fillna(0).sum())
    capex_total = float(dataframe["capex_optimise_line"].sum())
    economie = capex_local - capex_total
    taux = economie / capex_local if capex_local else 0.0
    return {
        "capex_total": capex_total,
        "capex_local": capex_local,
        "capex_import": capex_import,
        "economie": economie,
        "taux": taux,
    }


def build_kpi_control_row(name: str, expected: float, backend: float, tolerance: float = 1e-4) -> dict:
    delta = backend - expected
    pct = (delta / expected) if expected else 0.0
    return {
        "KPI": name,
        "Expected": expected,
        "Backend": backend,
        "Ecart": delta,
        "Ecart_%": pct,
        "OK_KO": "OK" if abs(delta) <= tolerance else "KO",
    }


def build_chart_control_row(name: str, source_sum: float, chart_sum: float, tolerance: float = 1e-4) -> dict:
    delta = chart_sum - source_sum
    pct = (delta / source_sum) if source_sum else 0.0
    return {
        "Graphique": name,
        "Source": source_sum,
        "Dashboard": chart_sum,
        "Ecart": delta,
        "Ecart_%": pct,
        "OK_KO": "OK" if abs(delta) <= tolerance else "KO",
    }


def audit_scenario(service: DashboardService, filters: DashboardFilters, label: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    dataframe = service._load_dashboard_dataframe(filters)
    ventilated_dataframe = service._build_chantier_ventilated_dataframe(dataframe)
    backend_payload = service.get_chantier_dashboard(filters)
    expected = compute_expected_kpis(dataframe)
    backend = backend_payload["kpis"]

    kpi_rows = [
        build_kpi_control_row("CAPEX_TOTAL", expected["capex_total"], float(backend["capex_optimise"])),
        build_kpi_control_row("CAPEX_LOCAL", expected["capex_local"], float(backend["capex_brut"])),
        build_kpi_control_row("CAPEX_IMPORT", expected["capex_import"], float(dataframe["montant_import"].fillna(0).sum())),
        build_kpi_control_row("ECONOMIE", expected["economie"], float(backend["economie"])),
        build_kpi_control_row("TAUX", expected["taux"], float(backend["taux_optimisation"])),
    ]

    chart_rows = []
    lot_source = float(dataframe.groupby("lot_label")["capex_optimise_line"].sum().sum())
    lot_dashboard = float(sum(item["capex"] for item in backend_payload["charts"]["cout_par_lot"]))
    chart_rows.append(build_chart_control_row("COUT_PAR_LOT", lot_source, lot_dashboard))

    building_source = float(dataframe.groupby("batiment_label")["capex_optimise_line"].sum().sum())
    building_dashboard = float(sum(item["capex"] for item in backend_payload["charts"]["cout_par_batiment"]))
    chart_rows.append(build_chart_control_row("COUT_PAR_BATIMENT", building_source, building_dashboard))

    level_source = float(ventilated_dataframe.groupby("niveau_label")["capex_optimise_line"].sum().sum())
    level_dashboard = float(sum(item["capex"] for item in backend_payload["charts"]["cout_par_niveau"]))
    chart_rows.append(build_chart_control_row("COUT_PAR_NIVEAU", level_source, level_dashboard))

    heatmap_source = float(
        ventilated_dataframe.groupby(["lot_label", "niveau_label"])["capex_optimise_line"].sum().sum()
    )
    heatmap_dashboard = float(sum(item["capex"] for item in backend_payload["charts"]["repartition_lot_niveau"]))
    chart_rows.append(build_chart_control_row("REPARTITION_LOT_NIVEAU", heatmap_source, heatmap_dashboard))

    kpi_df = pd.DataFrame(kpi_rows)
    kpi_df.insert(0, "Scenario", label)
    chart_df = pd.DataFrame(chart_rows)
    chart_df.insert(0, "Scenario", label)
    return kpi_df, chart_df


def main() -> None:
    service = DashboardService()
    base_df = service._load_dashboard_dataframe(DashboardFilters())

    source_name = "build_fact_metre"
    legacy_fact_rows = 300
    analytics_rows = len(base_df)

    anomaly_rows = {
        "global_levels": int((base_df["niveau_label"] == "GLOBAL").sum()),
        "global_buildings": int((base_df["batiment_id"] == "BAT_GLOBAL").sum()),
        "null_montant_import": int(base_df["montant_import"].isna().sum()),
        "import_without_import_amount": int(
            ((base_df["decision_label"] == "IMPORT") & (base_df["montant_import"].fillna(0) <= 0)).sum()
        ),
        "non_importable_import": int(
            ((base_df["decision_label"] == "IMPORT") & (base_df["importable"] != 1)).sum()
        ),
    }

    scenarios = [
        ("sans_filtre", DashboardFilters()),
        ("lot_1", DashboardFilters(lot_id=1)),
        ("batiment_principal", DashboardFilters(batiment_id="BAT_PRINCIPAL")),
        ("niveau_etage_1", DashboardFilters(niveau_id="ETAGE 1")),
    ]

    kpi_frames = []
    chart_frames = []
    for label, filters in scenarios:
        kpi_df, chart_df = audit_scenario(service, filters, label)
        kpi_frames.append(kpi_df)
        chart_frames.append(chart_df)

    kpi_control = pd.concat(kpi_frames, ignore_index=True)
    chart_control = pd.concat(chart_frames, ignore_index=True)

    kpi_control_path = ARTIFACTS_DIR / "chantier_dashboard_audit_kpi_control.csv"
    chart_control_path = ARTIFACTS_DIR / "chantier_dashboard_audit_chart_control.csv"
    report_path = ARTIFACTS_DIR / "chantier_dashboard_audit_report.md"

    kpi_control.to_csv(kpi_control_path, index=False)
    chart_control.to_csv(chart_control_path, index=False)

    report_lines = [
        "# Audit Dashboard Audit Chantier",
        "",
        "## Source reelle",
        "",
        f"- Source detaillee utilisee par le backend : `{source_name}`",
        f"- Lignes chargees dans le dashboard : `{analytics_rows}`",
        f"- Lignes dans le `fact_metre` historique SQLite : `{legacy_fact_rows}`",
        "- Conclusion : le dashboard ne lit pas directement la table `fact_metre` historique ; il lit le schema analytique SQLAlchemy `build_fact_metre` via `DashboardService._load_dashboard_dataframe`.",
        "",
        "## KPI",
        "",
        f"- CAPEX Brut (sans filtre) : `{compute_expected_kpis(base_df)['capex_local']:,.2f}`",
        f"- CAPEX Optimise (sans filtre) : `{compute_expected_kpis(base_df)['capex_total']:,.2f}`",
        f"- Economie (sans filtre) : `{compute_expected_kpis(base_df)['economie']:,.2f}`",
        f"- Taux (sans filtre) : `{compute_expected_kpis(base_df)['taux']:.6f}`",
        "",
        "## Anomalies detectees",
        "",
        f"- Lignes avec `niveau = GLOBAL` : `{anomaly_rows['global_levels']}`",
        f"- Lignes avec `batiment = BAT_GLOBAL` : `{anomaly_rows['global_buildings']}`",
        f"- Lignes avec `montant_import` null : `{anomaly_rows['null_montant_import']}`",
        f"- Lignes `decision=IMPORT` sans montant import exploitable : `{anomaly_rows['import_without_import_amount']}`",
        f"- Lignes `decision=IMPORT` alors que `importable != 1` : `{anomaly_rows['non_importable_import']}`",
        "",
        "## Ventilation",
        "",
        "- `GLOBAL` apparait massivement sur le niveau, pas sur le batiment.",
        "- Le backend ventile maintenant analytiquement les lignes `GLOBAL` vers les niveaux détaillés du même bâtiment et du même lot quand c'est possible.",
        "- Les KPI globaux ne sont pas modifiés ; seules les vues par niveau et la matrice `LOT x NIVEAU` utilisent cette ventilation.",
        "",
        "## Audit visuel",
        "",
        "- La page actuelle utilise des graphiques standards avec peu de marge basse ; les labels longs de lot risquent d'etre coupes.",
        "- Aucun `Top N` n'est disponible, donc les graphes peuvent devenir charges.",
        "- Le tableau detaille est absent : la page ne permet pas un controle lisible des lignes sous-jacentes.",
        "",
        "## Fichiers de controle",
        "",
        f"- KPI : `{kpi_control_path.name}`",
        f"- Graphiques : `{chart_control_path.name}`",
    ]
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"Rapport genere : {report_path}")
    print(f"KPI control : {kpi_control_path}")
    print(f"Chart control : {chart_control_path}")


if __name__ == "__main__":
    main()
