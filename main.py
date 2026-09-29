import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # 👈 Charge le fichier .env dès le démarrage de l'application

# Ingestion du chemin racine pour le routage de modules Python
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from nicegui import ui
from app.core.config import settings
from app.ui.cockpit import create_cockpit_page
from app.ui.site_agent import create_site_page


# Route 1 : Cockpit Hyperviseur / PC Crise ( / )
@ui.page("/")
async def dashboard_page():
    await create_cockpit_page()


# Route 2 : Postes de Supervision Locaux Agents ( /site/DINUM, /site/DOUMER... )
@ui.page("/site/{code_site}")
def site_agent_page(code_site: str):
    create_site_page(code_site)


# Lancement sur le réseau local
ui.run(
    title=f"{settings.APP_NAME} - Cockpit",
    storage_secret=settings.SECRET_KEY,
    host="0.0.0.0",
    dark=True,
    port=8080,
)
