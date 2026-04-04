# Rapport de comparaison DQE PDF vs SP2I_Build

- Projet analytique teste : `Centre Médical Pointe Noire`
- PDF source : `C:\Users\Geoffrey\Desktop\Services Construct\DQE_MEDICAL CENTER_13-08-2025.xlsx.pdf`
- Lots compares : `14`
- Lots identiques sur la base HT : `6/14`

## Totaux globaux

- Total HT PDF : `1 129 667 152.00`
- Total base HT en base : `762 882 807.53`
- Total `total_local` du modele : `877 315 228.65`

## Plus grands ecarts (base HT vs PDF)

- LOT 7 ÉLECTRICITÉ : PDF=175 755 050.00 | DB=30 431 550.00 | Ecart=-145 323 500.00
- LOT 1 GROS ŒUVRE ET DÉMOLITION : PDF=218 723 945.00 | DB=88 335 706.53 | Ecart=-130 388 238.47
- LOT 13 ALUCOBOND : PDF=159 589 381.00 | DB=74 088 757.50 | Ecart=-85 500 623.50
- LOT 14 PEINTURE : PDF=52 589 814.00 | DB=34 231 452.00 | Ecart=-18 358 362.00
- LOT 10 PLOMBERIE SANITAIRE : PDF=47 233 525.00 | DB=64 331 025.00 | Ecart=17 097 500.00
- LOT 6 MENUISERIE BOIS : PDF=24 456 360.00 | DB=20 144 550.00 | Ecart=-4 311 810.00
- LOT 2 ÉTANCHÉITÉ : PDF=38 856 005.00 | DB=38 856 695.50 | Ecart=690.50
- LOT 3 REVÊTEMENT DURS : PDF=152 397 863.00 | DB=152 397 862.00 | Ecart=-1.00
- LOT 4 MENUISERIE ALUMINIUM ET VITRERIE : PDF=109 091 760.00 | DB=109 091 760.00 | Ecart=0.00
- LOT 5 MENUISERIE MÉTALLIQUE ET FERRONNERIE : PDF=11 614 655.00 | DB=11 614 655.00 | Ecart=0.00

## Lecture rapide

- `base_ht_db` compare le PDF au calcul brut `quantite × pu_local`.
- `total_local_db` inclut la logique metier du modele actuel, donc il peut etre plus eleve.
- Si les ecarts sont importants, cela indique que la base actuelle ne correspond pas a cette version du DQE.
