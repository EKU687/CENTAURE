import asyncio
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv, find_dotenv

# Rechargement forcé du .env
load_dotenv(find_dotenv(), override=True)


class NotificationService:

    @staticmethod
    def _get_smtp_config():
        """Récupération centralisée de la configuration SMTP."""
        smtp_host = os.getenv("SMTP_SERVER") or os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", 587))
        smtp_user = os.getenv("SMTP_EMAIL") or os.getenv("SMTP_USER", "")
        smtp_password = os.getenv("SMTP_PASSWORD", "")
        sender_email = os.getenv("SENDER_EMAIL") or smtp_user
        return smtp_host, smtp_port, smtp_user, smtp_password, sender_email

    @staticmethod
    def _send_single_email_sync(
        recipient: str, subject: str, html_content: str
    ) -> bool:
        smtp_host, smtp_port, smtp_user, smtp_password, sender_email = (
            NotificationService._get_smtp_config()
        )

        if not smtp_user or not smtp_password:
            print("❌ [CENTAURE SMTP] Identifiants manquants dans le .env.")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"CENTAURE Alerte <{sender_email}>"
        msg["To"] = recipient

        part_html = MIMEText(html_content, "html")
        msg.attach(part_html)

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        try:
            print(f"🔄 Connexion SMTP à {smtp_host}:{smtp_port}...")

            if smtp_port == 465:
                with smtplib.SMTP_SSL(
                    smtp_host, smtp_port, context=context, timeout=30
                ) as server:
                    print("🔑 Authentification SSL direct...")
                    server.login(smtp_user, smtp_password)
                    print(f"📧 Envoi à {recipient}...")
                    server.sendmail(sender_email, recipient, msg.as_string())
            else:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                    print("🔒 Négociation STARTTLS...")
                    server.starttls(context=context)
                    print("🔑 Authentification...")
                    server.login(smtp_user, smtp_password)
                    print(f"📧 Envoi à {recipient}...")
                    server.sendmail(sender_email, recipient, msg.as_string())

            print(f"✅ [CENTAURE SMTP] E-mail envoyé avec succès à {recipient} !")
            return True

        except smtplib.SMTPAuthenticationError as auth_err:
            print(
                f"❌ [CENTAURE SMTP AUTH ERROR] Identifiants refusés par le serveur : {auth_err}"
            )
            return False
        except Exception as e:
            print(f"❌ [CENTAURE SMTP ERROR] Échec lors de l'envoi : {e}")
            return False

    @staticmethod
    async def send_email_async(recipient: str, subject: str, html_content: str) -> bool:
        """Enveloppe async pour l'envoi non-bloquant."""
        return await asyncio.to_thread(
            NotificationService._send_single_email_sync,
            recipient,
            subject,
            html_content,
        )

    @staticmethod
    async def notify_crise_activation(
        crise_data: Dict[str, Any], membres: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, int]:
        """Dispatch parallèle des e-mails d'alerte aux membres lors de l'activation."""
        if not membres:
            print("⚠️ [CENTAURE SMTP] Aucun membre fourni pour la notification.")
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
                "⚠️ [CENTAURE SMTP] Aucun destinataire valide trouvé avec une adresse e-mail."
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
        """Envoie un e-mail de convocation individuel lors de l'ajout d'un membre à une crise déjà active."""
        email = membre.get("email")
        if not email:
            print("⚠️ [CENTAURE SMTP] Pas d'adresse e-mail pour ce membre.")
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
