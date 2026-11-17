# 📋 CENTAURE — Suivi de Développement

**Dernière mise à jour :** 17/11/2026 soir — push GitHub + déploiement PROD
Fly.io v34 effectués et recette en ligne OK (voir § Séance du 17/11, suite 3)
**Branche :** `main` — refonte PCO + fin COS + écran mural **committés et
poussés** ( **Serveur DEV local ARRÊTÉ proprement le 14/11 au soir** — port
8080 libéré (curl → 000) ; relance demain :
`cd C:\Dev\CENTAURE && .venv\Scripts\python.exe -u main.py`,
fenêtre dédiée, `PYTHONUNBUFFERED=1` si redirigé, logs dans `_dev_server.log` ;
migration Supabase appliquée ; voir § Déploiement du 13/11 )

---

## 🗓️ Séance du 17/11 — finalisation avant mise en PROD (points 0a/0b/0c)

Objectif : livrer les 3 points notés le 14/11 soir, puis commit/push + déploiement Fly.io.

Décisions prises et raisons :

1. **0c — rester sur l'onglet « Cellules de Crise » après clôture/archivage** :
   l'onglet PCO est désormais rendu dans un `@ui.refreshable`
   (`cockpit.py`), dont le handle `.refresh` est stocké dans
   `app.storage.client["refresh_crises_tab"]` ; `archive_crise_action` /
   `delete_crise_action` (`crise_dialogs.py`) appellent
   `_refresh_crises_tab_or_reload()` (repli `ui.navigate.reload()` si handle
   absent) au lieu de recharger toute la page.
2. **0b — phrase de convocation conditionnelle** : `_phrase_convocation(niveau)`
   dans `notification_service.py` — gravité >= 3 ou CRITIQUE/MAJEURE/S4 →
   « rejoindre immédiatement le PC Crise » ; sinon « prenez connaissance de
   cette activation et tenez-vous prêt(e)… ». Utilisée dans les 2 e-mails
   (activation + affectation individuelle).
3. **0a — SITREP en PDF joint à l'e-mail** : nouveau module
   `app/services/pdf_service.py` — **PDF généré en Python pur** (A4, Helvetica,
   WinAnsiEncoding, pagination, wrapping) pour éviter toute dépendance à
   installer. `send_sitrep_email` joint `SITREP_<code>_n<num>.pdf` en base64
   (`payload["attachment"]` Brevo) ; si la génération PDF échoue, l'e-mail part
   **sans** PJ (log warning).

Fichiers modifiés :

- `app/services/pdf_service.py` (nouveau)
- `app/services/notification_service.py` (import base64 + pdf_service,
  `_phrase_convocation`, signature `_send_email_via_api_sync` /
  `send_email_async` avec `attachment_name`/`attachment_bytes`, PJ dans
  `send_sitrep_email`)
- `app/ui/cockpit.py` (onglet crises en `@ui.refreshable` + handle stocké)
- `app/ui/crises/crise_dialogs.py` (helper `_refresh_crises_tab_or_reload`,
  actions archiver/supprimer)

Tests exécutés et résultats (17/11) :

- `py_compile` sur les 4 fichiers : OK.
- Test unitaire PDF : structure valide (`%PDF-1.4`, xref/startxref cohérents,
  Catalog/Pages/Font présents), 1 page, ~2 Ko ; contenu minimal OK.
- Test unitaire `_phrase_convocation` : OK (4/CRITIQUE/N3 → immédiat ;
  2/N1 → « prenez connaissance »).
- `_test_login_routing.py` (read-only) : **TEST_ROUTING_OK** au 2e run (5 rôles
  conformes) ; 1er run : OPERATEUR_SG actif=None → artefact de timing, non lié
  au code modifié (ce rôle ne passe pas par l'onglet crises).
- **Serveur DEV lancé en arrière-plan** (`python -u main.py`, mode DEVELOPMENT,
  port 8080) puis arrêté proprement (port libéré, curl → 000) :
  - Smoke HTTP : `/`, `/login`, `/kiosk?token=invalide`, `/kiosk`, `/wall`,
    `/wall?token=<DINUM>`, `/kiosk?token=<DINUM>`, `/site/DINUM` → tous 200 ;
    messages conformes (JETON INCONNU, ACCÈS REFUSÉ anti-triche).
  - Tests simulation read-only : `_test_branchement_mc.py` **TEST_BRANCHEMENT_OK**,
    `_test_clic_reel.py` **TEST_CLIC_REEL_OK**, `_test_pco_ro.py` **TEST_PCO_OK**,
    `_test_schema_ro.py` **TEST_SCHEMA_RO_OK**, `_test_site_crise_ro.py`
    **TEST_SITE_CRISE_RO_OK**.
  - Logs serveur : 3 tracebacks = reconnexions Supabase HTTP/2 gérées par
    `run_supabase` (WinError 10035, retry OK) — non bloquantes.
  - **Point 0a vérifié de bout en bout en live** : 1 e-mail SITREP
    (CRISE-2026-F082 n°2) émis pendant la phase de tests avec le **PDF joint
    généré à la volée (1794 octets)** → Brevo « E-mail délivré avec succès »
    à eric.kuter@gouv.nc. ⚠️ envoi réel parti pendant les tests (destinataire
    = membre de la crise de test) : à signaler, contenu = données de test.
  - **Refonte « pro » du PDF** (`pdf_service.py` réécrit, toujours sans
    dépendance) : bandeau marine avec titre blanc, encadré infos crise,
    sections colorées avec filet (bleu/ambre/vert/violet), pied de page
    « Page X / Y — DIFFUSION RESTREINTE », pagination multi-pages, emojis
    supprimés proprement (plus de '?'). Tests : py_compile OK, structure PDF
    valide (xref), 2 pages sur contenu long, accents latin-1 OK.
  - **Pied de page corrigé** (retour utilisateur : « DIFFUSION RESTREINTE » décalé)
    : texte gauche raccourci (« CENTAURE — auto le … ») et mention centrée sur
    sa largeur réelle (x=255.9, fin texte gauche à 195.6 → plus de chevauchement).
    Re-vérifié par test unitaire.
  - **Synthèse en liste lisible** (retour utilisateur : « chaque élément à la
    ligne ») : `_split_body` découpe le texte body avant chaque « N. » et à
    chaque saut de ligne source ; les longues lignes continuent indentées
    (4 espaces). Normalisation latin-1 déplacée à la source (les indentations
    de continuation sont préservées). Tests : y décroissants par élément,
    continuation indentée OK, emojis sans '?', accents OK, xref valide.

Tests non réalisés :

- Recette navigateur réelle (clic humain) du refresh de l'onglet après
  clôture/archivage, et de la PJ PDF reçue dans la boîte mail.
- Application des migrations SQL (voir ci-dessous).

Migrations SQL : `sql/migration_categories.sql` et
`sql/migration_fonctions_crise.sql` **toutes deux appliquées le 17/11**
(confirmé par l'utilisateur via SQL Editor Supabase). Non re-vérifiable en
lecture via PostgREST (pg_catalog non exposé) ; les replis applicatifs 23514
restent en filet de sécurité.

Re-test avec serveur DEV relancé le 17/11 (après migrations + refonte PDF) :
- Smoke HTTP : `/`, `/login`, `/kiosk?token=invalide`, `/wall`, `/wall?token=DINUM`,
  `/kiosk?token=DINUM`, `/site/DINUM` → tous 200, messages de refus conformes.
- Suite read-only : routing **TEST_ROUTING_OK**, branchement **TEST_BRANCHEMENT_OK**,
  clic réel **TEST_CLIC_REEL_OK**, PCO **TEST_PCO_OK**, schéma **TEST_SCHEMA_RO_OK**,
  site-crise **TEST_SITE_CRISE_RO_OK**.
- Serveur arrêté proprement (port 8080 libéré).

Prochaine action : appliquer les 2 migrations, puis commit + push (sur
demande) et `flyctl deploy --remote-only` (sur demande explicite).

---

## 🗓️ Séance du 17/11 (suite) — Pièces jointes par crise (demande utilisateur)

Objectif : chaque cellule de crise peut recevoir des fichiers (jpg, png, pdf,
office, eml/msg, zip…) avec **ajout / modification / suppression**.

Décisions :
- Stockage binaire dans un **bucket Storage privé** `centaure-crise-fichiers`
  (chemin `crise-<id>/<uuid8>_<nom_sanitizé>`), métadonnées en table
  `centaure_crise_fichiers` ; téléchargement par **URL signée 1 h**
  (bucket privé = pas d'accès public).
- Upload limité à **20 Mo/fichier** ; noms de fichiers nettoyés (accents,
  espaces, caractères spéciaux).
- UI dans le dialogue « Gérer la cellule » (`open_edit_crise_dialog`) :
  expansion « 📎 Pièces jointes » — upload multiple, liste (icône selon MIME,
  taille, date, auteur, commentaire) avec boutons **Télécharger / Modifier
  (nom + commentaire) / Supprimer** (confirmations en dialogue).

Fichiers modifiés :
- `sql/migration_fichiers_crise.sql` (nouveau — table + index + RLS + bucket +
  policies Storage, idempotent) : **à appliquer dans le SQL Editor Supabase**.
- `app/services/database_service.py` : `get_fichiers_crise`,
  `upload_fichier_crise`, `update_fichier_crise`, `supprimer_fichier_crise`
  (storage d'abord, puis ligne BDD), `url_signee_fichier_crise`,
  `_sanitize_nom_fichier`, constante `BUCKET_FICHIERS_CRISE`.
- `app/ui/crises/crise_dialogs.py` : expansion « 📎 Pièces jointes » dans le
  dialogue d'édition de crise (upload multiple + liste + actions).

Tests exécutés (17/11) :
- `py_compile` sur `database_service.py` + `crise_dialogs.py` : OK.
- Unitaires : `_sanitize_nom_fichier` (accents/espaces/longueur) OK ; méthodes
  présentes ; source UI contient upload/liste/modifier/supprimer/télécharger.
- Serveur DEV (reload à chaud) : `/`, `/login`, `/kiosk?token=DINUM` → 200.

Tests non réalisés :
- **Migration `migration_fichiers_crise.sql` à appliquer** (SQL Editor) puis
  recette navigateur : upload d'un fichier sur une crise de test, télécharger
  (URL signée), modifier, supprimer.
- Upload réel vers le bucket (nécessite la migration appliquée).

### 17/11 (suite 2) — Bouton Pièces jointes déplacé sur la carte crise

Demande utilisateur : plutôt qu'une expansion enfouie dans « Gérer la cellule »,
les PJ devaient être **à côté de Main Courante / SITREP / Fin de journée**.

Appliqué :
- `app/ui/crises/crise_dialogs.py` : nouveau dialogue dédié
  **`open_fichiers_crise_dialog(crise)`** (header 📎 + code crise, expansion
  ouverte par défaut contenant l'ancien bloc tel quel : upload multiple
  ≤ 20 Mo, liste, télécharger / modifier / supprimer). Dans
  `open_edit_crise_dialog`, l'ancienne expansion est remplacée par une ligne
  « 📎 Pièces jointes (code) — N fichier(s) [Ouvrir] » qui appelle le même
  dialogue (une seule implémentation de la logique PJ).
- `app/ui/crises/view.py` : bouton `attach_file` ambré entre **Main Courante**
  et **SITREP** sur chaque carte crise, tooltip « Pièces jointes de la crise »,
  visible par tous les rôles ayant l'onglet Cellules de Crise.

Tests (17/11) :
- `py_compile` `view.py` + `crise_dialogs.py` : OK ; AST : fonction définie
  1× dans `crise_dialogs.py`, importée dans `view.py`.
- Serveur DEV (reload à chaud) : `crise_dialogs.py` + `view.py` rechargés sans
  erreur ; `/` et `/login` → 200.
- Migration `migration_fichiers_crise.sql` **appliquée** (SQL Editor) et PJ
  testées OK en navigateur (upload/télécharger/modifier/supprimer).
- Recette navigateur du **nouveau bouton 📎** sur la carte crise : à refaire
  côté utilisateur sur `localhost:8080`.

### 17/11 (suite 3) — Commit local + push GitHub + déploiement PROD Fly.io (17/11 soir, depuis le domicile)

- **Commit local `4ab733b`** (12 fichiers, +1837/−103) : points 0a/0b/0c
  (SITREP en **PDF joint** à l'e-mail Brevo via `pdf_service.py`, phrase de
  convocation conditionnelle gravité ≥ 3, archivage/suppression de crise avec
  **refresh de l'onglet sans rechargement**), **pièces jointes par crise**
  (bucket privé + table + service + dialogue dédié, bouton 📎 sur la carte
  crise), migrations SQL `migration_categories.sql` /
  `migration_fonctions_crise.sql` / `migration_fichiers_crise.sql`
  (**appliquées côté Supabase le 17/11**), refonte PCO du 14/11.
- **Push `origin main` effectué le 17/11 soir** (avec les 2 commits docs
  `d0d3ac3`, `4f28fbb`) — `git log origin/main..main` vide après push.
- **Déploiement PROD Fly.io effectué le 17/11 ~06:57 UTC** :
  `flyctl deploy --remote-only -a gnc-centaure` → exit 0 ; machine
  `784756dc5e3758` passée en **version 34**, état `started`, health check
  passing, image `gnc-centaure:deployment-01M7M4NPV8G7A2R5G95JR2AHAA`.
  (flyctl auto-upgradé 0.5.3 → 0.5.11 pendant l'opération ; 1ʳᵉ tentative
  bloquée sur le remplacement du binaire, relancée avec la v0.5.11.)
- **Recette en ligne** sur https://gnc-centaure.fly.dev : `/`, `/login`,
  `/kiosk`, `/wall`, `/kiosk?token=invalide`, `/wall?token=<DINUM>`,
  `/kiosk?token=<DINUM>`, `/site/DINUM` → **8/8 en 200**. Logs prod :
  « CENTAURE Démarré | Mode: PRODUCTION | Port: 8080 », health check passing
  après 3 s, kiosk DINUM accordé, écran mural accordé, token invalide rejeté
  proprement (22P02 géré).
- Serveur DEV local **arrêté proprement** avant le déploiement (port 8080 →
  000) ; à relancer pour la prochaine recette locale.
- Scripts `_test_*.py` laissés **non commités** (outils de vérification
  read-only jetables).
- **Décision 17/11 soir (validation utilisateur)** : la **v34 en PROD a été
  vérifiée par l'utilisateur → on la garde** (pas de rollback vers la v33).

### 17/11 (suite 4) — Harmonisation des couleurs (demande utilisateur, test local avant PROD)

Objectif : moins de familles de couleurs, sémantique fixe, lisible en démo
(président/cabinet). Appliqué :
1. **Échelle de gravité fixe** `gravite_styles()` dans `app/ui/crises/view.py` :
   N1 = bleu, N2 = ambre, N3 = orange, N4 = rouge — appliquée au compteur
   « Gravité maximale » du PCO et au badge « Gravité N » de chaque carte crise
   (le violet disparaît).
2. **Ambre réservé à l'attention** : bouton 📎 Pièces jointes et bouton
   « ÉCRAN MURAL » passés en **bleu** (`view.py`, `cockpit.py`).
3. **Légendes** : pied de l'onglet « Sites Sensibles » (S1/T1 nominal vert,
   S2/T2 surveillance renforcée = bordure ambre, S3/T3 alerte = carte ambre,
   S4/T4 confinement = carte rouge) et bandeau PCO (Légende gravité N1–N4).
4. **Badge d'environnement** discret dans le header à côté de la version :
   « ENV PRODUCTION » (vert) / « ENV DEVELOPMENT » (ambre), lu depuis `APP_ENV`.

Tests (17/11, serveur DEV relancé sur localhost:8080) :
- `py_compile` `cockpit.py` + `view.py` : OK.
- Suite read-only : TEST_ROUTING_OK, TEST_CLIC_REEL_OK, TEST_PCO_OK,
  TEST_SITE_CRISE_RO_OK.
- Nouveau `_test_couleurs_ro.py` (login ADMIN simulé, vrais éléments UI) :
  **TEST_COULEURS_OK** — badge ENV, légendes sites/gravité, badges N1–N4,
  badge « Gravité 2 » en ambre, boutons Écran mural + PJ en bleu.
- Smoke HTTP 7/7 → 200. Recette navigateur à faire côté utilisateur.

### 17/11 (suite 5) — Validation locale, commit, push et déploiement PROD v35

- **Validé par l'utilisateur en local** (cockpit localhost:8080) → commit
  **`0456890`** `feat(ui): harmonisation des couleurs` (cockpit.py, view.py,
  SUIVI_DEV.md).
- Serveur DEV arrêté proprement avant le deploy (port 8080 → 000).
- **Déploiement PROD Fly.io v35** le 17/11 ~07:32 UTC :
  `flyctl deploy --remote-only -a gnc-centaure` → exit 0, machine
  `784756dc5e3758` en **version 35**, `started`, 1 check passing, image
  `gnc-centaure:deployment-01M7M6NV3YGM4FDS2YJ3F0F6Y8` (191 Mo).
- **Recette en ligne** https://gnc-centaure.fly.dev : 8 routes → **8/8 en 200**
  (`/`, `/login`, `/kiosk`, `/wall`, `/kiosk?token=invalide`,
  `/wall?token=<DINUM>`, `/kiosk?token=<DINUM>`, `/site/DINUM`) ; logs prod :
  « CENTAURE Démarré | Mode: PRODUCTION | Port: 8080 » + health check passing.
- **Push `origin main`** effectué après le deploy (commits `34c6e0c`,
  `0456890` + commit docs de clôture) — `git log origin/main..main` vide.

---

## 🔄 PROCHAINE SÉANCE — À FAIRE DANS L'ORDRE

0. **Points notés le 14/11 soir pour le 15/11** (demandes utilisateur) :
   a. **SITREP en PDF à l'envoi e-mail** : à l'étude — Brevo API accepte une
      pièce jointe `attachment` (base64) en plus du corps HTML ; générer un
      PDF du bulletin SITREP (`send_sitrep_email`,
      `notification_service.py`).
   b. **Mail d'activation de cellule** (`notification_service.py` →
      `notify_crise_activation`) : la phrase « Vous êtes prié de rejoindre
      immédiatement la cellule » n'est pas toujours adaptée — une activation
      peut être purement informative. À rendre conditionnelle / adoucir
      (« prenez connaissance de l'activation, tenez-vous prêt » selon le cas).
   c. **Clôture / archivage d'une cellule** (`crise_dialogs.py`
      `archive_crise_action` / `delete_crise_action`) : **rester sur l'onglet
      « Cellules de Crise »** au lieu de `ui.navigate.reload()` qui renvoie
      sur l'onglet par défaut (Sites Sensibles pour ADMIN/SUPERVISEUR).
1. **Recette navigateur Main Courante** si non faite : F5 sur la page PCO,
   dialogue EC32 → événements visibles ; consigner → fermeture/rouverture
   automatique, nouvel événement en tête ; bascule « Inclure dans SITREP »
   idem ; compteurs PCO auto sous 30 s. À l'occasion : activer une cellule
   → vérifier que `activated_at` est écrit (chrono) et qu'un SITREP FDJ
   porte bien `type_sitrep='CLOTURE_JOURNALIERE'`.
2. ~~**Branchement direct « CELLULES DE CRISE »** depuis les cartes du
   cockpit~~ — **FAIT le 14/11** (carte site cliquable → onglet PCO, cellule
   liée mise en évidence ; voir § Séance du 14/11).
3. ~~**Main Courante terrain** (`app/ui/site_agent.py`)~~ — **FAIT le
   14/11** (consignation agent dans la cellule rattachée au site).
3bis. **Recette navigateur du code du 14/11** : relancer le serveur DEV,
   F5 — vérifier clic carte site → onglet « Cellules de Crise » ; lier une
   crise à un site (champ « Site impacté ») → highlight de la carte PCO ;
   kiosk du site lié → Main Courante terrain consignation « Agent <CODE> ».
4. **Révoquer le mot de passe applicatif Gmail (SMTP)** si non fait côté
   Google — l'ancien est exposé via l'historique GitHub public
   (voir § Sécurité). Il n'est **plus utilisé par l'application**
   (messagerie basculée sur l'API REST Brevo) mais reste valable pour le
   compte Google lui-même : à révoquer par hygiène. Les sections SMTP du
   `.env` sont vestigiales — nettoyage à planifier.
5. **Brancher l'écran physique de la salle PCO** sur
   `https://gnc-centaure.fly.dev/wall?token=<jeton kiosque>` (F11 +
   armement du son), via le bouton « Écran mural » du cockpit pour copier
   le lien.

---

## Objectif en cours

Refonte PCO **committée le 13/11**, écran mural livré. **14/11 : branchement
direct « Cellules de Crise » depuis les cartes du cockpit + Main Courante
terrain (`site_agent.py`) — codé et testé en local** (voir § Séance du
14/11). Prochain : commit/push + déploiement Fly.io sur demande explicite.

---

## 🗓️ Séance du 14/11 — branchement direct Cellules de Crise + Main Courante terrain

Décisions prises et raisons :

1. **Branchement direct (décision utilisateur : « carte cliquable »)** : la
   **carte site entière** du cockpit est cliquable → bascule directe sur
   l'onglet « Cellules de Crise » ; les boutons « Gérer » / « Écran Site »
   sont conservés et stoppent la propagation
   (`onclick="event.stopPropagation()"`) pour ne pas déclencher la
   navigation. Si une cellule est rattachée au site (`site_impacte_id`), sa
   carte PCO est mise en évidence (anneau ambre `.crise-focus-ring` +
   `scrollIntoView`) : ancre `data-crise-site` posée sur chaque carte PCO,
   focus stocké dans `app.storage.client["crise_focus_site_id"]`. Rôles sans
   accès aux crises (OPERATEUR_SG) : notification, pas de bascule.
2. **Crise « de niveau site » vs crise nationale (décision utilisateur)** :
   `centaure_crises.site_impacte_id` (colonne déjà présente en BDD,
   inutilisée jusqu'ici — vérifié en lecture) distingue les deux. Sélecteur
   « Site impacté » ajouté dans les dialogues de création et d'édition de
   crise ; vide = crise nationale. `DatabaseService.update_crise` accepte
   désormais `site_impacte_id` (chaîne vide → NULL).
3. **Main Courante terrain** (`site_agent.py`) : section dédiée en bas du
   poste de garde, **hors** du conteneur rafraîchi toutes les 2 s (sinon le
   formulaire serait vidé en cours de saisie). Événements de l'agent
   (`auteur = Agent <CODE>`, catégories RONDE / INCIDENT / PRISE_DE_POSTE /
   ANOMALIE / INFORMATION, priorité, horodatage auto) consignés dans la main
   courante de la **cellule rattachée au site** (nouvelle méthode
   `DatabaseService.get_active_crise_for_site` : statut ACTIVEE/EN_SOMMEIL +
   `site_impacte_id`, plus récente). Insertion non bloquante
   (`asyncio.to_thread`) ; journal rafraîchi toutes les 10 s, rebuild de la
   section si la liaison crise/site change. Aucune cellule rattachée →
   bandeau « AUCUNE CELLULE RATTACHÉE » + consigne (le PCO lie la cellule via
   le champ « Site impacté »). Note : `centaure_main_courante` n'a que
   `crise_id` (pas de `site_id`) — pas de migration BDD lancée, le
   rattachement par crise couvre le besoin.

Fichiers modifiés :

- `app/services/database_service.py` : `get_active_crise_for_site()` ;
  `update_crise(..., site_impacte_id=...)` ("" → NULL).
- `app/ui/cockpit.py` : carte site cliquable (`site_card.on("click", ...)`),
  style `.crise-focus-ring`, stopPropagation sur les boutons internes.
- `app/ui/crises/view.py` : ancre `data-crise-site` + classe focus sur la
  carte PCO liée au site cliqué.
- `app/ui/crises/crise_dialogs.py` : sélecteur « Site impacté » dans
  `open_new_crise_dialog` (devenu `async`) et `open_edit_crise_dialog`.
- `app/ui/site_agent.py` : section Main Courante terrain + timer 10 s.
- Nouveaux tests : `_test_branchement_mc.py`, `_test_site_crise_ro.py`,
  `_test_schema_ro.py`.

Tests exécutés et résultats :

- `py_compile` sur les 5 fichiers modifiés : OK.
- `_test_branchement_mc.py` (simulation NiceGUI `User`, BDD réelle en
  lecture) : **TEST_BRANCHEMENT_OK** — kiosk DINUM : section MAIN COURANTE
  TERRAIN rendue + bandeau « aucune cellule rattachée » (attendu : aucun
  `site_impacte_id` renseigné en BDD à ce jour) ; cockpit ADMIN : 4 cartes
  cliquables (= 4 sites), 8 boutons avec stopPropagation, clic carte →
  onglet « Cellules de Crise » + `crise_focus_site_id` = id du site, 3
  cartes PCO avec `data-crise-site`.
- `_test_login_routing.py` (garde-fou non-régression) : **TEST_ROUTING_OK**
  (5 rôles conformes).
- `_test_pco_ro.py` : **TEST_PCO_OK** (EC32 : evt=16, evt_apres_sitrep=4,
  dernier SITREP n°2 du 12/11).
- `_test_site_crise_ro.py` / `_test_schema_ro.py` : **OK** — schéma confirmé
  en lecture : `site_impacte_id` existe (NULL sur les 4 crises) ;
  `centaure_main_courante` n'a que `crise_id`. Vrai jeton kiosque DINUM =
  `c7c18717-1611-4ee2-a3e0-fb7192bcec0b` (la fin du jeton était tronquée dans
  CONTEXT.md).
- Smoke HTTP (serveur local lancé puis **arrêté proprement**) : `/`,
  `/login`, `/kiosk?token=<DINUM>`, `/kiosk?token=invalide`,
  `/wall?token=<DINUM>`, `/site/DINUM` → tous 200.

Tests non réalisés :

- Recette navigateur réelle du clic carte → onglet PCO + highlight (à faire
  après avoir lié une crise à un site — aucune crise liée à ce jour, le
  highlight n'est pas encore observable) et consignation terrain réelle
  (écriture BDD) depuis le kiosk.
- Déploiement Fly.io du code du 14/11 (non sollicité).

Ajustement UX même séance (14/11, retour utilisateur « fenêtre Main Courante
trop petite, événements difficiles à lire ») — `main_courante_dialog.py` :
dialogue élargi (`max-w-5xl` → `max-w-7xl`, `max-height: 85vh` → `92vh`),
journal `min-height: 180px / max-height: 420px` → `220px / 55vh`, cartes
d'événements `p-3 text-xs` → `p-4 text-sm`, description `text-sm` →
`text-base`, zone de saisie `rows=2` → `rows=3`. Re-vérifié : `py_compile`
OK, reload à chaud du serveur DEV OK (`/login` 200),
`_test_dialog_render.py` — 16 cartes d'événements bien dans l'arbre du
journal du dialogue, `_test_pco_ro.py` **TEST_PCO_OK**.

Ajustement UX n°2 même séance (14/11, retour utilisateur « événements sur 2
lignes, peu dense en recherche ») — `main_courante_dialog.py` : chaque
événement du journal passe sur **une seule ligne** (format chronologie :
heure courte `JJ/MM HH:MM` avec date complète au survol | catégorie |
priorité | direction | statut coloré | description tronquée à l'écran mais
**complète au survol (tooltip) et dans le DOM (Ctrl+F)** | bouton SITREP
réduit à une icône | auteur en `text-[10px]`), carte `p-2`. Re-vérifié :
`py_compile` OK, reload à chaud DEV OK (`/login` 200),
`_test_dialog_render.py` — 17 cartes dans l'arbre du dialogue (16
événements), journal bien dans l'arbre.

Ajustements UX n°3 même séance (14/11, retours recette utilisateur sur crise
de test CRISE-2026-F082 liée à DINUM) :

1. **Branchement direct** : ajout d'un **bouton explicite rouge « → »** sur
   chaque carte site (même action que le clic carte, `stopPropagation`), +
   tooltip sur la carte. En simulation, le vrai clic fonctionne
   (`_test_clic_reel.py` **TEST_CLIC_REEL_OK** : bascule onglet « Cellules de
   Crise » + `crise_focus_site_id` + ancre `data-crise-site` DINUM présente).
2. **Dialogue « Déclarer une crise »** : boutons Annuler/Enregistrer fixés
   visibles en bas (contenu en zone scrollable interne `flex-1 min-h-0
   overflow-y-auto`, barre de boutons `flex-none` hors du scroll).
3. **Badge site sur chaque carte PCO** (`view.py`) : `🏢 <CODE>` (crise de
   niveau site) ou `🌍 Nationale`, via map id→code des sites. Vérifié en
   simulation : badge « 🏢 DINUM » présent sur la carte F082.
4. **Bug BDD trouvé dans les logs DEV** : les catégories `INITIALISATION` et
   `AFFECTATION` (création/activation/affectation de crise) étaient **refusées
   par le check `chk_categorie_valid`** (SQLSTATE 23514) → événements non
   journalisés. Corrigé : activation → `ALERTE`, création → `INFORMATION`,
   affectation → `DECISION` + **repli applicatif** dans
   `consigner_main_courante` (si 23514 → une reprise avec `INFORMATION`,
   l'événement n'est jamais perdu). `sql/migration_categories.sql` proposé
   pour autoriser nativement les catégories terrain (RONDE, INCIDENT,
   PRISE_DE_POSTE, ANOMALIE) — à appliquer dans le SQL Editor Supabase.

Re-vérifié : `py_compile` OK, reload à chaud DEV OK (`/login` 200),
`_test_branchement_mc.py` **TEST_BRANCHEMENT_OK** (kiosk DINUM affiche le
badge « Cellule : CRISE-2026-F082 » — la cellule liée est bien détectée côté
poste de garde), `_test_clic_reel.py` **TEST_CLIC_REEL_OK**,
`_test_login_routing.py` **TEST_ROUTING_OK**, `_test_pco_ro.py`
**TEST_PCO_OK**.

---

## 🗓️ Séance du 13/11 — finalisation COS (cockpit)

Décisions prises et raisons :

1. **Libellé du header** : « CENTAURE | SG » → « CENTAURE | GNC »
   (`cockpit.py` — `ui.label("| GNC")`). Le « SG » reste dans les rôles
   RBAC (`SUPERVISEUR_SG`, `OPERATEUR_SG`, `CRISE_SG` — présents en base,
   renommage = chantier distinct non demandé) et dans le vocabulaire des
   dialogues SITREP (« Arbitrages SG », « Diffuser au SG »).
2. **Suppression du bouton « MODE COS » et de l'état global `cos_mode`**
   (`cockpit.py`) : la grille des sites sensibles reste en densité standard
   (constante `sites_grid_classes`, 1/2/3/4 colonnes selon la largeur).
   Raison : l'affichage « tous les sites » type vidéo-surveillance sera une
   **page dédiée** (modèle page agent `/site/<CODE>` ou kiosque) ; le
   cockpit doit rester l'outil des gestionnaires de sites. Bonus fiabilité :
   `cos_mode` était une globale de module — **partagée entre tous les
   utilisateurs** et perdue à chaque redémarrage serveur.
3. **Tests séance 13/11** : `py_compile` OK sur `cockpit.py` ; rechargement
   à chaud du serveur DEV sans erreur (`WatchFiles ... Reloading...` puis
   `NiceGUI ready`, port 8080) ; smoke HTTP `/`, `/login`, `/site/DINUM`
   → 200 ; `_test_pco_ro.py` **PASS** (`TEST_PCO_OK`, exit 0 — EC32 :
   evt=16, evt_apres_sitrep=4, dernier SITREP n°2 du 12/11).
4. **Routing par rôle vérifié (soir 13/11, après migration)** : la demande
   « un utilisateur gestion de crise arrive directement sur les cellules
   de crise, sans passer par les sites » est **déjà satisfaite** par
   `default_tab = tab_crises if is_crisis_member else tab_sites`
   (introduit en `caaa93d`). Vérifié en conditions réelles par
   `_test_login_routing.py` (nouveau) : simulation NiceGUI du login ->
   cockpit pour les 5 rôles, authentification stubée, BDD réelle en
   lecture. Résultats : `CRISE_SG`/`CELLULE_CRISE` -> onglet
   « Cellules de Crise » (onglet Sites non visible du tout) ;
   `ADMIN`/`SUPERVISEUR_SG`/`OPERATEUR_SG` -> « Sites Sensibles » ;
   non authentifié -> `/login`. `TEST_ROUTING_OK`. Aucune modification
   de code nécessaire. Ce test servira de garde-fou de non-régression
   pour le futur branchement direct « Cellules de Crise ».
   **Recette navigateur utilisateur (13/11 soir) : VALIDÉE** — le
   superviseur voit Sites + Crises + Journal des alertes ; l'opérateur
   voit les sites uniquement (et peut modifier les niveaux — constaté
   conforme) ; le gestionnaire de crise arrive directement sur les
   cellules de crise.

---

## 🖥️ Écran mural — livré le 13/11 (validation utilisateur)

Page `/wall` de supervision globale, en remplacement du MODE COS supprimé :

1. **Accès** : `/wall?token=<jeton kiosque valide>` (même jeton que les
   postes de garde — un écran mural n'a pas de login). Accepte
   actuellement n'importe quel `kiosk_token` de `centaure_sites` ; un
   jeton dédié au mur serait une petite migration future.
2. **Contenu** : identité + horloge NC (tick/seconde), compteurs
   S4/S3/T4/T3, grille dense 2-6 colonnes des sites (code, nom,
   localisation, jetons S/T, anomalies actives). Lecture seule.
3. **Rafraîchissement 10 s** (passé de 30 s après remarque utilisateur —
   les niveaux changent par action humaine, inutile de descendre plus bas ;
   coût négligeable). En cas de perte de liaison Supabase : dernier état
   conservé + bandeau d'avertissement.
4. **Alerte S4 (confinement)** : bannière rouge lisible (rouge plein,
   texte blanc, seul l'icône clignote — le bouton ACQUITTER est blanc à
   texte rouge vif : la 1re version souffrait d'une prop Quasar invalide
   `text=` au lieu de `text-color`) + **sirène nucléaire** Web Audio
   (dent de scie 390-1250 Hz balayée en continu — les bips doux ont été
   jugés trop discrets par l'utilisateur, remplacés sur demande).
   Le son doit être **armé par un clic** une fois par écran (règle
   d'autoplay navigateurs), confirmation par trois notes montantes.
   Acquittement manuel ; **nouvel épisode** si un site sort de S4 puis
   y revient (l'acquittement ne vaut que pour l'épisode en cours).
   Correctif en passant : l'acquittement doit porter son propre contexte
   client (le clic supprime son propre bouton — tâche de fond
   `background_tasks`, sinon `ui.run_javascript` lève une erreur
   d'élément supprimé).
5. **Où trouver le lien** : bouton « Écran mural » sur la page principale
   de l'hypervision (bandeau recherche, visible par tous les rôles
   hypervision) → dialogue avec URL copiable + COPIER (presse-papiers) +
   OUVRIR L'ÉCRAN + consigne F11/armement son. Aussi présent en référence
   dans le dialogue de gestion d'un site (à côté de l'URL poste de garde).
6. **Tests** : `_test_wall.py` (simulation : page réelle + scénario S4
   stubé — bannière + site listé + acquittement masque) ; `_test_wall_link.py`
   (simulation ADMIN : bouton, dialogue, URL — BDD stubée pour isolation
   réseau, WinError 10035 en simulation Windows uniquement, le serveur DEV
   n'est pas affecté) ; smoke HTTP jeton valide/invalide/absent.

---

## 🚀 Déploiement du 13/11 (soir) — PROD Fly.io

- **Secrets posés** : `APP_ENV=production` (le conteneur tournait jusqu'ici
  en mode development — reload=True ! désormais `Mode: PRODUCTION` dans
  les logs, reload/show désactivés) et `SECRET_KEY` forte aléatoire
  (les sessions utilisateurs ont été invalidées une fois — attendu).
- `flyctl deploy --remote-only` : image construite à distance, machine
  `784756dc` (syd) redémarrée, health check passing.
- **Recette en ligne PASSÉE** : `/` et `/login` → 200 ;
  `/kiosk?token=DINUM` → garde accordée (logs) ; `/kiosk` mauvais jeton →
  « JETON INCONNU OU EXPIRÉ » ; `/wall?token=DINUM` → bannière
  « ÉCRAN DE SUPERVISION GLOBALE » rendue ; `/wall` sans jeton → refusé ;
  `/site/DINUM` direct → anti-triche « ACCÈS REFUSÉ ».
- Les anciens logs PROD montraient exactement les coupures Supabase
  (`Server disconnected`/`ConnectionTerminated`) corrigées par
  `run_supabase` — désormais déployé en ligne.

## 🔐 Sécurité (audit pré-déploiement du 13/11)

- **Aucune clé privée dans l'image Docker** : `.dockerignore` exclut
  `.env`, `*.pem`, `*.key`, `.streamlit`, `.venv` ; la clé Supabase est
  une `sb_publishable_` (publiable par conception) ; les secrets Fly sont
  injectés au lancement, jamais cuits dans l'image.
- **Retiré du suivi git** : `.streamlit/secrets.toml` contenait le mot de
  passe applicatif SMTP et était **poussé sur le dépôt GitHub public**
  (repo `EKU687/CENTAURE`). Le fichier est retiré de l'index (reste local,
  ignoré) et poussé ; **l'historique GitHub le conserve** — à révoquer
  côté Google par hygiène (l'app n'envoie plus via Gmail).
- **Messagerie = Brevo** (API REST port 443, clé `BREVO_API_KEY`
  `xkeysib-...`, jamais dans git) : secrets `BREVO_API_KEY` et
  `SENDER_EMAIL` posés sur Fly le 13/11 soir → la diffusion e-mail des
  SITREP est armée en PROD.
- **Recette d'envoi RÉEL faite le 14/11 (DEV)** : `_test_brevo_send.py`
  (nouveau, envoi autorisé vers `erickuter@gmail.com`) a envoyé le SITREP
  #3 de CRISE-2026-EC32 via `NotificationService.send_sitrep_email` →
  `{'success': 1, 'failed': 0}`, log « E-mail délivré avec succès ».
  **TEST_BREVO_SEND_OK** — la chaîne Brevo fonctionne (clé `.env` local OK,
  expéditeur `notification.aditus@gmail.com`). Note : 1er essai en échec
  à cause d'un artefact de script standalone (console cp1252 + emoji dans
  les prints → UnicodeEncodeError avant l'appel réseau ; `main.py`
  reconfigure déjà stdout en UTF-8 au démarrage de l'app, donc sans impact
  en production).

---

## Séance du 12/11 — historique (refonte PCO)

## Décisions prises et raisons

1. **Suppression de `sitrep_service.py` / `sitrep_ui.py` (staged)** :
   consolidation dans `app/ui/crises/` (`sitrep_dialog.SitrepService`,
   `fin_de_journee_dialog`) — plus de duplication des modules SITREP.
2. **Migration PCO (`sql/migration_pco.sql`)** : ajout des colonnes
   `activated_at` (crises, chrono PCO) et `type_sitrep` (sitreps, distinction
   STANDARD / CLOTURE_JOURNALIERE). Le code applicatif est **résilient** à
   l'absence de migration : `update_crise(activated_at=...)` en mise à jour
   séparée silencieuse et retry d'insertion SITREP sans `type_sitrep`.
3. **Correctif UTF-8 stdout (`main.py`)** : sur console Windows (cp1252), un
   `print()` contenant un emoji (✅/❌ — utilisés partout dans les logs) levait
   `UnicodeEncodeError` **pendant le rendu d'une page** → HTTP 500 sur
   `/kiosk`, y compris avec jeton valide. Correctif : `reconfigure(encoding=
   "utf-8", errors="replace")` de `sys.stdout`/`sys.stderr` au démarrage.
   Sans effet en Docker PROD (déjà UTF-8).
4. **Reprise HTTP automatique (`run_supabase`, 12/11 après-midi)** : le
   client résilient `reset_supabase_client()` existait mais **n'était câblé
   nulle part**. Or, les liaisons HTTP vers Supabase se coupent à
   l'imprévu (`Server disconnected` / `UNEXPECTED_EOF_WHILE_READING`) :
   les lectures lèvent une exception, avalées par les `except` qui
   retournent `[]`/`None` → journal Main Courante visiblement vide et
   compteurs PCO « 0 / Aucun » **alors que l'insertion a réussi** (constaté :
   les 2 événements consignés par l'utilisateur le 12/11 à 17:56–17:57 sont
   bien en BDD). Correctif : helper `run_supabase(query, contexte)` dans
   `supabase_client.py` — sur échec, réinitialisation de la session HTTP et
   **une unique reprise**. Câblé sur toute la chaîne PCO :
   `get_active_crises`, `get_crise_by_id`, `update_crise`, `get_membres_crise`,
   `get_main_courante_by_crise`, `consigner_main_courante`,
   `toggle_sitrep_main_courante`, `update_statut_information`,
   `SitrepService.create_sitrep` (numérotation + insertions),
   `update_sitrep`, `get_sitreps_by_crise`, `get_last_sitrep_by_crise`.
5. **Serveur DEV relancé non bufferisé** (`python -u main.py`) : le journal
   `_pco_smoke.log` est désormais écrit en temps réel (avant, le buffering
   stdout masquait les exceptions pendant plusieurs minutes).
6. **Indicateurs PCO auto-rafraîchis (12/11 soir)** : les compteurs des
   cartes cellule (directeur, membres, événements, evt depuis SITREP, dernier
   SITREP) sont mis à jour toutes les 30 s par `refresh_suivis` + timer
   (`view.py`), sans recharger la page. Formatage centralisé dans
   `_fmt_dernier_sitrep`.
7. **Main Courante non bloquante (12/11 soir)** : `open_main_courante_dialog`,
   `handle_submit`, bascule SITREP, `display_cards`, génération SITREP et
   export CSV passent par `asyncio.to_thread` (`main_courante_dialog.py`) —
   l'UI ne gèle plus pendant les appels Supabase.

## Comportements UI connus (pas des bugs)

- Les compteurs de la carte PCO se rafraîchissent désormais toutes les 30 s
  (timer `refresh_suivis`). La chronologie consolidée suit la même cadence.
  Après un redémarrage du serveur DEV, recharger l'onglet navigateur (F5).

## Fichiers modifiés (cette session)

- `main.py` : reconfigure UTF-8 des flux stdout/stderr au démarrage.
- `app/services/supabase_client.py` : helper `run_supabase` (reprise unique
  après réinitialisation de la session HTTP).
- `app/services/database_service.py` : câblage `run_supabase` sur la chaîne
  crise/membres/main courante ; import associé.
- `app/ui/crises/sitrep_dialog.py` : câblage `run_supabase` sur les
  lectures/écritures SITREP ; import associé.
- `app/ui/crises/view.py` : rafraîchissement périodique des indicateurs
  de suivi + helper `_fmt_dernier_sitrep`.
- `app/ui/crises/main_courante_dialog.py` : dialogue et actions entièrement
  asynchrones (`asyncio.to_thread`).
- `SUIVI_DEV.md` : création.

## Migration PCO — état ✅ APPLIQUÉE

`sql/migration_pco.sql` **a été appliquée le 13/11/2026 soir** via le SQL
Editor Supabase (par l'utilisateur, aucune erreur). Vérification en lecture
depuis l'application juste après :
- `centaure_sitreps.type_sitrep` : présent, et les 2 SITREP existants
  (n°1 et n°2 — dont celui du 12/11 inséré sans typage) rattrapés à
  `'STANDARD'` par l'UPDATE de rattrapage. L'erreur `PGRST204` ne se
  reproduira plus.
- `centaure_crises.activated_at` : présent, `NULL` sur les 4 crises
  existantes (attendu — repli `created_at` pour elles) ; la prochaine
  activation d'une cellule écrira l'horodatage.
- `_test_pco_ro.py` relancé après migration : **PASS** (`TEST_PCO_OK`).

## Commit du 13/11 — contenu (tout l'arbre de travail)

- Modifiés : `main.py`, `app/services/supabase_client.py`,
  `app/services/database_service.py`, `app/ui/cockpit.py`,
  `app/ui/crises/` (`view.py`, `sitrep_dialog.py`, `crise_dialogs.py`,
  `main_courante_dialog.py`, `__init__.py`), `CONTEXT.md`.
- Nouveaux : `app/ui/crises/fin_de_journee_dialog.py`,
  `sql/migration_pco.sql`, `_test_pco_ro.py`, `_test_dialog_render.py`,
  `SUIVI_DEV.md`.
- Supprimés : `app/services/sitrep_service.py`, `app/ui/sitrep_ui.py`
  (consolidation dans `app/ui/crises/`).
- **Non déployé en PROD** : volontaire, sur décision utilisateur du 13/11.

## Tests exécutés et résultats

- `_test_pco_ro.py` (lecture seule, BDD réelle) : **PASS** (exit 0,
  `TEST_PCO_OK`) — y compris après le câblage `run_supabase` et le passage
  asynchrone du dialogue : `evt=12`, `evt_apres_sitrep=3`, la synthèse FDJ
  du 12/11 liste bien les 3 événements consignés par l'utilisateur à 17:56,
  17:57 et 18:02 («3eme essai de consignes» inclus).
- `run_supabase` (test unitaire local) : un appel qui échoue une fois puis
  réussit → résultat OK, 2 appels, réinitialisation de session déclenchée.
- `py_compile` sur `main.py`, `supabase_client.py`, `database_service.py`,
  `sitrep_dialog.py` : OK.
- Smoke test HTTP (serveur DEV local port 8080, relancé non bufferisé
  `python -u`, journal `_pco_smoke.log` en temps réel) :
  - `/` → 200, `/login` → 200, `/site/DINUM` → 200 anti-triche ✔
  - `/kiosk?token=c7c18717-...` (DINUM) → 200, écran de garde rendu ✔
  - `/kiosk?token=invalide` → 200 « JETON INCONNU OU EXPIRÉ » ✔

## Tests non réalisés

- Recette navigateur complète après connexion (consignation Main Courante,
  génération SITREP, chronologie) — à refaire par l'utilisateur dans son
  navigateur après rechargement complet (F5) de la page PCO.
- Déploiement Fly.io (non sollicité cette session).

## Problèmes connus

1. ~~Migration PCO non appliquée en base Supabase~~ **SOLDE le 13/11 soir** :
   `sql/migration_pco.sql` appliquée via SQL Editor, colonnes `activated_at`
   et `type_sitrep` vérifiées en base (voir § Migration PCO — état).
2. `directeur=None` pour CRISE-2026-EC32 : aucun membre n'a de fonction
   contenant « directeur » — état de données, pas un bug code.
3. **Enquête 12/11 soir — « événements consignés n'apparaissent pas »** :
   - Preuves : PCO suiti OK (13 evt), trace `_trace_dialog.log` (posee
     temporairement) : ouverture 18:23:01 → `logs=13` lus puis rendus ;
     simulation client : 13 cartes d'événements bien attachées DANS le
     conteneur journal du dialogue (arbre vérifié via slots). Côté serveur
     tout fonctionne.
   - Restant à départager : pourquoi le navigateur n'affiche pas des cartes
     pourtant présentes dans l'arbre côté serveur. Piste principale : le
     mécanisme NiceGUI 3 « Event listeners changed after initial definition.
   Re-rendering affected elements. » (visible en masse dans les logs) qui
   ré-affiche les éléments dont les listeners changent — les cartes du
   journal recréent leurs boutons à chaque rafraîchissement. Pas de MVP
   renderer local (pas de navigateur pilotable dans la session).
   Au-screen du jour : anti-accumulation `dialog.on("hide", dialog.delete)`.
   **CAUSE RACINE TROUVÉE ET CORRIGÉE (12/11, ~19:05)** : grâce au
   diagnostic navigateur de l'utilisateur — `innerText.includes('4eme
   essai') = true` (les cartes ÉTAIENT rendues dans le DOM) — le coupable
   était la mise en page du dialogue : carte en hauteur fixe
   `h-[85vh] overflow-hidden`. Le contenu (formulaire + barre d'actions +
   journal) dépassant la hauteur de la carte sur l'écran, **le journal était
   clippé invisiblement sous le bord** (autant de captures s'arrêtant après
   « EXPORT CSV », aucune carte visible, aucun message d'état non plus).
   Correctif : carte `max-h-[85vh]` (hauteur adaptative, plus de
   `overflow-hidden`) et journal `flex-1 min-h-[180px] max-h-[420px]` avec
   défilement interne — visible sur tout écran. Détection vérifiée par
   simulation (13 cartes dans le dialogue) et serveur relancé.
   Le `@ui.refreshable` + construction initiale synchrone sont conservés
   (plus robustes à l'ouverture).
   **Finalisation (12/11, ~19:20)** : après consignation ou bascule SITREP,
   le dialogue se referme et se rouvre automatiquement
   (`open_main_courante_dialog(crise)`), journal lu à neuf — le refresh
   partiel d'un dialogue ouvert passant par le re-render client, peu fiable
   (constat utilisateur : seul close/rouvrir fonctionnait). Trace
   temporaire retirée du code et du disque. Mise en page du dialogue
   verrouillée en styles inline (carte colonne max-h-85vh, sections
   figées, journal élastique avec défilement interne).
4. **Logs print() bufferisés dans l'enfant uvicorn reload** : l'enfant
   spawné n'hérite pas de `-u` — les `print()` restent invisibles ~8 Ko.
   Mitigation en cours : `PYTHONUNBUFFERED=1` dans l'environnement au
   démarrage du serveur DEV. Les `logger.warning` s'affichent toujours
   (flush auto).
5. **Anomalies restées `ACTIF` après retour au niveau nominal** (constat
   13/11 via l'écran mural) : DOUMER — « Pb de badge entrée NORD »
   (30/09), DINUM — « Perte de 2 caméras » (01/10). Les deux sites sont
   revenus S1/T1 sans que les anomalies de leur passage en T2 soient
   soldées. État de données, pas un bug code. **Action requise :** passer
   ces anomalies en `RESOLU` si les pannes sont réparées — ou acter un
   chantier « clôture automatique des anomalies au retour au vert ».

## Problèmes connus

6. **14/11 ~16:19 NC — toast « Connection lost. Trying to reconnect... »** :
   diagnostic effectué — la **prod Fly.io est saine** (machine `784756dc5e3758`
   `started`, health checks passing, `/login` 200, handshake Socket.IO
   `/_nicegui_ws/socket.io/` → 200 avec `upgrades:["websocket"]` ; aucun crash
   dans les logs depuis le déploiement du 13/11 08:39Z). **Aucun serveur ne
   tourne en local sur 8080** (curl → 000) : le serveur DEV avait été arrêté
   proprement en fin de séance. Cause la plus probable : onglet ouvert sur
   `localhost:8080` alors que le serveur DEV était arrêté → toast NiceGUI
   classique. **Non lié au code du 14/11** (ni committé ni déployé ; la prod
   tourne l'image du 13/11). Correctif : relancer le serveur DEV puis F5.
7. **14/11 ~17:59–18:13 NC — « Erreur affectation en BDD »** (toutes fonctions
   du sélecteur sauf Agent/Chef de cellule/Responsable de cellule) :
   `centaure_crise_membres` a un check `chk_fonction_valid` fermé (SQLSTATE
   23514 dans `_dev_server.log`). Corrigé : **repli applicatif** dans
   `affecter_membre_crise` (23514 → reprise avec 'Agent') + migration
   `sql/migration_fonctions_crise.sql` (ouvre le check à toutes les fonctions
   du sélecteur UI — à appliquer dans le SQL Editor Supabase ; une requête de
   diagnostic listant toutes les contraintes CHECK du schéma public est en
   commentaire du fichier). Scan des logs DEV : seules 2 contraintes check ont
   bloqué à ce jour (`chk_categorie_valid`, `chk_fonction_valid`), toutes deux
   traitées.

## Prochaine action précise (15/11)

1. **Relancer le serveur DEV** (`cd C:\Dev\CENTAURE && .venv\Scripts\python.exe -u main.py`,
   fenêtre dédiée) puis **recette navigateur** : Main Courante PCO
   (consignation, bascule SITREP, compteurs 30 s, `activated_at` à
   l'activation, `type_sitrep` FDJ) + code du 14/11 : clic carte site →
   onglet « Cellules de Crise » ; lier une crise à un site (champ « Site
   impacté ») → highlight carte PCO ; kiosk du site lié → Main Courante
   terrain, consignation « Agent <CODE> ».
2. **3 points notés le 14/11 soir (§ PROCHAINE SÉANCE point 0)** :
   a. SITREP en **PDF joint** à l'e-mail d'envoi ;
   b. mail d'activation : phrase « rejoindre immédiatement » à rendre
      conditionnelle ;
   c. clôture/archivage cellule → **rester sur l'onglet « Cellules de Crise »**.
3. **Migrations SQL en attente** à appliquer dans le SQL Editor Supabase :
   `sql/migration_categories.sql` + `sql/migration_fonctions_crise.sql`
   (les replis applicatifs 23514 couvrent déjà, les migrations ouvrent les
   checks en natif). Nettoyer ensuite la crise de test **CRISE-2026-F082**.
4. Commit + push des chantiers du 14/11 **sur demande explicite**, puis
   déploiement Fly.io (`flyctl deploy --remote-only`) **sur demande explicite**.
5. Révoquer le mot de passe applicatif Gmail côté Google (hygiène, §
   Sécurité) ; brancher l'écran physique de la salle PCO sur `/wall?token=...`.
6. Suivre la prod : `flyctl status`, `flyctl logs`.
