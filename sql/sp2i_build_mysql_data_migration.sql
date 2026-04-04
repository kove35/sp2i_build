-- =====================================================================
-- SP2I_BUILD - Migration de donnees vers le modele MySQL cible
-- Source principale :
--   - source_dqe_pdf_articles
--   - source_dqe_pdf_lots
--   - t_projet
--   - t_batiment
--   - dim_niveau
--   - t_lot
--
-- Hypothese de travail :
--   Les tables legacy SQLite ont ete prealablement chargees dans MySQL
--   avec le meme nom et une structure proche de l'existant.
--
-- Objectif :
--   - reconstruire une structure transactionnelle fidele au DQE
--   - conserver la granularite projet -> batiment -> niveau -> lot -> article
--   - utiliser le PDF numerise comme source de verite DQE
-- =====================================================================

START TRANSACTION;

-- ---------------------------------------------------------------------
-- 0. PARAMETRES DE MIGRATION
-- ---------------------------------------------------------------------

SET @code_chantier := 'SP2I_BUILD';
SET @nom_chantier  := 'Centre medical Pointe-Noire';
SET @version_dqe   := 'DQE_2025_08_13';

-- ---------------------------------------------------------------------
-- 1. CHANTIER / PROJET / VERSION
-- ---------------------------------------------------------------------

INSERT INTO chantier (nom, code, description)
SELECT
    @nom_chantier,
    @code_chantier,
    'Chantier SP2I_BUILD alimente depuis le DQE PDF de reference'
FROM dual
WHERE NOT EXISTS (
    SELECT 1 FROM chantier c WHERE c.code = @code_chantier
);

SET @chantier_id := (
    SELECT id
    FROM chantier
    WHERE code = @code_chantier
    LIMIT 1
);

INSERT INTO projet (
    chantier_id,
    nom,
    code_chantier,
    version,
    date_creation,
    statut,
    devise
)
SELECT
    @chantier_id,
    COALESCE(tp.nom_projet, 'Centre medical Pointe-Noire'),
    @code_chantier,
    @version_dqe,
    COALESCE(tp.date_creation, NOW()),
    COALESCE(tp.statut, 'ETUDE'),
    COALESCE(tp.devise, 'FCFA')
FROM t_projet tp
WHERE tp.projet_id = 'PNR_MEDICAL_CENTER'
  AND NOT EXISTS (
      SELECT 1
      FROM projet p
      WHERE p.code_chantier = @code_chantier
        AND p.version = @version_dqe
  )
LIMIT 1;

SET @projet_id := (
    SELECT id
    FROM projet
    WHERE code_chantier = @code_chantier
      AND version = @version_dqe
    LIMIT 1
);

INSERT INTO dqe_version (
    projet_id,
    version_code,
    source_fichier,
    date_import,
    est_version_active,
    commentaire
)
SELECT
    @projet_id,
    @version_dqe,
    MIN(source_file),
    NOW(),
    1,
    'Version reconstruite depuis source_dqe_pdf_articles'
FROM source_dqe_pdf_articles s
WHERE NOT EXISTS (
    SELECT 1
    FROM dqe_version dv
    WHERE dv.projet_id = @projet_id
      AND dv.version_code = @version_dqe
);

SET @version_id := (
    SELECT id
    FROM dqe_version
    WHERE projet_id = @projet_id
      AND version_code = @version_dqe
    LIMIT 1
);

UPDATE dqe_version
SET est_version_active = CASE WHEN id = @version_id THEN 1 ELSE 0 END
WHERE projet_id = @projet_id;

-- ---------------------------------------------------------------------
-- 2. BATIMENTS
-- ---------------------------------------------------------------------

INSERT INTO batiment (
    projet_id,
    code_batiment,
    nom_batiment,
    ordre_affichage
)
SELECT
    @projet_id,
    tb.batiment_id,
    tb.nom_batiment,
    COALESCE(tb.ordre_affichage, 0)
FROM t_batiment tb
WHERE tb.projet_id = 'PNR_MEDICAL_CENTER'
  AND NOT EXISTS (
      SELECT 1
      FROM batiment b
      WHERE b.projet_id = @projet_id
        AND b.code_batiment = tb.batiment_id
  );

-- Batiment technique de secours si des lignes restent ambiguës.
INSERT INTO batiment (
    projet_id,
    code_batiment,
    nom_batiment,
    ordre_affichage
)
SELECT
    @projet_id,
    'BAT_GLOBAL',
    'Batiment Global',
    999
FROM dual
WHERE NOT EXISTS (
    SELECT 1
    FROM batiment b
    WHERE b.projet_id = @projet_id
      AND b.code_batiment = 'BAT_GLOBAL'
);

-- ---------------------------------------------------------------------
-- 3. NIVEAUX
-- ---------------------------------------------------------------------

INSERT INTO niveau (
    projet_id,
    batiment_id,
    code_niveau,
    nom_niveau,
    ordre_niveau,
    surface_m2
)
SELECT
    @projet_id,
    b.id,
    dn.niveau_id,
    dn.niveau_id,
    COALESCE(dn.ordre_niveau, 0),
    NULL
FROM dim_niveau dn
JOIN batiment b
  ON b.projet_id = @projet_id
 AND b.code_batiment = dn.batiment_id
WHERE dn.projet_id = 'PNR_MEDICAL_CENTER'
  AND NOT EXISTS (
      SELECT 1
      FROM niveau n
      WHERE n.batiment_id = b.id
        AND n.code_niveau = dn.niveau_id
  );

-- Niveau GLOBAL pour le batiment de secours.
INSERT INTO niveau (
    projet_id,
    batiment_id,
    code_niveau,
    nom_niveau,
    ordre_niveau,
    surface_m2
)
SELECT
    @projet_id,
    b.id,
    'GLOBAL',
    'GLOBAL',
    999,
    NULL
FROM batiment b
WHERE b.projet_id = @projet_id
  AND b.code_batiment = 'BAT_GLOBAL'
  AND NOT EXISTS (
      SELECT 1
      FROM niveau n
      WHERE n.batiment_id = b.id
        AND n.code_niveau = 'GLOBAL'
  );

-- ---------------------------------------------------------------------
-- 4. LOTS
-- ---------------------------------------------------------------------

INSERT INTO lot (
    projet_id,
    numero_lot,
    code_lot,
    nom_lot,
    description_lot,
    type_lot,
    ordre_lot
)
SELECT
    @projet_id,
    tl.lot_id,
    tl.code_lot,
    tl.nom_lot,
    tl.description_lot,
    tl.type_lot,
    COALESCE(tl.ordre_lot, tl.lot_id)
FROM t_lot tl
WHERE NOT EXISTS (
    SELECT 1
    FROM lot l
    WHERE l.projet_id = @projet_id
      AND l.numero_lot = tl.lot_id
);

-- ---------------------------------------------------------------------
-- 5. UTILISATEUR PAR DEFAUT ET BUDGET INITIAL
-- ---------------------------------------------------------------------

INSERT INTO utilisateur (nom, role)
SELECT 'Systeme SP2I_BUILD', 'ADMIN'
FROM dual
WHERE NOT EXISTS (
    SELECT 1 FROM utilisateur u WHERE u.nom = 'Systeme SP2I_BUILD'
);

SET @responsable_systeme_id := (
    SELECT id
    FROM utilisateur
    WHERE nom = 'Systeme SP2I_BUILD'
    LIMIT 1
);

INSERT INTO budget_suivi (
    id_projet,
    budget_initial,
    budget_engage,
    budget_restant
)
SELECT
    @projet_id,
    ROUND(COALESCE(SUM(total_ht), 0), 2),
    0,
    ROUND(COALESCE(SUM(total_ht), 0), 2)
FROM source_dqe_pdf_articles
WHERE NOT EXISTS (
    SELECT 1 FROM budget_suivi bs WHERE bs.id_projet = @projet_id
);

-- ---------------------------------------------------------------------
-- 6. ENRICHISSEMENT TEMPORAIRE DU PDF
-- ---------------------------------------------------------------------

DROP TEMPORARY TABLE IF EXISTS tmp_pdf_articles_enriched;

CREATE TEMPORARY TABLE tmp_pdf_articles_enriched AS
SELECT
    s.id AS source_article_id,
    s.source_file,
    s.page_number,
    s.lot_code,
    CAST(REPLACE(s.lot_code, 'LOT ', '') AS UNSIGNED) AS numero_lot,
    s.lot_label,
    s.section_code,
    s.section_label,
    s.item_number,
    s.designation,
    s.designation_normalized,
    s.unite,
    s.quantite,
    s.pu_ht,
    s.total_ht,
    CASE
        WHEN UPPER(CONCAT(' ', COALESCE(s.section_label, ''), ' ', COALESCE(s.designation, ''), ' ')) LIKE '%ANNEXE%' THEN 'BAT_ANNEXE'
        WHEN UPPER(CONCAT(' ', COALESCE(s.section_label, ''), ' ', COALESCE(s.designation, ''), ' ')) LIKE '%PRINCIPAL%' THEN 'BAT_PRINCIPAL'
        WHEN UPPER(COALESCE(s.section_label, '')) IN ('ETAGE 1', 'ETAGE 2', 'DUPLEX 1', 'DUPLEX 2', 'REZ DE CHAUSSEE', 'RDC', 'FONDATIONS', 'TERRASSE') THEN 'BAT_PRINCIPAL'
        ELSE 'BAT_GLOBAL'
    END AS inferred_batiment_code,
    CASE
        WHEN UPPER(COALESCE(s.section_label, '')) IN ('BÂTIMENT PRINCIPAL', 'BATIMENT PRINCIPAL', 'BÂTIMENT ANNEXE', 'BATIMENT ANNEXE') THEN 'GLOBAL'
        WHEN UPPER(COALESCE(s.section_label, '')) IN ('REZ DE CHAUSSÉE', 'REZ DE CHAUSSEE') THEN 'RDC'
        WHEN UPPER(COALESCE(s.section_label, '')) = 'RDC' THEN 'RDC'
        WHEN UPPER(COALESCE(s.section_label, '')) = 'ETAGE 1' THEN 'ETAGE 1'
        WHEN UPPER(COALESCE(s.section_label, '')) = 'ETAGE 2' THEN 'ETAGE 2'
        WHEN UPPER(COALESCE(s.section_label, '')) = 'DUPLEX 1' THEN 'DUPLEX 1'
        WHEN UPPER(COALESCE(s.section_label, '')) = 'DUPLEX 2' THEN 'DUPLEX 2'
        WHEN UPPER(COALESCE(s.section_label, '')) = 'TERRASSE' THEN 'TERRASSE'
        WHEN UPPER(COALESCE(s.section_label, '')) = 'FONDATIONS' THEN 'FONDATIONS'
        WHEN UPPER(COALESCE(s.designation, '')) LIKE '%(RDC)%' THEN 'RDC'
        WHEN UPPER(COALESCE(s.designation, '')) LIKE '%(ÉTAGE 1)%'
          OR UPPER(COALESCE(s.designation, '')) LIKE '%(ETAGE 1)%' THEN 'ETAGE 1'
        WHEN UPPER(COALESCE(s.designation, '')) LIKE '%(ÉTAGE 2)%'
          OR UPPER(COALESCE(s.designation, '')) LIKE '%(ETAGE 2)%' THEN 'ETAGE 2'
        WHEN UPPER(COALESCE(s.designation, '')) LIKE '%DUPLEX 1%' THEN 'DUPLEX 1'
        WHEN UPPER(COALESCE(s.designation, '')) LIKE '%DUPLEX 2%' THEN 'DUPLEX 2'
        WHEN UPPER(COALESCE(s.designation, '')) LIKE '%TERRASSE%' THEN 'TERRASSE'
        WHEN UPPER(COALESCE(s.designation, '')) LIKE '%FONDATION%' THEN 'FONDATIONS'
        ELSE 'GLOBAL'
    END AS inferred_niveau_code,
    CASE
        WHEN UPPER(COALESCE(s.section_label, '')) IN ('BÂTIMENT PRINCIPAL', 'BATIMENT PRINCIPAL', 'BÂTIMENT ANNEXE', 'BATIMENT ANNEXE') THEN NULL
        WHEN COALESCE(s.section_label, '') = '' THEN 'GENERAL'
        ELSE s.section_label
    END AS inferred_sous_lot_label
FROM source_dqe_pdf_articles s;

-- ---------------------------------------------------------------------
-- 7. SOUS-LOTS
-- ---------------------------------------------------------------------

INSERT INTO sous_lot (
    lot_id,
    code_sous_lot,
    nom_sous_lot,
    description_sous_lot,
    ordre_affichage
)
SELECT DISTINCT
    l.id,
    CONCAT(
        'SL_',
        LPAD(e.numero_lot, 2, '0'),
        '_',
        UPPER(
            REPLACE(
                REPLACE(
                    REPLACE(
                        REPLACE(
                            REPLACE(COALESCE(e.inferred_sous_lot_label, 'GENERAL'), ' ', '_'),
                            '-', '_'
                        ),
                        '''', ''
                    ),
                    'É', 'E'
                ),
                'Â', 'A'
            )
        )
    ) AS code_sous_lot,
    COALESCE(e.inferred_sous_lot_label, 'GENERAL') AS nom_sous_lot,
    CONCAT('Sous-lot issu du PDF pour ', l.nom_lot) AS description_sous_lot,
    0
FROM tmp_pdf_articles_enriched e
JOIN lot l
  ON l.projet_id = @projet_id
 AND l.numero_lot = e.numero_lot
WHERE COALESCE(e.inferred_sous_lot_label, 'GENERAL') IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM sous_lot sl
      WHERE sl.lot_id = l.id
        AND sl.code_sous_lot = CONCAT(
            'SL_',
            LPAD(e.numero_lot, 2, '0'),
            '_',
            UPPER(
                REPLACE(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(COALESCE(e.inferred_sous_lot_label, 'GENERAL'), ' ', '_'),
                                '-', '_'
                            ),
                            '''', ''
                        ),
                        'É', 'E'
                    ),
                    'Â', 'A'
                )
            )
        )
  );

-- ---------------------------------------------------------------------
-- 8. PRESTATIONS
-- ---------------------------------------------------------------------

INSERT INTO prestation (
    projet_id,
    version_id,
    lot_id,
    sous_lot_id,
    code_bpu,
    designation,
    unite,
    quantite,
    prix_unitaire,
    montant_total_ht,
    date_validation,
    statut,
    phase,
    responsable_id
)
SELECT
    @projet_id,
    @version_id,
    l.id,
    sl.id,
    CONCAT('PDF-', e.source_article_id),
    e.designation,
    e.unite,
    e.quantite,
    e.pu_ht,
    e.total_ht,
    NOW(),
    'ACCEPTE',
    'ETUDE',
    @responsable_systeme_id
FROM tmp_pdf_articles_enriched e
JOIN lot l
  ON l.projet_id = @projet_id
 AND l.numero_lot = e.numero_lot
LEFT JOIN sous_lot sl
  ON sl.lot_id = l.id
 AND sl.code_sous_lot = CONCAT(
        'SL_',
        LPAD(e.numero_lot, 2, '0'),
        '_',
        UPPER(
            REPLACE(
                REPLACE(
                    REPLACE(
                        REPLACE(
                            REPLACE(COALESCE(e.inferred_sous_lot_label, 'GENERAL'), ' ', '_'),
                            '-', '_'
                        ),
                        '''', ''
                    ),
                    'É', 'E'
                ),
                'Â', 'A'
            )
        )
    )
WHERE NOT EXISTS (
    SELECT 1
    FROM prestation p
    WHERE p.projet_id = @projet_id
      AND p.version_id = @version_id
      AND p.code_bpu = CONCAT('PDF-', e.source_article_id)
);

-- ---------------------------------------------------------------------
-- 9. PRESTATION_NIVEAU
-- ---------------------------------------------------------------------

INSERT INTO prestation_niveau (
    prestation_id,
    niveau_id,
    batiment_id,
    quantite,
    montant
)
SELECT
    p.id,
    n.id,
    b.id,
    p.quantite,
    p.montant_total_ht
FROM tmp_pdf_articles_enriched e
JOIN prestation p
  ON p.projet_id = @projet_id
 AND p.version_id = @version_id
 AND p.code_bpu = CONCAT('PDF-', e.source_article_id)
JOIN batiment b
  ON b.projet_id = @projet_id
 AND b.code_batiment = e.inferred_batiment_code
JOIN niveau n
  ON n.batiment_id = b.id
 AND n.code_niveau = e.inferred_niveau_code
WHERE NOT EXISTS (
    SELECT 1
    FROM prestation_niveau pn
    WHERE pn.prestation_id = p.id
      AND pn.niveau_id = n.id
      AND pn.batiment_id = b.id
);

-- ---------------------------------------------------------------------
-- 10. MISE A JOUR BUDGET ENGAGE / RESTANT
-- ---------------------------------------------------------------------

CALL mettre_a_jour_budget_restant();

COMMIT;

-- ---------------------------------------------------------------------
-- 11. REQUETES DE CONTROLE POST-MIGRATION
-- ---------------------------------------------------------------------

-- Controle 1 : total DQE importe
-- SELECT ROUND(SUM(montant_total_ht), 2) AS total_dqe_importe
-- FROM prestation
-- WHERE projet_id = @projet_id
--   AND version_id = @version_id;

-- Controle 2 : comparaison avec le PDF de reference
-- Attendu : 1 129 667 152 FCFA
-- SELECT ROUND(SUM(total_ht), 2) AS total_pdf
-- FROM source_dqe_pdf_articles;

-- Controle 3 : nombre de prestations par lot
-- SELECT l.numero_lot, l.nom_lot, COUNT(*) AS nb_prestations, ROUND(SUM(p.montant_total_ht), 2) AS montant_total
-- FROM prestation p
-- JOIN lot l ON l.id = p.lot_id
-- WHERE p.projet_id = @projet_id
-- GROUP BY l.numero_lot, l.nom_lot
-- ORDER BY l.numero_lot;

-- Controle 4 : exemple reel demande
-- LOT 2 -> Batiment Principal -> Etage 1
-- SELECT
--     l.numero_lot,
--     l.nom_lot,
--     b.nom_batiment,
--     n.nom_niveau,
--     ROUND(SUM(pn.montant), 2) AS montant_total
-- FROM prestation_niveau pn
-- JOIN prestation p ON p.id = pn.prestation_id
-- JOIN lot l ON l.id = p.lot_id
-- JOIN batiment b ON b.id = pn.batiment_id
-- JOIN niveau n ON n.id = pn.niveau_id
-- WHERE p.projet_id = @projet_id
--   AND l.numero_lot = 2
--   AND b.code_batiment = 'BAT_PRINCIPAL'
--   AND n.code_niveau = 'ETAGE 1'
-- GROUP BY l.numero_lot, l.nom_lot, b.nom_batiment, n.nom_niveau;

-- Controle 5 : lignes du DQE exemple
-- "LOT 2 : BATIMENT PRINCIPAL ; ETAGE 1 : Locaux humides"
-- SELECT
--     p.designation,
--     p.unite,
--     p.quantite,
--     p.prix_unitaire,
--     p.montant_total_ht
-- FROM prestation p
-- JOIN lot l ON l.id = p.lot_id
-- JOIN prestation_niveau pn ON pn.prestation_id = p.id
-- JOIN batiment b ON b.id = pn.batiment_id
-- JOIN niveau n ON n.id = pn.niveau_id
-- WHERE p.projet_id = @projet_id
--   AND l.numero_lot = 2
--   AND b.code_batiment = 'BAT_PRINCIPAL'
--   AND n.code_niveau = 'ETAGE 1'
-- ORDER BY p.designation;
