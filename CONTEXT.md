# 📄 RÉSUMÉ DE CONTEXTE — PROJET CENTAURE

---

## 1. Intention & Architecture du Projet
* **Projet** : CENTAURE – Plateforme d'hypervision et de gestion de crise stratégique (SG).
* **Tech Stack** :
  * **Python** (3.11+)
  * **NiceGUI** (FastAPI / Quasar / Tailwind, communication WebSockets)
  * **Supabase** (PostgreSQL backend avec RLS)
  * **SMTP via asyncio** pour les notifications d'urgence
* **Architecture Backend (`app/services/database_service.py`)** : Couche d'accès aux données 100% stateless utilisant exclusivement le pattern `@staticmethod` (`DatabaseService.method()`). Tout le code IHM s'appuie sur cette norme.
* **Architecture Async** : Encapsulation systématique des requêtes BDD dans `asyncio.to_thread()` pour éviter tout blocage de la boucle d'événements (*Event Loop*) et garantir la fluidité du rendu NiceGUI.

---

## 2. Réalisations & Acquis de la Session (Validation Phase 3 & Refactoring Async)

### ✉️ Service de Notification & SMTP
* Alignement de `NotificationService` sur le pattern `@staticmethod`.
* Correction du bug d'argument positionnel manquant (`membres`) lors de l'activation des cellules de crise.
* Envoi asynchrone non-bloquant des convocations et alertes e-mail au format HTML.

### ⚡ Refactoring Async & IHM NiceGUI
* Résolution des avertissements Python `RuntimeWarning: coroutine was never awaited`.
* Passage en `async / await` propre du composant de vue des crises (`render_crises_view`) et des pages principales (`create_cockpit_page` dans `cockpit.py` et `@ui.page('/') async def dashboard_page()` dans `main.py`).

### 📦 Gestion de Version & Git
* Initialisation du dépôt Git local (`git init`).
* Configuration du fichier `.gitignore` pour exclure l'environnement virtuel (`.venv/`) et protéger les clés d'API / identifiants sensibles du fichier `.env`.
* Création du commit de sauvegarde initial.

---

## 3. Prochaine Étape (Phase 4 — À attaquer lors de la prochaine session)

* **Vue Hypervision des Sites Critiques (`sites_ui.py` / `cockpit.py`)** :
  * Finalisation du suivi dynamique et réactif des postures Sûreté (**S1 à S4**) et Technique (**T1 à T4**).
  * Optimisation du rendu visuel de la grille responsive sous Tailwind / Quasar.
* **Procédure d'Alerte Générale S4 (Bouton Rouge)** :
  * Déclenchement du confinement massif **S4** sur l'ensemble des sites avec sirène/alerte visuelle dans l'IHM.
  * Consignation automatique de l'événement dans la Main Courante Supabase.
  * Module d'acquittement en temps réel pour les agents terrain via la route dédiée `/site/{code_site}`.