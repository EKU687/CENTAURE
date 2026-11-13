import sys
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Force la sortie en UTF-8 : sur console Windows (cp1252/cp850), un simple
# print() contenant un emoji (✅/❌) lève une UnicodeEncodeError qui fait
# planter le rendu des pages (HTTP 500). Sous Docker (PROD), l'UTF-8 étant
# déjà actif, ce reparamétrage est sans effet.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Charge le fichier .env dès le démarrage
load_dotenv()

# Ingestion du chemin racine pour le routage de modules Python
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from nicegui import app, ui
from app.core import config
from app.services.database_service import DatabaseService
from app.ui.cockpit import create_cockpit_page
from app.ui.site_agent import create_site_page
from app.ui.login_ui import render_login_page

# ----------------------------------------------------------------------
# Configuration de l'environnement (DEV vs PROD)
# ----------------------------------------------------------------------
ENVIRONMENT = os.getenv("APP_ENV", os.getenv("ENV", "development")).lower()
IS_PROD = ENVIRONMENT in ["production", "prod"]
PORT = int(os.getenv("PORT", 8080))

# Fallback de sécurité si SECRET_KEY est absente de la config
SECRET_KEY = getattr(config, "SECRET_KEY", None) or os.getenv(
    "SECRET_KEY", "centaure_secret_session_key_2026"
)


# ----------------------------------------------------------------------
# Route 0 : Authentification Cockpit Central ( /login )
# ----------------------------------------------------------------------
@ui.page("/login")
def login_page():
    """Page d'authentification pour les administrateurs et opérateurs SG."""
    render_login_page()


# ----------------------------------------------------------------------
# Route 1 : Cockpit Hyperviseur / PC Crise ( / ) - Protégée par Login
# ----------------------------------------------------------------------
@ui.page("/")
async def dashboard_page():
    """Accès au Cockpit Central réservé aux utilisateurs authentifiés."""
    if not app.storage.user.get("authenticated", False):
        ui.navigate.to("/login")
        return

    await create_cockpit_page()


# ----------------------------------------------------------------------
# Route 2 : Postes de Supervision Locaux Kiosque ( Permanent 24/7 )
# URL sur écran de garde : /kiosk?token=c7c18717-1611-4ee2-a3e0-fb7192bcec0b
# ----------------------------------------------------------------------
@ui.page("/kiosk")
async def kiosk_page(token: str = ""):
    """Valide le jeton UUID Supabase, initialise la session client et charge le Poste de Garde."""
    clean_token = str(token).strip() if token else ""

    # Rejet immédiat si jeton absent ou anomalie textuelle évidente
    if not clean_token or any(
        err in clean_token.lower() for err in ["erreur", "introuvable", "none", "null"]
    ):
        with ui.column().classes(
            "w-full h-screen items-center justify-center bg-slate-950 text-red-500 p-8 text-center"
        ):
            ui.icon("screen_lock_portrait", size="xl", color="red-5")
            ui.label("ACCÈS KIOSQUE REFUSÉ").classes(
                "text-2xl font-black text-red-500 tracking-wider mt-4"
            )
            ui.label("Jeton d'accès manquant ou format invalide.").classes(
                "text-slate-300 text-sm mt-2"
            )
        return

    # Validation du jeton via la méthode dédiée du DatabaseService
    try:
        site_data = await asyncio.to_thread(
            DatabaseService.get_site_by_kiosk_token, clean_token
        )
    except Exception as e:
        print(f"❌ Erreur lors de la validation du token Kiosque : {e}")
        site_data = None

    # Jeton non trouvé dans Supabase
    if not site_data:
        with ui.column().classes(
            "w-full h-screen items-center justify-center bg-slate-950 text-amber-500 p-8 text-center"
        ):
            ui.icon("no_accounts", size="xl", color="amber-5")
            ui.label("JETON INCONNU OU EXPIRÉ").classes(
                "text-2xl font-black text-amber-500 tracking-wider mt-4"
            )
            ui.label(
                "Ce jeton Kiosque n'est pas reconnu par le serveur Supabase."
            ).classes("text-slate-300 text-sm mt-2")
        return

    site_code = site_data.get("code_site")
    if not site_code:
        ui.notify("Erreur d'intégrité : code site manquant.", type="negative")
        return

    # 🔑 AUTORISATION : Sauvegarde dans le stockage client de l'onglet/navigateur
    app.storage.client["kiosk_site_code"] = site_code.upper()
    print(f"✅ Accès Kiosque accordé pour le site : {site_code}")

    # Rendu direct de l'interface Poste de Garde pour le site validé
    create_site_page(site_code)


# ----------------------------------------------------------------------
# Route 3 : Route directe /site/{code_site} (Verrouillage contre la triche)
# ----------------------------------------------------------------------
@ui.page("/site/{code_site}")
async def site_agent_page(code_site: str):
    """Interdit l'accès direct par URL sauf pour Admin SG ou Kiosque validé."""
    user_role = app.storage.user.get("role", "GUEST")
    is_sg_admin = user_role in ["ADMIN", "SUPERVISEUR_SG", "OPERATEUR_SG"]

    # Vérification si le navigateur possède le jeton validé pour CE site
    assigned_kiosk_site = app.storage.client.get("kiosk_site_code")

    if not is_sg_admin and (
        not assigned_kiosk_site or assigned_kiosk_site.upper() != code_site.upper()
    ):
        with ui.column().classes(
            "w-full h-screen items-center justify-center bg-slate-950 text-red-500 p-8 text-center"
        ):
            ui.icon("shield", size="xl", color="red-5")
            ui.label("ERROR: SÉCURITÉ CENTAURE : ACCÈS REFUSÉ").classes(
                "text-2xl font-black text-red-500 tracking-wider mt-4"
            )
            ui.label(
                f"L'accès direct à l'URL /site/{code_site} est strictement interdit."
            ).classes("text-slate-300 text-sm mt-2")
            ui.label(
                "Ce poste de garde doit utiliser son URL Kiosque dédiée munie d'un jeton d'accès."
            ).classes("text-slate-400 text-xs italic mt-1")
        return

    create_site_page(code_site)


# ----------------------------------------------------------------------
# Démarrage de l'Application NiceGUI
# ----------------------------------------------------------------------
if __name__ in {"__main__", "__mp_main__"}:
    print(f"CENTAURE Démarré | Mode: {ENVIRONMENT.upper()} | Port: {PORT}")

    app_name = getattr(config, "APP_NAME", "CENTAURE")
    ui.run(
        title=f"{app_name} - Cockpit Central",
        storage_secret=SECRET_KEY,
        host="0.0.0.0",
        port=PORT,
        dark=True,
        reload=not IS_PROD,  # True en DEV, False en PROD
        show=not IS_PROD,  # True en DEV, False en PROD
    )
