# 📌 Document de Contexte & Reprise de Session — CENTAURE

**Projet :** Cockpit Central de Supervision CENTAURE (Gouvernement de la Nouvelle-Calédonie)  
**Architecture :** Python 3.14 / NiceGUI / Supabase (PostgreSQL)  
**Date d'actualisation :** 30 septembre 2026  

---

## 1. Vue d'Ensemble & Progression de la Session

L'objectif principal de cette session était d'intégrer le contrôle d'accès utilisateur (RBAC) et d'assurer une authentification matérielle fluide via **YubiKey** sur le Cockpit **CENTAURE**.

### Réalisations majeures :
1. **Module de Gestion des Accès (CRUD Users) :**
   * Ajout de l'onglet `Gestion Accès` réservé au rôle `ADMIN`.
   * Prise en charge de la création, modification et suppression des comptes utilisateurs dans Supabase.
   * Gestion des rôles RBAC : `ADMIN`, `SUPERVISEUR_SG`, `OPERATEUR_SG`.

2. **Authentification YubiKey Stabilisée (Mode OTP HID / Clé Publique) :**
   * Abandon de l'API WebAuthn/FIDO2 standard (qui imposait la saisie/gestion de PIN matériels et les contraintes de domaine Windows Hello).
   * Migration réussie vers l'écoute de la frappe clavier de la YubiKey (mode HID OTP / extraction des 12 premiers caractères de l'identifiant public).
   * Sécurisation visuelle de la saisie (champs masqués par puces `password=True`) aussi bien sur la page de `/login` que dans la modale d'enrôlement.

3. **Ergonomie & Session :**
   * Intégration du bouton de déconnexion (`do_logout`) dans le Header du Cockpit (`app/ui/cockpit.py`).
   * Nettoyage automatique de la session `app.storage.user` avec redirection vers `/login`.

---

## 2. Point Attention & Bug à Traiter en Priorité (Next Step)

⚠️ **Anomalie identifiée en fin de session :**
* **Problème :** Les protocoles associés aux sites sensibles n'apparaissent plus correctement dans les fiches ou les sélecteurs de posture.
* **Action pour la prochaine session :** Inspecter les requêtes BDD `DatabaseService.get_site_protocols()` et vérifier le rendu dynamique dans la modale d'inspection de `app/ui/cockpit.py`.

---

## 3. État Technique du Code Base

### A. Modèle BDD Supabase (`centaure_yubikeys`)
```sql
CREATE TABLE IF NOT EXISTS centaure_yubikeys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES centaure_users(id) ON DELETE CASCADE,
    credential_id TEXT UNIQUE NOT NULL, -- Stocke les 12 premiers caractères (Clé Publique)
    public_key TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### B. Méthodes Clés (`DatabaseService`)
* `get_all_users()` / `save_user()` / `delete_user()` : Administration des comptes.
* `save_yubikey_public_id(user_id, public_id)` : Enregistrement de l'empreinte matérielle à 12 caractères.
* `authenticate_by_yubikey(yubi_raw_input)` : Vérification et connexion instantanée par YubiKey.
* `get_site_protocols(site_code)` : *(À corriger lors de la prochaine session)*.

### C. Fichiers Mis à Jour
* `app/ui/login_ui.py` : Écran de connexion hybride (Pass/YubiKey) avec champs masqués.
* `app/ui/users_ui.py` : Vue d'administration et modale d'association YubiKey.
* `app/ui/cockpit.py` : Hypervision principale, header avec logout et onglet d'administration conditionnel.

---

## 4. Programme de la Prochaine Session

1. **Correction du bug des Protocoles Sites :** Diagnostiquer et corriger l'affichage des protocoles associés aux sites sensibles.
2. **Audit / Logs de Sécurité :** Traçabilité des actions sensibles et connexions YubiKey.
3. **Revue de Code & Finalisation :** Vérification globale avant le déploiement sur l'infrastructure du Gouvernement.