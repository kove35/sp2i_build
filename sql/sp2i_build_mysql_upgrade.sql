-- =====================================================================
-- SP2I_BUILD - Migration / extension SQL MySQL
-- Objectif :
--   - normaliser la structure DQE
--   - conserver la hierarchie chantier -> batiment -> niveau -> lot
--   - supporter l'analyse BI et le suivi budgetaire
-- Contraintes :
--   - aucune suppression de table
--   - uniquement CREATE / ALTER / INSERT / UPDATE / VIEW / TRIGGER / PROCEDURE
-- Compatible :
--   - MySQL 8+
-- =====================================================================

-- ---------------------------------------------------------------------
-- 0. TABLES DE REFERENCE COMPLEMENTAIRES
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS chantier (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(255) NOT NULL,
    code VARCHAR(100) NOT NULL,
    description TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_chantier_code UNIQUE (code)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS utilisateur (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(255) NOT NULL,
    role VARCHAR(100) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS phase_chantier (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_phase_chantier_nom UNIQUE (nom)
) ENGINE=InnoDB;

INSERT INTO phase_chantier (nom)
SELECT x.nom
FROM (
    SELECT 'ETUDE' AS nom
    UNION ALL SELECT 'EXECUTION'
    UNION ALL SELECT 'RESERVE'
) AS x
LEFT JOIN phase_chantier p ON p.nom = x.nom
WHERE p.id IS NULL;

-- ---------------------------------------------------------------------
-- 1. TABLES COEUR METIER
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS projet (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    chantier_id BIGINT UNSIGNED NULL,
    nom VARCHAR(255) NOT NULL,
    code_chantier VARCHAR(100) NULL,
    version VARCHAR(50) NULL,
    date_creation DATETIME NULL,
    statut VARCHAR(100) NULL,
    devise VARCHAR(20) NULL DEFAULT 'FCFA',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_projet_chantier
        FOREIGN KEY (chantier_id) REFERENCES chantier(id),
    CONSTRAINT uq_projet_code_version UNIQUE (code_chantier, version)
) ENGINE=InnoDB;

ALTER TABLE projet
    ADD COLUMN IF NOT EXISTS chantier_id BIGINT UNSIGNED NULL,
    ADD COLUMN IF NOT EXISTS code_chantier VARCHAR(100) NULL,
    ADD COLUMN IF NOT EXISTS version VARCHAR(50) NULL,
    ADD COLUMN IF NOT EXISTS date_creation DATETIME NULL,
    ADD COLUMN IF NOT EXISTS statut VARCHAR(100) NULL,
    ADD COLUMN IF NOT EXISTS devise VARCHAR(20) NULL DEFAULT 'FCFA',
    ADD COLUMN IF NOT EXISTS created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS batiment (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    projet_id BIGINT UNSIGNED NOT NULL,
    code_batiment VARCHAR(100) NOT NULL,
    nom_batiment VARCHAR(255) NOT NULL,
    ordre_affichage INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_batiment_projet
        FOREIGN KEY (projet_id) REFERENCES projet(id),
    CONSTRAINT uq_batiment_projet_code UNIQUE (projet_id, code_batiment)
) ENGINE=InnoDB;

ALTER TABLE batiment
    ADD COLUMN IF NOT EXISTS projet_id BIGINT UNSIGNED NULL,
    ADD COLUMN IF NOT EXISTS code_batiment VARCHAR(100) NULL,
    ADD COLUMN IF NOT EXISTS nom_batiment VARCHAR(255) NULL,
    ADD COLUMN IF NOT EXISTS ordre_affichage INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS niveau (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    projet_id BIGINT UNSIGNED NOT NULL,
    batiment_id BIGINT UNSIGNED NOT NULL,
    code_niveau VARCHAR(100) NOT NULL,
    nom_niveau VARCHAR(255) NOT NULL,
    ordre_niveau INT NOT NULL DEFAULT 0,
    surface_m2 DECIMAL(18,2) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_niveau_projet
        FOREIGN KEY (projet_id) REFERENCES projet(id),
    CONSTRAINT fk_niveau_batiment
        FOREIGN KEY (batiment_id) REFERENCES batiment(id),
    CONSTRAINT uq_niveau_batiment_code UNIQUE (batiment_id, code_niveau),
    CONSTRAINT chk_niveau_surface_positive CHECK (surface_m2 IS NULL OR surface_m2 > 0)
) ENGINE=InnoDB;

ALTER TABLE niveau
    ADD COLUMN IF NOT EXISTS projet_id BIGINT UNSIGNED NULL,
    ADD COLUMN IF NOT EXISTS batiment_id BIGINT UNSIGNED NULL,
    ADD COLUMN IF NOT EXISTS code_niveau VARCHAR(100) NULL,
    ADD COLUMN IF NOT EXISTS nom_niveau VARCHAR(255) NULL,
    ADD COLUMN IF NOT EXISTS ordre_niveau INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS surface_m2 DECIMAL(18,2) NULL,
    ADD COLUMN IF NOT EXISTS created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS lot (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    projet_id BIGINT UNSIGNED NOT NULL,
    numero_lot INT NOT NULL,
    code_lot VARCHAR(100) NOT NULL,
    nom_lot VARCHAR(255) NOT NULL,
    description_lot TEXT NULL,
    type_lot VARCHAR(100) NULL,
    ordre_lot INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_lot_projet
        FOREIGN KEY (projet_id) REFERENCES projet(id),
    CONSTRAINT uq_lot_projet_numero UNIQUE (projet_id, numero_lot),
    CONSTRAINT uq_lot_projet_code UNIQUE (projet_id, code_lot)
) ENGINE=InnoDB;

ALTER TABLE lot
    ADD COLUMN IF NOT EXISTS projet_id BIGINT UNSIGNED NULL,
    ADD COLUMN IF NOT EXISTS numero_lot INT NULL,
    ADD COLUMN IF NOT EXISTS code_lot VARCHAR(100) NULL,
    ADD COLUMN IF NOT EXISTS nom_lot VARCHAR(255) NULL,
    ADD COLUMN IF NOT EXISTS description_lot TEXT NULL,
    ADD COLUMN IF NOT EXISTS type_lot VARCHAR(100) NULL,
    ADD COLUMN IF NOT EXISTS ordre_lot INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS sous_lot (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    lot_id BIGINT UNSIGNED NOT NULL,
    code_sous_lot VARCHAR(100) NOT NULL,
    nom_sous_lot VARCHAR(255) NOT NULL,
    description_sous_lot TEXT NULL,
    ordre_affichage INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_sous_lot_lot
        FOREIGN KEY (lot_id) REFERENCES lot(id),
    CONSTRAINT uq_sous_lot_lot_code UNIQUE (lot_id, code_sous_lot)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS dqe_version (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    projet_id BIGINT UNSIGNED NOT NULL,
    version_code VARCHAR(50) NOT NULL,
    source_fichier VARCHAR(500) NULL,
    date_import DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    est_version_active TINYINT(1) NOT NULL DEFAULT 0,
    commentaire TEXT NULL,
    CONSTRAINT fk_dqe_version_projet
        FOREIGN KEY (projet_id) REFERENCES projet(id),
    CONSTRAINT uq_dqe_version_projet_code UNIQUE (projet_id, version_code)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS prestation (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    projet_id BIGINT UNSIGNED NOT NULL,
    version_id BIGINT UNSIGNED NULL,
    lot_id BIGINT UNSIGNED NOT NULL,
    sous_lot_id BIGINT UNSIGNED NULL,
    code_bpu VARCHAR(100) NULL,
    designation TEXT NOT NULL,
    unite VARCHAR(50) NOT NULL,
    quantite DECIMAL(18,3) NOT NULL,
    prix_unitaire DECIMAL(18,2) NOT NULL,
    montant_total_ht DECIMAL(18,2) NOT NULL,
    date_validation DATETIME NULL,
    statut VARCHAR(20) NOT NULL DEFAULT 'REVISION',
    phase VARCHAR(20) NOT NULL DEFAULT 'ETUDE',
    responsable_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_prestation_projet
        FOREIGN KEY (projet_id) REFERENCES projet(id),
    CONSTRAINT fk_prestation_version
        FOREIGN KEY (version_id) REFERENCES dqe_version(id),
    CONSTRAINT fk_prestation_lot
        FOREIGN KEY (lot_id) REFERENCES lot(id),
    CONSTRAINT fk_prestation_sous_lot
        FOREIGN KEY (sous_lot_id) REFERENCES sous_lot(id),
    CONSTRAINT fk_prestation_responsable
        FOREIGN KEY (responsable_id) REFERENCES utilisateur(id),
    CONSTRAINT chk_prestation_quantite_positive CHECK (quantite > 0),
    CONSTRAINT chk_prestation_pu_positive CHECK (prix_unitaire > 0),
    CONSTRAINT chk_prestation_montant_positive CHECK (montant_total_ht > 0),
    CONSTRAINT chk_prestation_statut CHECK (statut IN ('ACCEPTE', 'REVISION', 'REJETE')),
    CONSTRAINT chk_prestation_phase CHECK (phase IN ('ETUDE', 'EXECUTION', 'RESERVE'))
) ENGINE=InnoDB;

ALTER TABLE prestation
    ADD COLUMN IF NOT EXISTS projet_id BIGINT UNSIGNED NULL,
    ADD COLUMN IF NOT EXISTS version_id BIGINT UNSIGNED NULL,
    ADD COLUMN IF NOT EXISTS lot_id BIGINT UNSIGNED NULL,
    ADD COLUMN IF NOT EXISTS sous_lot_id BIGINT UNSIGNED NULL,
    ADD COLUMN IF NOT EXISTS code_bpu VARCHAR(100) NULL,
    ADD COLUMN IF NOT EXISTS designation TEXT NULL,
    ADD COLUMN IF NOT EXISTS unite VARCHAR(50) NULL,
    ADD COLUMN IF NOT EXISTS quantite DECIMAL(18,3) NULL,
    ADD COLUMN IF NOT EXISTS prix_unitaire DECIMAL(18,2) NULL,
    ADD COLUMN IF NOT EXISTS montant_total_ht DECIMAL(18,2) NULL,
    ADD COLUMN IF NOT EXISTS date_validation DATETIME NULL,
    ADD COLUMN IF NOT EXISTS statut VARCHAR(20) NOT NULL DEFAULT 'REVISION',
    ADD COLUMN IF NOT EXISTS phase VARCHAR(20) NOT NULL DEFAULT 'ETUDE',
    ADD COLUMN IF NOT EXISTS responsable_id BIGINT UNSIGNED NULL,
    ADD COLUMN IF NOT EXISTS created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS prestation_niveau (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    prestation_id BIGINT UNSIGNED NOT NULL,
    niveau_id BIGINT UNSIGNED NOT NULL,
    batiment_id BIGINT UNSIGNED NOT NULL,
    quantite DECIMAL(18,3) NOT NULL,
    montant DECIMAL(18,2) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_prestation_niveau_prestation
        FOREIGN KEY (prestation_id) REFERENCES prestation(id),
    CONSTRAINT fk_prestation_niveau_niveau
        FOREIGN KEY (niveau_id) REFERENCES niveau(id),
    CONSTRAINT fk_prestation_niveau_batiment
        FOREIGN KEY (batiment_id) REFERENCES batiment(id),
    CONSTRAINT chk_prestation_niveau_quantite_positive CHECK (quantite > 0),
    CONSTRAINT chk_prestation_niveau_montant_positive CHECK (montant > 0),
    CONSTRAINT uq_prestation_niveau UNIQUE (prestation_id, niveau_id, batiment_id)
) ENGINE=InnoDB;

ALTER TABLE prestation_niveau
    ADD COLUMN IF NOT EXISTS prestation_id BIGINT UNSIGNED NULL,
    ADD COLUMN IF NOT EXISTS niveau_id BIGINT UNSIGNED NULL,
    ADD COLUMN IF NOT EXISTS batiment_id BIGINT UNSIGNED NULL,
    ADD COLUMN IF NOT EXISTS quantite DECIMAL(18,3) NULL,
    ADD COLUMN IF NOT EXISTS montant DECIMAL(18,2) NULL,
    ADD COLUMN IF NOT EXISTS created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS budget_suivi (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_projet BIGINT UNSIGNED NOT NULL,
    budget_initial DECIMAL(18,2) NOT NULL DEFAULT 0,
    budget_engage DECIMAL(18,2) NOT NULL DEFAULT 0,
    budget_restant DECIMAL(18,2) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_budget_suivi_projet
        FOREIGN KEY (id_projet) REFERENCES projet(id),
    CONSTRAINT chk_budget_initial_positive CHECK (budget_initial >= 0),
    CONSTRAINT chk_budget_engage_positive CHECK (budget_engage >= 0),
    CONSTRAINT chk_budget_restant_positive CHECK (budget_restant >= 0),
    CONSTRAINT uq_budget_suivi_projet UNIQUE (id_projet)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS avenant (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_projet BIGINT UNSIGNED NOT NULL,
    montant DECIMAL(18,2) NOT NULL,
    description TEXT NOT NULL,
    date_avenant DATE NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_avenant_projet
        FOREIGN KEY (id_projet) REFERENCES projet(id),
    CONSTRAINT chk_avenant_montant_non_nul CHECK (montant <> 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS facture (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_projet BIGINT UNSIGNED NOT NULL,
    montant DECIMAL(18,2) NOT NULL,
    date_facture DATE NOT NULL,
    statut VARCHAR(20) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_facture_projet
        FOREIGN KEY (id_projet) REFERENCES projet(id),
    CONSTRAINT chk_facture_montant_positive CHECK (montant > 0),
    CONSTRAINT chk_facture_statut CHECK (statut IN ('BROUILLON', 'VALIDEE', 'PAYEE', 'ANNULEE'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS audit_modification (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nom_table VARCHAR(100) NOT NULL,
    id_ligne BIGINT UNSIGNED NOT NULL,
    type_operation VARCHAR(20) NOT NULL,
    detail_modification JSON NULL,
    utilisateur_id BIGINT UNSIGNED NULL,
    date_modification DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_modification_utilisateur
        FOREIGN KEY (utilisateur_id) REFERENCES utilisateur(id),
    CONSTRAINT chk_audit_operation CHECK (type_operation IN ('INSERT', 'UPDATE', 'DELETE'))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2. INDEX DE PERFORMANCE
-- ---------------------------------------------------------------------

CREATE INDEX idx_lot_numero_lot ON lot (numero_lot);
CREATE INDEX idx_prestation_lot ON prestation (lot_id);
CREATE INDEX idx_prestation_sous_lot ON prestation (sous_lot_id);
CREATE INDEX idx_prestation_projet ON prestation (projet_id);
CREATE INDEX idx_prestation_niveau_id_niveau ON prestation_niveau (niveau_id);
CREATE INDEX idx_prestation_niveau_id_batiment ON prestation_niveau (batiment_id);
CREATE INDEX idx_niveau_batiment ON niveau (batiment_id);
CREATE INDEX idx_batiment_projet ON batiment (projet_id);

-- ---------------------------------------------------------------------
-- 3. TRIGGERS DE COHERENCE
-- ---------------------------------------------------------------------

DELIMITER $$

CREATE TRIGGER trg_prestation_niveau_validate_insert
BEFORE INSERT ON prestation_niveau
FOR EACH ROW
BEGIN
    DECLARE v_count INT DEFAULT 0;

    SELECT COUNT(*)
      INTO v_count
      FROM niveau n
     WHERE n.id = NEW.niveau_id
       AND n.batiment_id = NEW.batiment_id;

    IF v_count = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Incoherence : le niveau ne depend pas du batiment fourni.';
    END IF;
END$$

CREATE TRIGGER trg_prestation_niveau_validate_update
BEFORE UPDATE ON prestation_niveau
FOR EACH ROW
BEGIN
    DECLARE v_count INT DEFAULT 0;

    SELECT COUNT(*)
      INTO v_count
      FROM niveau n
     WHERE n.id = NEW.niveau_id
       AND n.batiment_id = NEW.batiment_id;

    IF v_count = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Incoherence : le niveau ne depend pas du batiment fourni.';
    END IF;
END$$

CREATE TRIGGER trg_prestation_niveau_ai
AFTER INSERT ON prestation_niveau
FOR EACH ROW
BEGIN
    UPDATE prestation p
       SET p.montant_total_ht = (
            SELECT COALESCE(SUM(pn.montant), 0)
              FROM prestation_niveau pn
             WHERE pn.prestation_id = NEW.prestation_id
       ),
           p.updated_at = CURRENT_TIMESTAMP
     WHERE p.id = NEW.prestation_id;
END$$

CREATE TRIGGER trg_prestation_niveau_au
AFTER UPDATE ON prestation_niveau
FOR EACH ROW
BEGIN
    UPDATE prestation p
       SET p.montant_total_ht = (
            SELECT COALESCE(SUM(pn.montant), 0)
              FROM prestation_niveau pn
             WHERE pn.prestation_id = NEW.prestation_id
       ),
           p.updated_at = CURRENT_TIMESTAMP
     WHERE p.id = NEW.prestation_id;
END$$

CREATE TRIGGER trg_prestation_niveau_ad
AFTER DELETE ON prestation_niveau
FOR EACH ROW
BEGIN
    UPDATE prestation p
       SET p.montant_total_ht = (
            SELECT COALESCE(SUM(pn.montant), 0)
              FROM prestation_niveau pn
             WHERE pn.prestation_id = OLD.prestation_id
       ),
           p.updated_at = CURRENT_TIMESTAMP
     WHERE p.id = OLD.prestation_id;
END$$

CREATE TRIGGER trg_prestation_audit_insert
AFTER INSERT ON prestation
FOR EACH ROW
BEGIN
    INSERT INTO audit_modification (nom_table, id_ligne, type_operation, detail_modification, utilisateur_id)
    VALUES (
        'prestation',
        NEW.id,
        'INSERT',
        JSON_OBJECT(
            'designation', NEW.designation,
            'quantite', NEW.quantite,
            'prix_unitaire', NEW.prix_unitaire,
            'montant_total_ht', NEW.montant_total_ht
        ),
        NEW.responsable_id
    );
END$$

CREATE TRIGGER trg_prestation_audit_update
AFTER UPDATE ON prestation
FOR EACH ROW
BEGIN
    INSERT INTO audit_modification (nom_table, id_ligne, type_operation, detail_modification, utilisateur_id)
    VALUES (
        'prestation',
        NEW.id,
        'UPDATE',
        JSON_OBJECT(
            'ancienne_quantite', OLD.quantite,
            'nouvelle_quantite', NEW.quantite,
            'ancien_pu', OLD.prix_unitaire,
            'nouveau_pu', NEW.prix_unitaire,
            'ancien_montant', OLD.montant_total_ht,
            'nouveau_montant', NEW.montant_total_ht
        ),
        NEW.responsable_id
    );
END$$

DELIMITER ;

-- ---------------------------------------------------------------------
-- 4. VUES ANALYTIQUES
-- ---------------------------------------------------------------------

CREATE OR REPLACE VIEW vue_budget_par_lot AS
SELECT
    p.projet_id,
    p.lot_id,
    l.numero_lot,
    l.code_lot,
    l.nom_lot,
    SUM(p.montant_total_ht) AS montant_total_ht
FROM prestation p
JOIN lot l ON l.id = p.lot_id
GROUP BY
    p.projet_id,
    p.lot_id,
    l.numero_lot,
    l.code_lot,
    l.nom_lot;

CREATE OR REPLACE VIEW vue_budget_par_niveau AS
SELECT
    p.projet_id,
    pn.niveau_id,
    n.nom_niveau,
    SUM(pn.montant) AS montant_total_ht
FROM prestation_niveau pn
JOIN prestation p ON p.id = pn.prestation_id
JOIN niveau n ON n.id = pn.niveau_id
GROUP BY
    p.projet_id,
    pn.niveau_id,
    n.nom_niveau;

CREATE OR REPLACE VIEW vue_budget_par_batiment AS
SELECT
    p.projet_id,
    pn.batiment_id,
    b.nom_batiment,
    SUM(pn.montant) AS montant_total_ht
FROM prestation_niveau pn
JOIN prestation p ON p.id = pn.prestation_id
JOIN batiment b ON b.id = pn.batiment_id
GROUP BY
    p.projet_id,
    pn.batiment_id,
    b.nom_batiment;

CREATE OR REPLACE VIEW vue_budget_par_batiment_niveau_lot AS
SELECT
    p.projet_id,
    pn.batiment_id,
    b.nom_batiment,
    pn.niveau_id,
    n.nom_niveau,
    p.lot_id,
    l.numero_lot,
    l.nom_lot,
    SUM(pn.montant) AS montant_total_ht
FROM prestation_niveau pn
JOIN prestation p ON p.id = pn.prestation_id
JOIN batiment b ON b.id = pn.batiment_id
JOIN niveau n ON n.id = pn.niveau_id
JOIN lot l ON l.id = p.lot_id
GROUP BY
    p.projet_id,
    pn.batiment_id,
    b.nom_batiment,
    pn.niveau_id,
    n.nom_niveau,
    p.lot_id,
    l.numero_lot,
    l.nom_lot;

CREATE OR REPLACE VIEW vue_suivi_engagement AS
SELECT
    bs.id_projet,
    pr.nom AS nom_projet,
    bs.budget_initial,
    bs.budget_engage,
    bs.budget_restant,
    COALESCE(SUM(f.montant), 0) AS montant_facture,
    COALESCE(SUM(a.montant), 0) AS montant_avenants
FROM budget_suivi bs
JOIN projet pr ON pr.id = bs.id_projet
LEFT JOIN facture f ON f.id_projet = bs.id_projet
LEFT JOIN avenant a ON a.id_projet = bs.id_projet
GROUP BY
    bs.id_projet,
    pr.nom,
    bs.budget_initial,
    bs.budget_engage,
    bs.budget_restant;

CREATE OR REPLACE VIEW vue_comparatif_initial_restant AS
SELECT
    bs.id_projet,
    pr.nom AS nom_projet,
    bs.budget_initial,
    bs.budget_engage,
    bs.budget_restant,
    (bs.budget_initial - bs.budget_restant) AS budget_consomme
FROM budget_suivi bs
JOIN projet pr ON pr.id = bs.id_projet;

-- ---------------------------------------------------------------------
-- 5. PROCEDURES STOCKEES
-- ---------------------------------------------------------------------

DELIMITER $$

CREATE PROCEDURE calculer_cout_lot(IN p_id_lot BIGINT UNSIGNED)
BEGIN
    SELECT
        l.id AS id_lot,
        l.numero_lot,
        l.nom_lot,
        COALESCE(SUM(p.montant_total_ht), 0) AS cout_total_lot
    FROM lot l
    LEFT JOIN prestation p ON p.lot_id = l.id
    WHERE l.id = p_id_lot
    GROUP BY l.id, l.numero_lot, l.nom_lot;
END$$

CREATE PROCEDURE ventiler_par_niveau(
    IN p_id_prestation BIGINT UNSIGNED,
    IN p_montant_total DECIMAL(18,2)
)
BEGIN
    DECLARE v_id_lot BIGINT UNSIGNED;
    DECLARE v_id_projet BIGINT UNSIGNED;
    DECLARE v_total_surface DECIMAL(18,2);
    DECLARE v_quantite DECIMAL(18,3);

    SELECT lot_id, projet_id, quantite
      INTO v_id_lot, v_id_projet, v_quantite
      FROM prestation
     WHERE id = p_id_prestation;

    -- On ne ventile que les lots techniques cibles.
    IF v_id_lot IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Prestation introuvable pour ventilation.';
    END IF;

    IF v_id_lot NOT IN (4, 7, 10) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'La ventilation automatique est reservee aux lots 4, 7 et 10.';
    END IF;

    SELECT COALESCE(SUM(n.surface_m2), 0)
      INTO v_total_surface
      FROM niveau n
     WHERE n.projet_id = v_id_projet
       AND n.surface_m2 IS NOT NULL
       AND n.surface_m2 > 0;

    IF v_total_surface <= 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Impossible de ventiler : aucune surface niveau renseignee.';
    END IF;

    DELETE FROM prestation_niveau
     WHERE prestation_id = p_id_prestation;

    INSERT INTO prestation_niveau (
        prestation_id,
        niveau_id,
        batiment_id,
        quantite,
        montant
    )
    SELECT
        p_id_prestation,
        n.id,
        n.batiment_id,
        ROUND(v_quantite * (n.surface_m2 / v_total_surface), 3) AS quantite_ventilee,
        ROUND(p_montant_total * (n.surface_m2 / v_total_surface), 2) AS montant_ventile
    FROM niveau n
    WHERE n.projet_id = v_id_projet
      AND n.surface_m2 IS NOT NULL
      AND n.surface_m2 > 0;
END$$

CREATE PROCEDURE mettre_a_jour_budget_restant()
BEGIN
    UPDATE budget_suivi bs
    LEFT JOIN (
        SELECT projet_id, COALESCE(SUM(montant_total_ht), 0) AS budget_calcule
        FROM prestation
        GROUP BY projet_id
    ) p ON p.projet_id = bs.id_projet
    SET bs.budget_engage = COALESCE(p.budget_calcule, 0),
        bs.budget_restant = GREATEST(bs.budget_initial - COALESCE(p.budget_calcule, 0), 0),
        bs.updated_at = CURRENT_TIMESTAMP;
END$$

DELIMITER ;

-- ---------------------------------------------------------------------
-- 6. REQUETES DE VALIDATION
-- ---------------------------------------------------------------------

-- Validation 1 : verifier la hierarchie batiment / niveau
-- SELECT b.nom_batiment, n.nom_niveau, n.surface_m2
-- FROM niveau n
-- JOIN batiment b ON b.id = n.batiment_id
-- ORDER BY b.nom_batiment, n.ordre_niveau;

-- Validation 2 : verifier les prestations non ventilees
-- SELECT p.id, p.designation, p.montant_total_ht
-- FROM prestation p
-- LEFT JOIN prestation_niveau pn ON pn.prestation_id = p.id
-- WHERE pn.id IS NULL;

-- Validation 3 : verifier l'equilibre entre prestation et ventilation
-- SELECT
--     p.id,
--     p.designation,
--     p.montant_total_ht AS montant_prestation,
--     COALESCE(SUM(pn.montant), 0) AS montant_ventile
-- FROM prestation p
-- LEFT JOIN prestation_niveau pn ON pn.prestation_id = p.id
-- GROUP BY p.id, p.designation, p.montant_total_ht
-- HAVING ABS(p.montant_total_ht - COALESCE(SUM(pn.montant), 0)) > 1;

-- Validation 4 : cout electricite 1er etage batiment principal
-- Exemple metier demande :
-- "Combien coute le 1er etage du batiment principal en electricite ?"
--
-- SELECT
--     b.nom_batiment,
--     n.nom_niveau,
--     l.nom_lot,
--     SUM(pn.montant) AS cout_total
-- FROM prestation_niveau pn
-- JOIN prestation p ON p.id = pn.prestation_id
-- JOIN lot l ON l.id = p.lot_id
-- JOIN batiment b ON b.id = pn.batiment_id
-- JOIN niveau n ON n.id = pn.niveau_id
-- WHERE l.numero_lot = 7
--   AND b.nom_batiment = 'Batiment Principal'
--   AND n.nom_niveau = 'Etage 1'
-- GROUP BY b.nom_batiment, n.nom_niveau, l.nom_lot;

-- Validation 5 : budget par batiment + niveau + lot
-- SELECT *
-- FROM vue_budget_par_batiment_niveau_lot
-- ORDER BY nom_batiment, nom_niveau, numero_lot;

-- ---------------------------------------------------------------------
-- 7. JALONS DE DONNEES CONSEILLES
-- ---------------------------------------------------------------------

-- Exemple : renseigner les surfaces pour supporter la ventilation
-- UPDATE niveau SET surface_m2 = 107.66 WHERE nom_niveau = 'Etage 1' AND batiment_id = 1;
-- UPDATE niveau SET surface_m2 = 99.69  WHERE nom_niveau = 'Etage 2' AND batiment_id = 1;

-- Exemple : creer le chantier SP2I_BUILD si absent
-- INSERT INTO chantier (nom, code, description)
-- VALUES ('Centre medical Pointe-Noire', 'SP2I_BUILD', 'Projet DQE centre medical')
-- ON DUPLICATE KEY UPDATE description = VALUES(description);

