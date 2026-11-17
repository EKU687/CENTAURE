-- ============================================================================
-- CENTAURE — Pièces jointes des cellules de crise (upload / édition / suppression)
-- À exécuter dans le SQL Editor Supabase (Run). Idempotent.
--
-- Contexte : chaque crise peut recevoir des fichiers joints (jpg, png, pdf,
-- documents office, e-mails .eml/.msg, zip...). Le binaire va dans le bucket
-- Storage privé 'centaure-crise-fichiers' ; la métadonnée va dans la table
-- centaure_crise_fichiers. Téléchargement par URL signée (1 h).
-- ============================================================================

-- 1) Table des métadonnées de fichiers joints à une crise.
CREATE TABLE IF NOT EXISTS public.centaure_crise_fichiers (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crise_id      UUID NOT NULL REFERENCES public.centaure_crises(id) ON DELETE CASCADE,
    nom_fichier   TEXT NOT NULL,
    storage_path  TEXT NOT NULL,
    mime          TEXT,
    taille_octets BIGINT,
    commentaire   TEXT,
    uploade_par   TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_crise_fichiers_crise
    ON public.centaure_crise_fichiers(crise_id, created_at DESC);

-- 2) RLS + policies (même niveau d'accès que les autres tables de l'app :
--    la clé publishable utilisée par CENTAURE doit pouvoir lire/écrire).
ALTER TABLE public.centaure_crise_fichiers ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "centaure_crise_fichiers_all" ON public.centaure_crise_fichiers;
CREATE POLICY "centaure_crise_fichiers_all"
    ON public.centaure_crise_fichiers
    FOR ALL
    TO anon, authenticated
    USING (true)
    WITH CHECK (true);

-- 3) Bucket Storage privé pour les fichiers de crise.
INSERT INTO storage.buckets (id, name, public)
VALUES ('centaure-crise-fichiers', 'centaure-crise-fichiers', false)
ON CONFLICT (id) DO NOTHING;

-- 4) Policies Storage sur ce bucket (anon/authenticated, comme le reste de l'app).
DROP POLICY IF EXISTS "centaure-crise-fichiers insert" ON storage.objects;
CREATE POLICY "centaure-crise-fichiers insert"
    ON storage.objects FOR INSERT TO anon, authenticated
    WITH CHECK (bucket_id = 'centaure-crise-fichiers');

DROP POLICY IF EXISTS "centaure-crise-fichiers select" ON storage.objects;
CREATE POLICY "centaure-crise-fichiers select"
    ON storage.objects FOR SELECT TO anon, authenticated
    USING (bucket_id = 'centaure-crise-fichiers');

DROP POLICY IF EXISTS "centaure-crise-fichiers delete" ON storage.objects;
CREATE POLICY "centaure-crise-fichiers delete"
    ON storage.objects FOR DELETE TO anon, authenticated
    USING (bucket_id = 'centaure-crise-fichiers');
