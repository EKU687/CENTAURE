-- ============================================================================
-- CENTAURE — Migration PCO (Poste de Commandement Opérationnel)
-- À exécuter dans la console SQL Supabase (SQL Editor > Run).
-- Compatible idempotent : peut être rejouée sans risque.
-- ============================================================================

-- 1) Horodatage d'activation de la cellule de crise (chrono PCO / suivi).
--    Fallback applicatif sur created_at si NULL (crises déjà existantes).
ALTER TABLE public.centaure_crises
    ADD COLUMN IF NOT EXISTS activated_at TIMESTAMPTZ;

-- 2) Typologie des bulletins SITREP :
--    'STANDARD'            : point de situation en cours de gestion
--    'CLOTURE_JOURNALIERE' : SITREP de fin de journée
ALTER TABLE public.centaure_sitreps
    ADD COLUMN IF NOT EXISTS type_sitrep TEXT NOT NULL DEFAULT 'STANDARD';

-- Valeurs par défaut pour les lignes existantes.
UPDATE public.centaure_sitreps SET type_sitrep = 'STANDARD' WHERE type_sitrep IS NULL;
