# Audit Dashboard Audit Chantier

## Source reelle

- Source detaillee utilisee par le backend : `build_fact_metre`
- Lignes chargees dans le dashboard : `301`
- Lignes dans le `fact_metre` historique SQLite : `300`
- Conclusion : le dashboard ne lit pas directement la table `fact_metre` historique ; il lit le schema analytique SQLAlchemy `build_fact_metre` via `DashboardService._load_dashboard_dataframe`.

## KPI

- CAPEX Brut (sans filtre) : `877,315,228.61`
- CAPEX Optimise (sans filtre) : `458,814,541.77`
- Economie (sans filtre) : `418,500,686.84`
- Taux (sans filtre) : `0.477024`

## Anomalies detectees

- Lignes avec `niveau = GLOBAL` : `112`
- Lignes avec `batiment = BAT_GLOBAL` : `0`
- Lignes avec `montant_import` null : `0`
- Lignes `decision=IMPORT` sans montant import exploitable : `0`
- Lignes `decision=IMPORT` alors que `importable != 1` : `0`

## Ventilation

- `GLOBAL` apparait massivement sur le niveau, pas sur le batiment.
- Le backend ventile maintenant analytiquement les lignes `GLOBAL` vers les niveaux détaillés du même bâtiment et du même lot quand c'est possible.
- Les KPI globaux ne sont pas modifiés ; seules les vues par niveau et la matrice `LOT x NIVEAU` utilisent cette ventilation.

## Audit visuel

- La page actuelle utilise des graphiques standards avec peu de marge basse ; les labels longs de lot risquent d'etre coupes.
- Aucun `Top N` n'est disponible, donc les graphes peuvent devenir charges.
- Le tableau detaille est absent : la page ne permet pas un controle lisible des lignes sous-jacentes.

## Fichiers de controle

- KPI : `chantier_dashboard_audit_kpi_control.csv`
- Graphiques : `chantier_dashboard_audit_chart_control.csv`