# 🛡️ CENTAURE — Bilan Victoire PROD & Feuille de Route Métier

**Date de reprise :** Demain matin (Environnement Bureau / Multi-écrans)  
**Statut Global :**  **PRODUCTION STABLE & VALIDÉE**  
**Hébergement :** Fly.io (`https://gnc-centaure.fly.dev` — Région Sydney `syd`)  
**Base de données :** Supabase (`centaure_sites`, `centaure_protocoles`, sessions)  
**Architecture UI :** NiceGUI (FastAPI + WebSockets)  

---

## 1. 🏆 Rétrospective des Victoires Techniques (Session d'aujourd'hui)

La session d'aujourd'hui a permis de résoudre définitivement les blocages d'infrastructure et de connectivité qui provoquaient les coupures récurrentes (`Connection lost` / plantages serveur) :

### A. Résolution du tueur silencieux : Crash OOM (Out Of Memory)
* **Constat dans les logs :** Le conteneur Linux de Fly.io s'arrêtait brutalement avec `Out of memory: Killed process (python)`. La configuration par défaut de 256 Mo était insuffisante pour le runtime Python 3.11 combiné à NiceGUI, Uvicorn et les requêtes Supabase.
* **Correction appliquée :** Mise à l'échelle de la mémoire à **512 Mo** via `flyctl scale memory 512 -a gnc-centaure`. Le conteneur dispose désormais de la marge nécessaire pour encaisser la charge sans crash.

### B. Stabilisation du Pool de Connexions Supabase (HTTP/2 Resilience)
* **Constat dans les logs :** Présence d'erreurs en cascade (`Server disconnected`, `<ConnectionTerminated error_code:1>`, `SSL: UNEXPECTED_EOF_WHILE_READING`). Les liaisons HTTP/2 inactives (*idle*) étaient prématurément rompues entre Sydney et l'infrastructure Supabase.
* **Correction appliquée :** Refonte de `app/services/supabase_client.py` avec :
  - L'intégration de `ClientOptions` avec timeouts explicites (15 s).
  - La mise en place d'un wrapper dynamique (`SupabaseProxy`) et d'une routine de reconnexion à chaud (`reset_supabase_client`).

### C. Assainissement du Routage et de l'Accès Kiosque 24/7
* Élimination du doublon de route `@ui.page('/kiosk')` dans `main.py`.
* Validation bout-en-bout du jeton UUID Kiosque DINUM (`c7c18717-1611-4ee2-a3e0-fb7192bcec0b`).
* Verrouillage anti-triche fonctionnel : accès direct par URL refusé sans jeton préalable dans `app.storage.client`.

---

## 2. 📌 État Actuel du Projet

| Composant | Statut | Emplacement / Référence |
| :--- | :---: | :--- |
| **Conteneur Fly.io** | **Passant (Health checks OK)** | 512 Mo RAM / TCP 8080 |
| **Client Supabase** | **Résilient** | `app/services/supabase_client.py` |
| **Cockpit Central** | **Opérationnel** | `https://gnc-centaure.fly.dev/` |
| **Poste de Garde DINUM** | **Opérationnel** | `https://gnc-centaure.fly.dev/kiosk?token=...` |
| **Dépôt Git** | **Propre & synchronisé** | `main` à jour, `.gitignore` blindé |

---

## 3. 🎯 Ordre du Jour pour Demain (Développement Métier)

Grâce au confort de ton poste de travail multi-écrans au bureau, nous basculons entièrement sur la **valeur opérationnelle terrain**.

### Chantier 1 : La Main Courante Terrain (`app/ui/site_agent.py`)
* **Objectif :** Permettre à l'agent de poste DINUM de consigner en direct les événements du site.
* **Tâches clés :**
  1. Conception de l'interface de saisie rapide (Horodatage automatique, Catégories : Ronde, Incident, Prise de poste, Anomalie).
  2. Liaison avec la table Supabase dédiée à la main courante (insertion asynchrone non-bloquante).
  3. Rafraîchissement réactif du tableau d'événements sans rechargement de page.

### Chantier 2 : Le Déclenchement & Traitement des Crises (`cockpit.py` & `app/ui/crises/`)
* **Objectif :** Gérer l'élévation des postures de sûreté (S1 à S4) depuis le Cockpit sans rupture WebSocket.
* **Tâches clés :**
  1. Sécurisation du callback de passage en alerte S4 (encapsulation `try...except` et vérification de la présence du client avant mise à jour UI).
  2. Propagation temps réel du changement de posture vers le Kiosque DINUM connecté.
  3. Affichage immédiat des consignes et du protocole de confinement rattaché sur l'écran de garde.

---

## 4. 🚀 Commandes de Reprise Rapide Demain

Dès ton arrivée au bureau :

```powershell
# 1. Ouvrir le répertoire du projet
cd C:\Dev\CENTAURE

# 2. Activer l'environnement
.\.venv\Scripts\Activate.ps1

# 3. Vérifier le statut de la production en direct
flyctl status -a gnc-centaure

# 4. Écouter les logs Fly.io dans un terminal dédié
flyctl logs -a gnc-centaure
```

Le socle est solide, les pièges d'infrastructure sont désamorcés. Repose-toi bien ce soir et rendez-vous demain pour coder le cœur métier sur tes écrans !