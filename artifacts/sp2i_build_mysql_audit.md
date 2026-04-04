# Audit Structure SQL - SP2I_BUILD

## Contexte audite

- Projet : `SP2I_BUILD`
- Chantier : `Centre medical a Pointe-Noire`
- Source DQE de reference : `data/DQE_MEDICAL CENTER_13-08-2025.xlsx.pdf`
- Total DQE PDF observe : `1 129 667 152 FCFA`

## Constat sur la base actuellement disponible

L'audit a ete realise a partir des bases SQLite locales :

- `sp2i_build.db`
- `sp2i_saas.db`

Tables metier detectees dans `sp2i_build.db` :

- `t_projet`
- `t_batiment`
- `dim_niveau`
- `t_lot`
- `fact_metre`
- `source_dqe_pdf_articles`
- `source_dqe_pdf_lots`

Tables analytiques detectees dans `sp2i_saas.db` :

- `build_projects`
- `build_dim_batiments`
- `build_dim_niveaux`
- `build_lots`
- `build_sous_lots`
- `build_articles`
- `build_fact_metre`

## Ecarts entre la structure actuelle et la cible ERP / BI

### 1. Hierarchie chantier -> batiment -> niveau incomplete

Points positifs :

- `t_projet` porte deja les informations de projet.
- `t_batiment` porte deja une dimension batiment.
- `dim_niveau` porte deja une dimension niveau.
- `fact_metre` contient deja `batiment_id` et `niveau_id`.

Limites :

- il n'existe pas de table `chantier` formelle ;
- `t_batiment` et `dim_niveau` ne sont pas relies par des cles etrangeres declaratives ;
- le niveau n'a pas de `surface_m2`, pourtant necessaire pour la ventilation automatique ;
- aucune contrainte ne garantit qu'un niveau appartient bien au bon batiment.

### 2. Grain metier insuffisant pour un DQE exploitable en ERP

`fact_metre` est utile pour la BI mais ne remplace pas une structure de saisie / pilotage DQE.

Colonnes observees :

- `projet_id`
- `code_bpu`
- `lot_id`
- `fam_article_id`
- `batiment_id`
- `niveau_id`
- `qte`
- `montant_local`
- `montant_import`
- `decision`

Colonnes manquantes pour un vrai suivi DQE :

- `sous_lot`
- `unite`
- `prix_unitaire`
- `montant_total_ht`
- `date_validation`
- `statut`
- `phase`
- `responsable_id`

Conclusion :

- la base actuelle est orientee analytique ;
- la cible demandee doit ajouter un modele transactionnel `prestation` / `prestation_niveau`.

### 3. Cles etrangeres et contraintes insuffisantes

La structure SQLite actuelle ne montre pas de strategie complete de cles etrangeres metier entre :

- projet
- batiment
- niveau
- lot
- sous_lot
- prestation
- prestation_niveau

Risques :

- donnees orphelines ;
- doublons metier ;
- incoherence entre batiment et niveau ;
- agrégations BI peu fiables.

### 4. Incoherence entre source DQE PDF et base analytique active

Mesures observees :

- `fact_metre` : `300` lignes
- Somme `fact_metre.montant_local` : `848 220 228,66 FCFA`
- `source_dqe_pdf_articles` : `445` lignes
- Somme `source_dqe_pdf_articles.total_ht` : `1 129 667 152 FCFA`

Conclusion :

- la base analytique actuelle n'est pas un reflet complet du DQE PDF de reference ;
- il faut une structure capable de stocker le DQE "tel quel" avant transformation analytique.

### 5. La granularite batiment / niveau existe bien dans la source PDF

Exemples observes dans `source_dqe_pdf_articles` :

- `LOT 2 | ETAGE 1 | Revetement monocouche | 107.66 | 17 276 | 1 859 934`
- `LOT 2 | ETAGE 1 | Releve d'etancheite h=50 cm | 182.8 | 8 641 | 1 579 575`
- `LOT 2 | ETAGE 2 | Revetement monocouche | 99.69 | 17 276 | 1 722 244`
- `LOT 2 | DUPLEX 1 | Revetement bicouche sous protection lourde | 320 | 34 552 | 11 056 640`

Conclusion :

- le modele cible doit absolument garder la hierarchie `batiment -> niveau -> lot -> sous_lot -> article`.

## Recommandations d'architecture

### Recommandation 1

Creer une couche transactionnelle normalisee :

- `chantier`
- `projet`
- `batiment`
- `niveau`
- `lot`
- `sous_lot`
- `prestation`
- `prestation_niveau`

### Recommandation 2

Garder `fact_metre` comme couche analytique derivee, et non comme table de saisie primaire.

### Recommandation 3

Ajouter la gestion de version DQE et l'historisation :

- `dqe_version`
- `audit_modification`

### Recommandation 4

Ajouter les vues d'analyse directement en SQL pour supporter :

- cout par lot ;
- cout par niveau ;
- cout par batiment ;
- cout par batiment + niveau + lot ;
- suivi budgetaire ;
- comparatif budget initial / engage / restant.

## Livrable associe

Le script MySQL complet correspondant est fourni dans :

- `sql/sp2i_build_mysql_upgrade.sql`
