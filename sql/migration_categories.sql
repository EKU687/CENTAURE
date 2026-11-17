-- ============================================================================
-- CENTAURE — Élargissement des catégories autorisées de la main courante
-- À exécuter dans le SQL Editor Supabase (Run). Idempotent.
--
-- Contexte : le check constraint chk_categorie_valid refusait jusqu'ici
-- 'INITIALISATION', 'AFFECTATION' et les catégories terrain
-- (RONDE, INCIDENT, PRISE_DE_POSTE, ANOMALIE) -> insertions rejetées (23514).
-- Un repli applicatif (categorie -> 'INFORMATION') existe dans le code, mais
-- cette migration rend les vraies catégories valides.
-- ============================================================================

ALTER TABLE public.centaure_main_courante
    DROP CONSTRAINT IF EXISTS chk_categorie_valid;

ALTER TABLE public.centaure_main_courante
    ADD CONSTRAINT chk_categorie_valid
    CHECK (categorie IN (
        'INFORMATION', 'ORDRE', 'DECISION', 'ALERTE', 'SITUATION',
        'INITIALISATION', 'AFFECTATION',
        'RONDE', 'INCIDENT', 'PRISE_DE_POSTE', 'ANOMALIE'
    ));
