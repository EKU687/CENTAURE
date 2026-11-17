-- ============================================================================
-- CENTAURE — Élargissement des fonctions autorisées des membres de cellule
-- À exécuter dans le SQL Editor Supabase (Run). Idempotent.
--
-- Contexte : le check constraint chk_fonction_valid de centaure_crise_membres
-- ne laissait passer que 'Agent', 'Chef de cellule', 'Responsable de cellule'
-- -> les autres fonctions du sélecteur UI (Directeur de crise, Officier de
-- liaison, etc.) étaient rejetées (SQLSTATE 23514, « Erreur affectation en
-- BDD »). Un repli applicatif (fonction -> 'Agent') existe dans le code.
-- ============================================================================

ALTER TABLE public.centaure_crise_membres
    DROP CONSTRAINT IF EXISTS chk_fonction_valid;

ALTER TABLE public.centaure_crise_membres
    ADD CONSTRAINT chk_fonction_valid
    CHECK (fonction_crise IN (
        'Agent',
        'Chef de cellule',
        'Responsable de cellule',
        'Directeur de crise',
        'Responsable sûreté',
        'Chef de service',
        'Officier de liaison',
        'Référent Cyber / SSI',
        'Rédacteur Main Courante',
        'Administratif'
    ));

-- Diagnostic : liste de TOUTES les contraintes CHECK du schéma public
-- (pour repérer d'un coup les autres listes fermées) :
-- SELECT conrelid::regclass AS table, conname, pg_get_constraintdef(oid)
-- FROM pg_constraint
-- WHERE contype = 'c' AND connamespace = 'public'::regnamespace;
