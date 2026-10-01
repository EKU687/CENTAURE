import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from app.services.supabase_client import supabase
from app.models.site import SiteCritique, AnomalieTechnique
from app.models.crise import CriseStrategique


class DatabaseService:
    """Service d'accès aux données Supabase pour le projet CENTAURE (Stateless)."""

    # =========================================================================
    # 🏢 GESTION DES SITES CRITIQUES & HYPERVISION
    # =========================================================================

    @staticmethod
    def get_all_sites() -> List[SiteCritique]:
        """Récupère tous les sites d'hypervision triés par ordre alphabétique fixe (code_site)."""
        try:
            res_sites = (
                supabase.table("centaure_sites")
                .select("*")
                .order("code_site", desc=False)
                .execute()
            )
            sites = [SiteCritique(**data) for data in res_sites.data]

            res_anomalies = (
                supabase.table("centaure_anomalies")
                .select("*")
                .eq("statut", "ACTIF")
                .execute()
            )
            anomalies = [AnomalieTechnique(**data) for data in res_anomalies.data]

            anomalies_by_site = {}
            for ano in anomalies:
                anomalies_by_site.setdefault(ano.site_id, []).append(ano)

            for site in sites:
                if site.id in anomalies_by_site:
                    site.anomalies = anomalies_by_site[site.id]

            return sites
        except Exception as e:
            print(f"❌ Erreur lors de la récupération des sites : {e}")
            return []

    @staticmethod
    def update_site_status(
        site_id: str,
        surete: str,
        technique: str,
        motif: Optional[str] = None,
        active_protocol_id: Optional[str] = None,
    ) -> bool:
        """Met à jour les niveaux S et T d'un site, le protocole actif retenu et insère un motif."""
        try:
            payload = {
                "surete_niveau": surete,
                "technique_niveau": technique,
                "updated_at": "now()",
            }
            if active_protocol_id is not None:
                payload["active_protocol_id"] = active_protocol_id

            supabase.table("centaure_sites").update(payload).eq("id", site_id).execute()

            if motif and motif.strip():
                domaine_impacte = (
                    "SURETE" if surete in ["S2", "S3", "S4"] else "TECHNIQUE"
                )
                supabase.table("centaure_anomalies").insert(
                    {
                        "site_id": site_id,
                        "domaine": domaine_impacte,
                        "equipement": f"Changement de statut ({surete} / {technique})",
                        "description": motif.strip(),
                        "statut": "ACTIF",
                    }
                ).execute()

            return True
        except Exception as e:
            print(f"❌ Erreur lors de la mise à jour du statut site : {e}")
            return False

    @staticmethod
    def add_anomalie(
        site_id: str, domaine: str, equipement: str, description: str
    ) -> bool:
        """Ajoute une anomalie et passe le site en vigilance technique ou sûreté."""
        try:
            supabase.table("centaure_anomalies").insert(
                {
                    "site_id": site_id,
                    "domaine": domaine,
                    "equipement": equipement,
                    "description": description,
                    "statut": "ACTIF",
                }
            ).execute()

            champ_niveau = (
                "technique_niveau" if domaine == "TECHNIQUE" else "surete_niveau"
            )
            valeur_niveau = "T2" if domaine == "TECHNIQUE" else "S2"

            supabase.table("centaure_sites").update({champ_niveau: valeur_niveau}).eq(
                "id", site_id
            ).execute()

            return True
        except Exception as e:
            print(f"❌ Erreur ajout anomalie : {e}")
            return False

    @staticmethod
    def resolve_anomalie(anomalie_id: str) -> bool:
        """Marque une anomalie comme résolue."""
        try:
            supabase.table("centaure_anomalies").update({"statut": "RESOLU"}).eq(
                "id", anomalie_id
            ).execute()
            return True
        except Exception as e:
            print(f"❌ Erreur résolution anomalie : {e}")
            return False

    @staticmethod
    def acquitter_alerte_s4(site_id: str, agent_nom: str = "Agent Site") -> bool:
        """Enregistre l'acquittement de l'ordre de confinement S4 par l'agent local."""
        try:
            supabase.table("centaure_acquittements").insert(
                {
                    "site_id": site_id,
                    "agent_nom": agent_nom,
                    "remarques": "Acquittement de la sirène et prise en compte du protocole de confinement.",
                }
            ).execute()
            return True
        except Exception as e:
            print(f"❌ Erreur acquittement S4 : {e}")
            return False

    @staticmethod
    def declencher_s4_general() -> bool:
        """Passe TOUS les sites en posture S4."""
        try:
            res = supabase.table("centaure_sites").select("id").execute()
            site_ids = [site["id"] for site in res.data]

            if not site_ids:
                return False

            supabase.table("centaure_sites").update(
                {"surete_niveau": "S4", "updated_at": "now()"}
            ).in_("id", site_ids).execute()

            return True
        except Exception as e:
            print(f"❌ Échec du déclenchement S4 : {e}")
            return False

    @staticmethod
    def reinitialiser_tous_sites_s1() -> bool:
        """Repasse l'intégralité des sites en Posture Sûreté S1."""
        try:
            res = supabase.table("centaure_sites").select("id").execute()
            site_ids = [site["id"] for site in res.data]

            if not site_ids:
                return True

            supabase.table("centaure_sites").update(
                {"surete_niveau": "S1", "updated_at": "now()"}
            ).in_("id", site_ids).execute()

            return True
        except Exception as e:
            print(f"❌ Erreur réinitialisation S1 générale : {e}")
            return False

    @staticmethod
    def update_site_info(
        site_id: str, nom: str, localisation: str, protocole: Optional[str] = None
    ) -> bool:
        """Met à jour les informations de base d'un site."""
        try:
            supabase.table("centaure_sites").update(
                {
                    "nom": nom.strip(),
                    "localisation": localisation.strip(),
                    "protocole_confinement": protocole.strip() if protocole else None,
                    "updated_at": "now()",
                }
            ).eq("id", site_id).execute()
            return True
        except Exception as e:
            print(f"❌ Erreur modification site : {e}")
            return False

    @staticmethod
    def delete_site(site_id: str) -> bool:
        """Supprime un site critique."""
        try:
            supabase.table("centaure_sites").delete().eq("id", site_id).execute()
            return True
        except Exception as e:
            print(f"❌ Erreur suppression site : {e}")
            return False

    # =========================================================================
    # 📜 GESTION DYNAMIQUE DES PROTOCOLES PAR SITE & RÉFÉRENTIEL
    # =========================================================================

    @staticmethod
    def get_site_protocols(site_code: str) -> List[Dict[str, Any]]:
        """Récupère tous les protocoles spécifiques configurés pour un site (ex: DINUM, DOUMER)."""
        try:
            res = (
                supabase.table("centaure_site_protocols")
                .select("*")
                .eq("site_code", str(site_code))
                .order("niveau", desc=False)
                .execute()
            )
            return res.data or []
        except Exception as e:
            print(f"❌ Erreur récupération protocoles site ({site_code}) : {e}")
            return []

    @staticmethod
    def save_site_protocol(protocol_data: Dict[str, Any]) -> bool:
        """Crée ou met à jour un protocole sur-mesure pour un site."""
        try:
            payload = {
                "site_code": str(protocol_data.get("site_code")),
                "niveau": str(protocol_data.get("niveau")).upper(),
                "titre": str(protocol_data.get("titre")).strip(),
                "consignes": str(protocol_data.get("consignes", "")).strip(),
                "updated_at": "now()",
            }
            if protocol_data.get("id"):
                supabase.table("centaure_site_protocols").update(payload).eq(
                    "id", str(protocol_data["id"])
                ).execute()
            else:
                supabase.table("centaure_site_protocols").insert(payload).execute()
            return True
        except Exception as e:
            print(f"❌ Erreur enregistrement protocole site : {e}")
            return False

    @staticmethod
    def delete_site_protocol(protocol_id: str) -> bool:
        """Supprime un protocole spécifique d'un site."""
        try:
            supabase.table("centaure_site_protocols").delete().eq(
                "id", str(protocol_id)
            ).execute()
            return True
        except Exception as e:
            print(f"❌ Erreur suppression protocole site : {e}")
            return False

    @staticmethod
    def get_all_ref_protocols() -> List[Dict[str, Any]]:
        """Récupère l'ensemble des modèles de protocoles du référentiel administrateur."""
        try:
            res = (
                supabase.table("centaure_ref_protocols")
                .select("*")
                .order("niveau_cible", desc=False)
                .execute()
            )
            return res.data or []
        except Exception as e:
            print(f"❌ Erreur récupération référentiel protocoles : {e}")
            return []

    @staticmethod
    def save_ref_protocol(ref_data: Dict[str, Any]) -> bool:
        """Crée ou met à jour un modèle de protocole dans le référentiel admin."""
        try:
            payload = {
                "code": str(ref_data.get("code")).strip().upper(),
                "titre": str(ref_data.get("titre")).strip(),
                "niveau_cible": str(ref_data.get("niveau_cible")).upper(),
                "consignes_standard": str(
                    ref_data.get("consignes_standard", "")
                ).strip(),
            }
            if ref_data.get("id"):
                supabase.table("centaure_ref_protocols").update(payload).eq(
                    "id", str(ref_data["id"])
                ).execute()
            else:
                supabase.table("centaure_ref_protocols").insert(payload).execute()
            return True
        except Exception as e:
            print(f"❌ Erreur enregistrement référentiel protocole : {e}")
            return False

    @staticmethod
    def delete_ref_protocol(ref_id: str) -> bool:
        """Supprime un modèle du référentiel administrateur."""
        try:
            supabase.table("centaure_ref_protocols").delete().eq(
                "id", str(ref_id)
            ).execute()
            return True
        except Exception as e:
            print(f"❌ Erreur suppression modèle référentiel : {e}")
            return False

    # =========================================================================
    # 🔥 GESTION DES CELLULES DE CRISE STRATÉGIQUES
    # =========================================================================

    @staticmethod
    def get_active_crises() -> List[Dict[str, Any]]:
        """Récupère toutes les crises actives."""
        try:
            res = (
                supabase.table("centaure_crises")
                .select("*")
                .in_("statut", ["ACTIVEE", "EN_SOMMEIL"])
                .order("created_at", desc=True)
                .execute()
            )
            return res.data or []
        except Exception as e:
            print(f"❌ Erreur récupération crises : {e}")
            return []

    @staticmethod
    def get_crise_by_id(crise_id: str) -> Optional[Dict[str, Any]]:
        """Récupère une crise par son UUID."""
        try:
            res = (
                supabase.table("centaure_crises")
                .select("*")
                .eq("id", str(crise_id))
                .execute()
            )
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"❌ Erreur récupération crise par ID : {e}")
            return None

    @staticmethod
    def create_crise(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Création d'une fiche de crise."""
        try:
            res = supabase.table("centaure_crises").insert(payload).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"❌ Échec création crise : {e}")
            return None

    @staticmethod
    def update_crise(
        crise_id: str,
        titre: Optional[str] = None,
        type_crise: Optional[str] = None,
        gravite: Optional[str] = None,
        description: Optional[str] = None,
        lieu_pc: Optional[str] = None,
        statut: Optional[str] = None,
    ) -> bool:
        """Mise à jour des informations de crise."""
        try:
            payload = {}
            if titre is not None:
                payload["titre"] = titre.strip()
            if type_crise is not None:
                payload["type_crise"] = type_crise.strip()
            if gravite is not None:
                payload["niveau_gravite"] = str(gravite).strip()
            if description is not None:
                payload["description"] = description.strip()
            if lieu_pc is not None:
                payload["lieu_pc"] = lieu_pc.strip()
            if statut is not None:
                payload["statut"] = statut.strip()

            if not payload:
                return True

            supabase.table("centaure_crises").update(payload).eq(
                "id", str(crise_id)
            ).execute()
            return True
        except Exception as e:
            print(f"❌ Échec modification crise : {e}")
            return False

    @staticmethod
    def archiver_crise(crise_id: str) -> bool:
        """Archivage d'une crise."""
        try:
            supabase.table("centaure_crises").update({"statut": "ARCHIVEE"}).eq(
                "id", str(crise_id)
            ).execute()
            return True
        except Exception as e:
            print(f"❌ Erreur archivage crise : {e}")
            return False

    @staticmethod
    def delete_crise(crise_id: str) -> bool:
        """Suppression d'une crise."""
        try:
            supabase.table("centaure_crises").delete().eq("id", str(crise_id)).execute()
            return True
        except Exception as e:
            print(f"❌ Erreur suppression crise : {e}")
            return False

    # =========================================================================
    # 📜 MAIN COURANTE (CONNEXION STRICTE AU SCHÉMA BDD EXACT)
    # =========================================================================

    @staticmethod
    def get_main_courante_by_crise(crise_id: str) -> List[Dict[str, Any]]:
        """
        Récupère les événements de la main courante triés par horodatage inverse.
        Champs BDD utilisés: id, crise_id, horodatage, auteur, categorie, description,
        niveau_priorite, created_at, statut_info, direction_concernee, message
        """
        try:
            res = (
                supabase.table("centaure_main_courante")
                .select("*")
                .eq("crise_id", str(crise_id))
                .order("horodatage", desc=True)
                .execute()
            )
            return res.data or []
        except Exception as e:
            print(f"❌ Erreur lecture centaure_main_courante : {e}")
            return []

    @staticmethod
    def consigner_main_courante(
        crise_id: str,
        description: str,
        categorie: str = "INFORMATION",
        auteur: str = "Opérateur SG",
        niveau_priorite: str = "NORMALE",
        statut_info: str = "CONFIRMEE",
        direction_concernee: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Consigne un événement selon la structure exacte des colonnes Supabase.
        """
        if not crise_id or not str(description).strip():
            print("⚠️ [MAIN COURANTE] crise_id ou description manquant.")
            return None

        clean_text = str(description).strip()
        dir_val = (
            direction_concernee.strip()
            if direction_concernee and direction_concernee != "TOUTES / GÉNÉRAL"
            else "TOUTES / GÉNÉRAL"
        )

        payload = {
            "crise_id": str(crise_id),
            "horodatage": datetime.utcnow().isoformat(),
            "auteur": str(auteur),
            "categorie": str(categorie).upper(),
            "description": clean_text,
            "niveau_priorite": str(niveau_priorite).upper(),
            "statut_info": str(statut_info).upper() if statut_info else "CONFIRMEE",
            "direction_concernee": dir_val,
        }

        try:
            res = supabase.table("centaure_main_courante").insert(payload).execute()
            if res.data:
                print(
                    f"📜 [MAIN COURANTE] Log inséré avec succès ID: {res.data[0].get('id')}"
                )
                return res.data[0]
            return None
        except Exception as e:
            print(f"❌ Erreur insertion centaure_main_courante : {e}")
            return None

    @staticmethod
    def update_statut_information(log_id: str, nouveau_statut: str) -> bool:
        """Met à jour le champ statut_info d'une entrée."""
        try:
            supabase.table("centaure_main_courante").update(
                {"statut_info": str(nouveau_statut).upper()}
            ).eq("id", str(log_id)).execute()
            return True
        except Exception as e:
            print(f"❌ Erreur mise à jour statut_info : {e}")
            return False

    ajouter_entree_main_courante = consigner_main_courante

    # =========================================================================
    # 👥 ANNUAIRE RH & DIRECTIONS (REFERENTIEL D'ÉTAT GNC)
    # =========================================================================

    @staticmethod
    def get_annuaire() -> List[Dict[str, Any]]:
        """Récupère la liste des agents de l'annuaire."""
        try:
            res = (
                supabase.table("centaure_annuaire")
                .select("*")
                .order("nom", desc=False)
                .execute()
            )
            return res.data or []
        except Exception as e:
            print(f"⚠️ Erreur récupération annuaire : {e}")
            return []

    @staticmethod
    def get_all_directions() -> List[str]:
        """Récupère le référentiel complet des directions du Gouvernement de la Nouvelle-Calédonie."""
        official_gnc_dirs = [
            "SG",
            "DPSE",
            "DINUM",
            "DAPM",
            "DAAJ",
            "DASS",
            "DIMENC",
            "DNC",
            "DSCGR",
            "Direction",
            "Sécurité",
        ]
        try:
            res = supabase.table("centaure_annuaire").select("service").execute()
            if res.data:
                db_dirs = {
                    str(item.get("service")).strip()
                    for item in res.data
                    if item.get("service")
                }
                combined = sorted(list(db_dirs.union(set(official_gnc_dirs))))
                return combined
            return official_gnc_dirs
        except Exception:
            return official_gnc_dirs

    @staticmethod
    def get_all_directions_full() -> List[Dict[str, str]]:
        """Format dictionnaire pour sélecteurs."""
        return [{"code": d} for d in DatabaseService.get_all_directions()]

    @staticmethod
    def get_membres_crise(crise_id: str) -> List[Dict[str, Any]]:
        """Récupère les membres affectés à une crise."""
        try:
            res = (
                supabase.table("centaure_crise_membres")
                .select("id, fonction_crise, centaure_annuaire(*)")
                .eq("crise_id", str(crise_id))
                .execute()
            )
            return res.data or []
        except Exception as e:
            print(f"⚠️ Erreur membres crise : {e}")
            return []

    @staticmethod
    def affecter_membre_crise(crise_id: str, personne_id: str, fonction: str) -> bool:
        """Affectation RH."""
        try:
            supabase.table("centaure_crise_membres").insert(
                {
                    "crise_id": str(crise_id),
                    "personne_id": str(personne_id),
                    "fonction_crise": fonction,
                }
            ).execute()
            return True
        except Exception as e:
            print(f"⚠️ Erreur affectation : {e}")
            return False

    @staticmethod
    def retirer_membre_crise(link_id: str) -> bool:
        """Retrait RH."""
        try:
            supabase.table("centaure_crise_membres").delete().eq(
                "id", str(link_id)
            ).execute()
            return True
        except Exception as e:
            print(f"⚠️ Erreur retrait : {e}")
            return False

    @staticmethod
    def get_active_protocol_for_site(site_code: str) -> Optional[Dict[str, Any]]:
        """
        Récupère le protocole actif sélectionné pour un site via sa colonne active_protocol_id,
        ou à défaut le premier protocole correspondant au niveau de sûreté actuel.
        """
        try:
            # 1. Récupérer le site avec son niveau et son active_protocol_id
            res_site = (
                supabase.table("centaure_sites")
                .select("surete_niveau, active_protocol_id")
                .eq("code_site", str(site_code))
                .execute()
            )
            if not res_site.data:
                return None

            site_data = res_site.data[0]
            active_proto_id = site_data.get("active_protocol_id")
            current_s = site_data.get("surete_niveau")

            # 2. Si un protocole spécifique est ciblé via active_protocol_id
            if active_proto_id:
                res_proto = (
                    supabase.table("centaure_site_protocols")
                    .select("*")
                    .eq("id", str(active_proto_id))
                    .execute()
                )
                if res_proto.data:
                    return res_proto.data[0]

            # 3. Fallback : Prendre le premier protocole du site qui correspond au niveau S actuel
            res_fallback = (
                supabase.table("centaure_site_protocols")
                .select("*")
                .eq("site_code", str(site_code))
                .eq("niveau", str(current_s))
                .execute()
            )
            return res_fallback.data[0] if res_fallback.data else None

        except Exception as e:
            print(f"❌ Erreur récupération protocole actif site ({site_code}) : {e}")
            return None

    @staticmethod
    def get_site_by_kiosk_token(token: str) -> Optional[Dict[str, Any]]:
        """Récupère le site correspondant au jeton d'accès permanent du poste de garde."""
        try:
            res = (
                supabase.table("centaure_sites")
                .select("*")
                .eq("kiosk_token", str(token).strip())
                .execute()
            )
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"❌ Erreur vérification token kiosque ({token}) : {e}")
            return None

    @staticmethod
    @staticmethod
    def get_kiosk_url_for_site(code_site: str, base_url: str = None) -> str:
        """
        Génère ou récupère l'URL d'accès permanent sécurisée (Kiosque) pour le poste de garde.
        """
        # Si aucune base_url n'est passée en paramètre, on lit APP_URL dans le .env
        if not base_url:
            base_url = os.getenv("APP_URL", "http://localhost:8080")

        clean_code = str(code_site).strip()
        try:
            # 1. Requête Supabase avec filtre insensible à la casse (ilike)
            res = (
                supabase.table("centaure_sites")
                .select("id, code_site, kiosk_token")
                .ilike("code_site", clean_code)
                .execute()
            )

            print(
                f"🔍 [DEBUG KIOSK] Recherche site '{clean_code}' -> Résultat BDD : {res.data}"
            )

            if res.data:
                site_record = res.data[0]
                token = site_record.get("kiosk_token")

                # 2. Si le token est NULL, on génère un UUID à la volée et on le sauvegarde
                if not token:
                    import uuid

                    new_token = str(uuid.uuid4())
                    supabase.table("centaure_sites").update(
                        {"kiosk_token": new_token}
                    ).eq("id", site_record["id"]).execute()
                    token = new_token

                return f"{base_url.rstrip('/')}/kiosk?token={token}"

            print(
                f"⚠️ [DEBUG KIOSK] Aucun site trouvé dans Supabase pour le code : '{clean_code}'"
            )
            return f"{base_url.rstrip('/')}/kiosk?token=site-non-trouve-{clean_code}"

        except Exception as e:
            print(f"❌ [DEBUG KIOSK] Erreur Supabase pour ({clean_code}) : {e}")
            return f"{base_url.rstrip('/')}/kiosk?token=erreur-connexion"

    @staticmethod
    def authenticate_user(username: str, password_plain: str) -> Optional[dict]:
        """Vérifie les identifiants d'un utilisateur du Cockpit."""
        try:
            res = (
                supabase.table("centaure_users")
                .select("id, username, nom_complet, role, password_hash")
                .eq("username", str(username).strip().lower())
                .execute()
            )
            if res.data:
                user = res.data[0]
                # Comparaison directe (ou vérification de hash bcrypt)
                if user.get("password_hash") == password_plain:
                    return {
                        "id": user["id"],
                        "username": user["username"],
                        "nom_complet": user["nom_complet"],
                        "role": user["role"],
                    }
            return None
        except Exception as e:
            print(f"❌ Erreur lors de l'authentification : {e}")
            return None

    @staticmethod
    def get_all_users() -> list:
        """Récupère la liste de tous les utilisateurs du Cockpit."""
        try:
            res = (
                supabase.table("centaure_users")
                .select("id, username, nom_complet, role, created_at")
                .execute()
            )
            return res.data or []
        except Exception as e:
            print(f"❌ Erreur récupération utilisateurs : {e}")
            return []

    @staticmethod
    def save_user(user_data: dict) -> bool:
        """Crée ou met à jour un utilisateur."""
        try:
            if "id" in user_data and user_data["id"]:
                supabase.table("centaure_users").update(user_data).eq(
                    "id", user_data["id"]
                ).execute()
            else:
                supabase.table("centaure_users").insert(user_data).execute()
            return True
        except Exception as e:
            print(f"❌ Erreur sauvegarde utilisateur : {e}")
            return False

    @staticmethod
    def delete_user(user_id: str) -> bool:
        """Supprime un utilisateur par son UUID."""
        try:
            supabase.table("centaure_users").delete().eq("id", user_id).execute()
            return True
        except Exception as e:
            print(f"❌ Erreur suppression utilisateur : {e}")
            return False

    @staticmethod
    def save_yubikey_credential(user_id: str, credential_id: str) -> bool:
        """Enregistre le credential_id de la YubiKey associée à un utilisateur dans Supabase."""
        try:
            payload = {
                "user_id": user_id,
                "credential_id": credential_id,
                "public_key": "stored_fido2_key",  # Empreinte de clé
            }
            supabase.table("centaure_yubikeys").insert(payload).execute()
            print(f"✅ [YUBIKEY] Clé FIDO2 enregistrée pour l'utilisateur {user_id}")
            return True
        except Exception as e:
            print(f"❌ Erreur sauvegarde YubiKey dans BDD : {e}")
            return False

    @staticmethod
    def save_yubikey_public_id(user_id: str, public_id: str) -> bool:
        """Enregistre l'identifiant public unique de la YubiKey pour un utilisateur."""
        try:
            payload = {
                "user_id": user_id,
                "credential_id": public_id[
                    :12
                ],  # Extrait les 12 caractères de la clé publique
                "public_key": "yubikey_otp_public",
            }
            supabase.table("centaure_yubikeys").insert(payload).execute()
            print(
                f"✅ [YUBIKEY] Identifiant public {public_id[:12]} associé à l'utilisateur {user_id}"
            )
            return True
        except Exception as e:
            print(f"❌ Erreur sauvegarde YubiKey Supabase : {e}")
            return False

    @staticmethod
    def authenticate_by_yubikey(yubi_raw_input: str) -> Optional[dict]:
        """Authentifie un utilisateur grâce aux 12 premiers caractères de sa YubiKey OTP."""
        try:
            if not yubi_raw_input or len(yubi_raw_input.strip()) < 12:
                return None

            public_id = yubi_raw_input.strip()[:12]
            print(f"🔑 [YUBIKEY LOGIN] Clé Publique soumise : {public_id}")

            # Recherche dans centaure_yubikeys
            res = (
                supabase.table("centaure_yubikeys")
                .select("user_id, centaure_users(id, username, nom_complet, role)")
                .eq("credential_id", public_id)
                .execute()
            )

            if res.data and len(res.data) > 0:
                user_info = res.data[0].get("centaure_users")
                if user_info:
                    print(
                        f"✅ [YUBIKEY LOGIN] Utilisateur reconnu : {user_info['username']}"
                    )
                    return user_info

            print(f"⚠️️ [YUBIKEY LOGIN] Clé {public_id} inconnue en base de données.")
            return None
        except Exception as e:
            print(f"❌ Erreur lors de l'authentification YubiKey : {e}")
            return None


db_service = DatabaseService()
