# Audit Dashboard Direction

## Source des donnees
- KPI des cartes : source PDF importee via `source_dqe_pdf_articles`.
- Graphiques detaillees et drill-down : meme source PDF unifiee.
- La page Direction est maintenant coherente de bout en bout : une seule source, le PDF de reference.
- PDF de reference detecte : `DQE_MEDICAL CENTER_13-08-2025.xlsx.pdf`
- Total HT du PDF : `1 129 667 152.00 FCFA`

## Anomalies qualite de donnees
- Doublons sur la cle metier code_bpu + designation + batiment + niveau : 221

## Controle KPI

| Scenario | KPI | Backend | Dashboard | Ecart | Ecart % | OK/KO |
|---|---|---:|---:|---:|---:|---|
| Sans filtre | capex_brut | 1 129 667 152.00 FCFA | 1 129 667 152.00 FCFA | 0.00 FCFA | 0.0000 % | OK |
| Sans filtre | capex_optimise | 584 017 781.54 FCFA | 584 017 781.54 FCFA | 0.00 FCFA | 0.0000 % | OK |
| Sans filtre | economie | 545 649 370.46 FCFA | 545 649 370.46 FCFA | 0.00 FCFA | 0.0000 % | OK |
| Sans filtre | taux_optimisation | 48.3018 % | 48.3018 % | 0.0000 % | 0.0000 % | OK |
| Filtre LOT: LOT 1 - Gros œuvre et démolition | capex_brut | 218 723 945.00 FCFA | 218 723 945.00 FCFA | 0.00 FCFA | 0.0000 % | OK |
| Filtre LOT: LOT 1 - Gros œuvre et démolition | capex_optimise | 218 723 945.00 FCFA | 218 723 945.00 FCFA | 0.00 FCFA | 0.0000 % | OK |
| Filtre LOT: LOT 1 - Gros œuvre et démolition | economie | 0.00 FCFA | 0.00 FCFA | 0.00 FCFA | 0.0000 % | OK |
| Filtre LOT: LOT 1 - Gros œuvre et démolition | taux_optimisation | 0.0000 % | 0.0000 % | 0.0000 % | 0.0000 % | OK |
| Filtre FAMILLE: Alucobond – Bardage Façade | capex_brut | 159 589 381.00 FCFA | 159 589 381.00 FCFA | 0.00 FCFA | 0.0000 % | OK |
| Filtre FAMILLE: Alucobond – Bardage Façade | capex_optimise | 12 179 389.85 FCFA | 12 179 389.85 FCFA | 0.00 FCFA | 0.0000 % | OK |
| Filtre FAMILLE: Alucobond – Bardage Façade | economie | 147 409 991.15 FCFA | 147 409 991.15 FCFA | 0.00 FCFA | 0.0000 % | OK |
| Filtre FAMILLE: Alucobond – Bardage Façade | taux_optimisation | 92.3683 % | 92.3683 % | 0.0000 % | 0.0000 % | OK |

## Controle graphiques

| Scenario | Graphique | Source | Graphique | Ecart | OK/KO |
|---|---|---:|---:|---:|---|
| Sans filtre | CAPEX par lot | 1 129 667 152.00 FCFA | 1 129 667 152.00 FCFA | 0.00 FCFA | OK |
| Sans filtre | Economie par famille | 545 649 370.46 FCFA | 545 649 370.46 FCFA | 0.00 FCFA | OK |
| Sans filtre | Structure decision | 584 017 781.54 FCFA | 584 017 781.54 FCFA | 0.00 FCFA | OK |
| Sans filtre | Top articles import | 310 795 303.94 FCFA | 310 795 303.94 FCFA | 0.00 FCFA | OK |
| Filtre LOT: LOT 1 - Gros œuvre et démolition | CAPEX par lot | 218 723 945.00 FCFA | 218 723 945.00 FCFA | 0.00 FCFA | OK |
| Filtre LOT: LOT 1 - Gros œuvre et démolition | Economie par famille | 0.00 FCFA | 0.00 FCFA | 0.00 FCFA | OK |
| Filtre LOT: LOT 1 - Gros œuvre et démolition | Structure decision | 218 723 945.00 FCFA | 218 723 945.00 FCFA | 0.00 FCFA | OK |
| Filtre LOT: LOT 1 - Gros œuvre et démolition | Top articles import | 0.00 FCFA | 0.00 FCFA | 0.00 FCFA | OK |
| Filtre FAMILLE: Alucobond – Bardage Façade | CAPEX par lot | 159 589 381.00 FCFA | 159 589 381.00 FCFA | 0.00 FCFA | OK |
| Filtre FAMILLE: Alucobond – Bardage Façade | Economie par famille | 147 409 991.15 FCFA | 147 409 991.15 FCFA | 0.00 FCFA | OK |
| Filtre FAMILLE: Alucobond – Bardage Façade | Structure decision | 12 179 389.85 FCFA | 12 179 389.85 FCFA | 0.00 FCFA | OK |
| Filtre FAMILLE: Alucobond – Bardage Façade | Top articles import | 147 409 991.15 FCFA | 147 409 991.15 FCFA | 0.00 FCFA | OK |

## Conclusion
- Le dashboard Direction est maintenant unifie sur une source unique : le PDF de reference.
- Les KPI et les graphiques controles ici racontent donc la meme histoire metier.
- Rapport CSV KPI : `artifacts\direction_dashboard_audit_kpi_control.csv`
- Rapport CSV graphiques : `artifacts\direction_dashboard_audit_chart_control.csv`