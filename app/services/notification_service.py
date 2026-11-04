import asyncio
import os
import json
import urllib.request
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv, find_dotenv

# Rechargement forcé des variables d'environnement (.env)
load_dotenv(find_dotenv(), override=True)


class NotificationService:

    @staticmethod
    def _send_email_via_api_sync(
        recipient: str, subject: str, html_content: str
    ) -> bool:
        """
        Envoi d'e-mail via l'API REST HTTPS de Brevo (Port 443).
        Contourne les blocages de ports SMTP (587/465) sur les réseaux sécurisés.
        """
        api_key = os.getenv("BREVO_API_KEY") or os.getenv("SMTP_PASSWORD", "")
        sender_email = os.getenv("SENDER_EMAIL") or os.getenv("SMTP_EMAIL", "")

        if not api_key:
            print(
                "❌ [CENTAURE API] Clé API Brevo manquante dans le .env (BREVO_API_KEY / SMTP_PASSWORD)."
            )
            return False

        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": api_key,
        }

        payload = {
            "sender": {"name": "CENTAURE Alerte", "email": sender_email},
            "to": [{"email": recipient}],
            "subject": subject,
            "htmlContent": html_content,
        }

        try:
            print(f"🔄 Envoi API REST Brevo vers {recipient}...")
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")

            with urllib.request.urlopen(req, timeout=15) as response:
                if response.getcode() in [200, 201, 202]:
                    print(
                        f"✅ [CENTAURE API] E-mail délivré avec succès à {recipient} !"
                    )
                    return True
                else:
                    print(
                        f"⚠️ [CENTAURE API] Code HTTP inattendu : {response.getcode()}"
                    )
                    return False

        except Exception as e:
            print(f"❌ [CENTAURE API ERROR] Échec d'envoi à {recipient} : {e}")
            if hasattr(e, "read"):
                try:
                    err_detail = e.read().decode("utf-8")
                    print(f"🔍 Détail de l'erreur Brevo : {err_detail}")
                except Exception:
                    pass
            return False

    @staticmethod
    async def send_email_async(recipient: str, subject: str, html_content: str) -> bool:
        """Enveloppe asynchrone non-bloquante exécutée dans un thread pour NiceGUI."""
        return await asyncio.to_thread(
            NotificationService._send_email_via_api_sync,
            recipient,
            subject,
            html_content,
        )

    @staticmethod
    async def notify_crise_activation(
        crise_data: Dict[str, Any], membres: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, int]:
        """Dispatch parallèle des e-mails d'alerte aux membres lors de l'activation d'une crise."""
        if not membres:
            print(
                "⚠️ [CENTAURE API] Aucun membre fourni pour la notification d'activation."
            )
            return {"success": 0, "failed": 0}

        nom_crise = crise_data.get("nom", crise_data.get("titre", "Crise non nommée"))
        code_crise = crise_data.get("code", crise_data.get("code_crise", "CRISE"))
        niveau = crise_data.get("niveau", crise_data.get("niveau_gravite", "CRITIQUE"))
        description = crise_data.get("description", "Aucune précision.")

        lieu_val = (crise_data.get("lieu") or crise_data.get("lieu_pc") or "").strip()
        lieu_display = lieu_val if lieu_val else "Non précisé"

        subject = f"🚨 [CENTAURE ALERTE] Activation Cellule de Crise : {code_crise}"

        tasks = []
        for membre in membres:
            agent = (
                membre.get("centaure_annuaire", {})
                if isinstance(membre.get("centaure_annuaire"), dict)
                else membre
            )
            email = agent.get("email") or membre.get("email")
            nom_agent = (
                f"{agent.get('prenom', '')} {agent.get('nom', '')}".strip() or "Agent"
            )

            if not email:
                continue

            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
                <div style="background-color: #990000; color: #ffffff; padding: 15px; border-radius: 5px;">
                    <h2 style="margin: 0;">🚨 ALERTE CENTAURE - CONVOCATION CELLULE DE CRISE</h2>
                </div>
                <p>Bonjour <strong>{nom_agent}</strong>,</p>
                <p>La cellule de crise suivante vient d'être <strong>ACTIVÉE</strong> :</p>
                <ul>
                    <li><strong>Code & Intitulé :</strong> {code_crise} - {nom_crise}</li>
                    <li><strong>Niveau de sévérité :</strong> <span style="color: red; font-weight: bold;">{niveau}</span></li>
                    <li><strong>Lieu / PC Ralliement :</strong> <span style="color: #005599; font-weight: bold;">{lieu_display}</span></li>
                    <li><strong>Description :</strong> {description}</li>
                </ul>
                <p>Vous êtes prié(e) de rejoindre immédiatement le PC Crise désigné.</p>
                <hr>
                <p style="font-size: 0.8em; color: #777;">Message automatique généré par le Système CENTAURE.</p>
            </body>
            </html>
            """
            tasks.append(
                NotificationService.send_email_async(email, subject, html_body)
            )

        if not tasks:
            print(
                "⚠️ [CENTAURE API] Aucun destinataire valide trouvé avec une adresse e-mail."
            )
            return {"success": 0, "failed": 0}

        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if r is True)
        failed_count = len(results) - success_count

        return {"success": success_count, "failed": failed_count}

    @staticmethod
    async def notify_membre_affectation(
        crise_data: Dict[str, Any], membre: Dict[str, Any]
    ) -> bool:
        """Envoie un e-mail de convocation individuel lors de l'affectation d'un membre."""
        email = membre.get("email")
        if not email:
            print("⚠️ [CENTAURE API] Pas d'adresse e-mail pour ce membre.")
            return False

        nom_crise = crise_data.get("titre", crise_data.get("nom", "Crise non nommée"))
        code_crise = crise_data.get("code_crise", crise_data.get("code", "CRISE"))
        niveau = crise_data.get("niveau_gravite", crise_data.get("niveau", "CRITIQUE"))
        description = crise_data.get("description", "Aucune précision fournie.")
        fonction = membre.get("fonction", "Agent")
        nom_agent = (
            f"{membre.get('prenom', '')} {membre.get('nom', '')}".strip() or "Agent"
        )

        lieu_val = (crise_data.get("lieu") or crise_data.get("lieu_pc") or "").strip()
        lieu_display = lieu_val if lieu_val else "Non précisé"

        subject = f"🚨 [CENTAURE ALERTE] Affectation Cellule de Crise : {code_crise}"

        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
            <div style="background-color: #990000; color: #ffffff; padding: 15px; border-radius: 5px;">
                <h2 style="margin: 0;">🚨 ALERTE CENTAURE - CONVOCATION INDIVIDUELLE</h2>
            </div>
            <p>Bonjour <strong>{nom_agent}</strong>,</p>
            <p>Vous venez d'être affecté(e) en tant que <strong>{fonction}</strong> à la cellule de crise active suivante :</p>
            <ul>
                <li><strong>Code & Intitulé :</strong> {code_crise} - {nom_crise}</li>
                <li><strong>Niveau de sévérité :</strong> <span style="color: red; font-weight: bold;">Niveau {niveau}</span></li>
                <li><strong>Lieu / PC Ralliement :</strong> <span style="color: #005599; font-weight: bold;">{lieu_display}</span></li>
                <li><strong>Description :</strong> {description}</li>
            </ul>
            <p>Vous êtes prié(e) de rejoindre immédiatement le PC Crise désigné.</p>
            <hr>
            <p style="font-size: 0.8em; color: #777;">Message automatique généré par le Système CENTAURE.</p>
        </body>
        </html>
        """
        return await NotificationService.send_email_async(email, subject, html_body)

    @staticmethod
    async def send_sitrep_email(
        crise_data: dict, sitrep_data: dict, destinataires: list[dict]
    ) -> dict:
        """
        Envoie le bulletin SITREP au format HTML aux destinataires sélectionnés via l'API HTTP Brevo.
        """
        if not destinataires:
            print("⚠️ [CENTAURE API SITREP] Aucun destinataire fourni.")
            return {
                "success": 0,
                "failed": 0,
                "error": "Aucun destinataire sélectionné",
            }

        code_crise = crise_data.get("code_crise", "CRISE")
        titre_crise = crise_data.get("titre", "Sans titre")
        num_sitrep = sitrep_data.get("numero_sitrep", "1")

        subject = f"📢 [SITREP #{num_sitrep}] {code_crise} - {titre_crise}"

        # Construction du corps HTML
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background-color: #1e293b; border: 1px solid #3b82f6; border-radius: 8px; padding: 20px;">
                <h2 style="color: #60a5fa; border-bottom: 2px solid #3b82f6; padding-bottom: 10px; margin-top: 0;">
                    📋 BULLETIN DE SITUATION (SITREP #{num_sitrep})
                </h2>
                <p style="font-size: 14px; color: #94a3b8;">
                    <strong>Crise :</strong> {code_crise} — {titre_crise}<br>
                    <strong>Rédacteur :</strong> {sitrep_data.get('redacteur', 'N/A')}<br>
                    <strong>Horodatage :</strong> {sitrep_data.get('horodatage_fmt', 'N/A')}
                </p>
                
                <div style="background-color: #090d16; padding: 12px; border-radius: 6px; margin-top: 15px;">
                    <h3 style="color: #93c5fd; margin-top: 0;">📌 Synthèse de la Situation</h3>
                    <p style="white-space: pre-line; color: #e2e8f0;">{sitrep_data.get('synthese_situation', 'Aucune synthèse')}</p>
                </div>

                {f'''
                <div style="background-color: #2e1065; padding: 12px; border-radius: 6px; margin-top: 15px; border-left: 4px solid #f59e0b;">
                    <h3 style="color: #fcd34d; margin-top: 0;">⚠️ Points d'attention / Arbitrages SG</h3>
                    <p style="white-space: pre-line; color: #fef08a;">{sitrep_data.get('points_attention')}</p>
                </div>
                ''' if sitrep_data.get('points_attention') else ''}

                {f'''
                <div style="background-color: #064e3b; padding: 12px; border-radius: 6px; margin-top: 15px; border-left: 4px solid #10b981;">
                    <h3 style="color: #6ee7b7; margin-top: 0;">🚀 Actions engagées</h3>
                    <p style="white-space: pre-line; color: #d1fae5;">{sitrep_data.get('actions_engagees')}</p>
                </div>
                ''' if sitrep_data.get('actions_engagees') else ''}

                {f'''
                <div style="margin-top: 15px; padding: 10px; background-color: #1e1b4b; border-radius: 6px;">
                    <strong style="color: #c084fc;">⏱️ Prochaine échéance / Réunion :</strong> 
                    <span style="color: #e9d5ff;">{sitrep_data.get('prochaine_echeance')}</span>
                </div>
                ''' if sitrep_data.get('prochaine_echeance') else ''}

                <hr style="border-color: #334155; margin-top: 25px;">
                <p style="font-size: 11px; color: #64748b; text-align: center;">
                    Cockpit CENTAURE — Message automatique à destination du Secrétariat Général.
                </p>
            </div>
        </body>
        </html>
        """

        tasks = []
        for dest in destinataires:
            email_addr = dest.get("email")
            if not email_addr:
                continue

            tasks.append(
                NotificationService.send_email_async(email_addr, subject, html_content)
            )

        if not tasks:
            print(
                "⚠️ [CENTAURE API SITREP] Aucune adresse e-mail valide dans la sélection."
            )
            return {"success": 0, "failed": 0, "error": "Aucune adresse e-mail valide."}

        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if r is True)
        failed_count = len(results) - success_count

        return {"success": success_count, "failed": failed_count}
