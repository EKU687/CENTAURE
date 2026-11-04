import asyncio
from datetime import datetime
from app.services.database_service import DatabaseService


class SitrepService:

    @staticmethod
    def generate_auto_summary(crise_id: str) -> dict:
        """Agrège automatiquement les données du cockpit pour pré-remplir le SITREP."""
        # 1. Récupération des sites et comptage des postures
        sites = DatabaseService.get_all_sites() or []
        sites_s4 = [
            s.code_site for s in sites if getattr(s, "surete_niveau", "") == "S4"
        ]
        sites_s3 = [
            s.code_site for s in sites if getattr(s, "surete_niveau", "") == "S3"
        ]
        sites_critiques = [
            s.code_site
            for s in sites
            if getattr(s, "technique_niveau", "") in ["T3", "T4"]
        ]

        # 2. Récupération des derniers événements de la Main Courante (Decisions / Alertes)
        logs = DatabaseService.get_main_courante_by_crise(crise_id) or []
        faits_marquants = [
            f"[{log.get('categorie')}] {log.get('description')}"
            for log in logs[:5]  # 5 derniers événements
        ]

        return {
            "sites_s4": sites_s4,
            "sites_s3": sites_s3,
            "sites_critiques_tech": sites_critiques,
            "faits_marquants": (
                "\n".join(faits_marquants)
                if faits_marquants
                else "Aucun fait marquant consigné."
            ),
        }

    @staticmethod
    def create_sitrep(payload: dict) -> bool:
        """Enregistre un nouveau SITREP dans Supabase."""
        try:
            # Récupérer le dernier numéro de SITREP pour cette crise
            existing = (
                DatabaseService.supabase.table("centaure_sitreps")
                .select("numero_sitrep")
                .eq("crise_id", payload["crise_id"])
                .order("numero_sitrep", desc=True)
                .limit(1)
                .execute()
            )

            next_num = (existing.data[0]["numero_sitrep"] + 1) if existing.data else 1
            payload["numero_sitrep"] = next_num

            res = (
                DatabaseService.supabase.table("centaure_sitreps")
                .insert(payload)
                .execute()
            )
            return bool(res.data)
        except Exception as err:
            print(f"❌ [SITREP SERVICE] Erreur création SITREP : {err}")
            return False

    @staticmethod
    def get_sitreps_by_crise(crise_id: str) -> list[dict]:
        """Récupère l'historique des SITREPs d'une crise."""
        try:
            res = (
                DatabaseService.supabase.table("centaure_sitreps")
                .select("*")
                .eq("crise_id", crise_id)
                .order("numero_sitrep", desc=True)
                .execute()
            )
            return res.data or []
        except Exception as err:
            print(f"❌ [SITREP SERVICE] Erreur chargement SITREPs : {err}")
            return []
