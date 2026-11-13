# 📋 CENTAURE — Suivi de Développement

**Dernière mise à jour :** 13/11/2026 soir (suite) — SÉANCE COS + MIGRATION +
**CHANTIER ÉCRAN MURAL LIVRÉ** (page /wall, alerte S4 sonore, lien exposé)
**Branche :** `main` — refonte PCO + correctifs session 12/11 + fin COS
**committés le 13/11** ( Serveur DEV tournant en arrière-plan de la
session ; migration Supabase SQL appliquée ce soir ; pas de mise en PROD,
sur décision utilisateur )

---

## 🔄 PROCHAINE SÉANCE — À FAIRE DANS L'ORDRE

1. **Recette navigateur Main Courante** si non faite : F5 sur la page PCO,
   dialogue EC32 → événements visibles ; consigner → fermeture/rouverture
   automatique, nouvel événement en tête ; bascule « Inclure dans SITREP »
   idem ; compteurs PCO auto sous 30 s. À l'occasion : activer une cellule
   → vérifier que `activated_at` est écrit (chrono) et qu'un SITREP FDJ
   porte bien `type_sitrep='CLOTURE_JOURNALIERE'`.
2. **Branchement direct « CELLULES DE CRISE »** depuis les cartes du
   cockpit (à la place des dialogues de gestion actuels).
3. **Main Courante terrain** (`app/ui/site_agent.py`).
4. **Déploiement Fly.io** : pas avant validation utilisateur explicite.
   Au déploiement : vérifier `APP_URL` (utilisée pour générer les URL
   kiosque/murale affichées dans le cockpit).

---

## Objectif en cours

Refonte PCO **committée le 13/11**. Prochains chantiers : page « écran
mural » dédiée, branchement direct « Cellules de Crise », Main Courante
terrain (`app/ui/site_agent.py`).

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

## Prochaine action précise

1. Recette navigateur Main Courante (si non déjà faite ce 13/11) — à
   l'occasion, vérifier `activated_at` écrit à la prochaine activation et
   `type_sitrep` sur un nouveau SITREP FDJ.
2. Chantier suivant au choix : branchement direct « Cellules de Crise »
   depuis le cockpit, ou Main Courante terrain (`app/ui/site_agent.py`).
3. Déploiement Fly.io : seulement sur demande explicite.
