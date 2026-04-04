# Audit Dashboard Audit Import

## Source reelle

- Source detaillee : `build_fact_metre` via `DashboardService._load_dashboard_dataframe`.
- Ce dashboard ne lit pas directement la table `fact_metre` historique SQLite.

## KPI sans filtre

- CAPEX FOB : `145,586,968.20`
- CAPEX Import TTC : `228,775,361.88`
- CAPEX Importable : `775,729,166.13`
- Articles sans prix Chine : `60`
- Taux couverture sourcing : `0.810197`

## Anomalies detectees

- Lignes importables : `245`
- Lignes importables encore au niveau `GLOBAL` : `104`
- Lignes importables encore au niveau `GLOBAL` apres ventilation analytique : `0`
- Lignes sans prix Chine : `60`
- Lignes `IMPORT` sans montant import : `0`
- Lignes `IMPORT` non importables : `0`

## Lecture metier

- Le calcul backend est coherent avec la source detaillee.
- Le principal point de vigilance n'est pas un ecart KPI, mais la couverture Chine incomplete et la persistance initiale de lignes importables au niveau GLOBAL.
- La ventilation analytique permet des vues par batiment et niveau sans modifier les totaux du dashboard.
- Les familles les plus exposees sans prix Chine sont la Plomberie, les Faux plafonds/Cloisons, l'Ascenseur et la Climatisation.

## Fichiers de controle

- `import_dashboard_audit_kpi_control.csv`
- `import_dashboard_audit_chart_control.csv`