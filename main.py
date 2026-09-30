import sys
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # Charge le fichier .env dès le démarrage

# Ingestion du chemin racine pour le routage de modules Python
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from nicegui import app, ui
from app.core import config
from app.services.database_service import DatabaseService
from app.ui.cockpit import create_cockpit_page
from app.ui.site_agent import create_site_page
from app.ui.login_ui import render_login_page


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
# URL sur écran de garde : /kiosk?token=a8f3b12d-90e4-4c11-b823-1d2e3f4a5b6c
# ----------------------------------------------------------------------
@ui.page("/kiosk")
async def kiosk_page(token: str = None):
    """Accès permanent sécurisé par jeton d'appareil (Kiosque 24/7)."""
    if not token:
        with ui.column().classes(
            "w-full h-screen items-center justify-center bg-slate-950 text-red-500 p-8 text-center"
        ):
            ui.icon("block", size="xl", color="red-5")
            ui.label("⛔ ACCÈS REFUSÉ").classes(
                "text-3xl font-black tracking-widest mt-4"
            )
            ui.label("Jeton d'accès poste (token) manquant dans l'URL.").classes(
                "text-slate-400 text-sm mt-2"
            )
        return

    # Vérification du jeton dans la BDD Supabase
    site_data = await asyncio.to_thread(DatabaseService.get_site_by_kiosk_token, token)

    if not site_data:
        with ui.column().classes(
            "w-full h-screen items-center justify-center bg-slate-950 text-red-500 p-8 text-center"
        ):
            ui.icon("gavel", size="xl", color="red-5")
            ui.label("⛔ JETON INVALIDE OU RÉVOQUÉ").classes(
                "text-3xl font-black tracking-widest mt-4"
            )
            ui.label("Ce poste n'est pas autorisé sur le réseau CENTAURE.").classes(
                "text-slate-400 text-sm mt-2"
            )
        return

    # Enregistre le code site attribué dans le stockage du navigateur client
    app.storage.client["kiosk_site_code"] = site_data["code_site"]

    # Rendu sécurisé de la vue terrain
    create_site_page(site_data["code_site"])


# ----------------------------------------------------------------------
# Route 3 : Route directe /site/{code_site} (Verrouillage contre la triche)
# ----------------------------------------------------------------------
@ui.page("/site/{code_site}")
async def site_agent_page(code_site: str):
    user_role = app.storage.user.get("role", "GUEST")
    is_sg_admin = user_role in ["ADMIN", "SUPERVISEUR_SG", "OPERATEUR_SG"]

    # Vérification si le navigateur a validé un token Kiosque préalable
    assigned_kiosk_site = app.storage.client.get("kiosk_site_code")

    # Si ce n'est PAS un Admin/Opérateur SG authentifié ET que le site ne correspond PAS au token kiosque
    if not is_sg_admin and (
        not assigned_kiosk_site or assigned_kiosk_site.upper() != code_site.upper()
    ):
        with ui.column().classes(
            "w-full h-screen items-center justify-center bg-slate-950 text-red-500 p-8 text-center"
        ):
            ui.icon("shield", size="xl", color="red-5")
            ui.label("⛔ SÉCURITÉ CENTAURE : ACCÈS REFUSÉ").classes(
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


# Lancement du serveur sur le réseau local
ui.run(
    title=f"{config.APP_NAME} - Cockpit",
    storage_secret=config.SECRET_KEY,
    host="0.0.0.0",
    dark=True,
    port=8080,
)
