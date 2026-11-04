import asyncio
from nicegui import app, ui
from app.core import config
from app.services.database_service import DatabaseService


def render_login_page():
    """Rendu de la page d'authentification du Cockpit Central avec option YubiKey OTP."""

    # Si l'utilisateur est déjà connecté, redirection immédiate vers le Cockpit
    if app.storage.user.get("authenticated", False):
        ui.navigate.to("/")
        return

    with ui.column().classes(
        "w-full h-screen items-center justify-center bg-slate-950 p-4"
    ):
        with ui.card().classes(
            "w-full max-w-md bg-slate-900 text-slate-100 p-8 border border-slate-700 shadow-2xl rounded-xl items-center"
        ):

            # Header Logo & Application
            ui.icon("shield", size="xl", color="red-5").classes("mb-2")
            ui.label(config.APP_NAME).classes(
                "text-3xl font-black tracking-widest text-red-500"
            )
            ui.label(config.APP_SUBTITLE).classes(
                "text-xs text-slate-400 mb-6 font-medium tracking-wide"
            )

            ui.separator().classes("bg-slate-700 w-full mb-6")

            # ------------------------------------------------------------------
            # Option 1 : Connexion Classique (Mot de passe)
            # ------------------------------------------------------------------
            input_user = (
                ui.input(label="Identifiant SG")
                .props("dark outline icon=person")
                .classes("w-full mb-3")
            )
            input_pass = (
                ui.input(label="Mot de passe", password=True)
                .props("dark outline icon=lock")
                .classes("w-full mb-4")
            )

            async def do_password_login():
                if not input_user.value or not input_pass.value:
                    ui.notify(
                        "Veuillez saisir votre identifiant et mot de passe.",
                        type="warning",
                    )
                    return

                btn_login.props("loading")
                user_data = await asyncio.to_thread(
                    DatabaseService.authenticate_user,
                    input_user.value,
                    input_pass.value,
                )
                btn_login.props(remove="loading")

                if user_data:
                    app.storage.user["username"] = user_data["username"]
                    app.storage.user["nom_complet"] = (
                        user_data.get("nom_complet") or user_data["username"]
                    )
                    app.storage.user["role"] = user_data["role"]
                    app.storage.user["authenticated"] = True

                    ui.notify(
                        f"Bienvenue {app.storage.user['nom_complet']} !",
                        type="positive",
                    )
                    ui.navigate.to("/")
                else:
                    ui.notify("Identifiant ou mot de passe incorrect.", type="negative")

            input_pass.on("keydown.enter", do_password_login)

            btn_login = (
                ui.button("SE CONNECTER", icon="login", on_click=do_password_login)
                .props("color=blue-7 font-bold")
                .classes("w-full py-3")
            )

            # ------------------------------------------------------------------
            # Option 2 : Connexion par YubiKey OTP (Mode Portail GNC)
            # ------------------------------------------------------------------
            ui.separator().classes("bg-slate-800 w-full my-6")

            ui.label("Connexion Rapide par YubiKey").classes(
                "text-xs font-bold text-amber-400 mb-2"
            )

            input_yubikey = (
                ui.input(
                    placeholder="Insérez et touchez votre YubiKey...",
                    password=True,  # Forçage natif du mode masqué (type="password")
                )
                .props("dark outline icon=key")
                .classes("w-full mb-2 font-mono")
            )

            async def do_yubikey_login():
                otp_value = input_yubikey.value.strip() if input_yubikey.value else ""

                if not otp_value or len(otp_value) < 12:
                    ui.notify(
                        "👉 Touchez le capteur doré de votre YubiKey...", type="info"
                    )
                    return

                btn_yubikey.props("loading")
                user_data = await asyncio.to_thread(
                    DatabaseService.authenticate_by_yubikey,
                    otp_value,
                )
                btn_yubikey.props(remove="loading")

                if user_data:
                    app.storage.user["username"] = user_data["username"]
                    app.storage.user["nom_complet"] = (
                        user_data.get("nom_complet") or user_data["username"]
                    )
                    app.storage.user["role"] = user_data["role"]
                    app.storage.user["authenticated"] = True

                    ui.notify(
                        f"🔑 Authentification YubiKey réussie ! Bienvenue {app.storage.user['nom_complet']}",
                        type="positive",
                    )
                    ui.navigate.to("/")
                else:
                    ui.notify(
                        "❌ YubiKey non reconnue ou non enregistrée.", type="negative"
                    )
                    input_yubikey.value = ""

            # La YubiKey envoie généralement la touche 'Entrée' à la fin de sa frappe
            input_yubikey.on("keydown.enter", do_yubikey_login)

            btn_yubikey = (
                ui.button(
                    "SE CONNECTER PAR YUBIKEY",
                    icon="vibration",
                    on_click=do_yubikey_login,
                )
                .props("outline color=amber-5 font-bold")
                .classes("w-full py-2 mt-1")
            )

            # Footer Version
            ui.label(
                f"Gouvernement de la Nouvelle-Calédonie • {config.DISPLAY_VERSION}"
            ).classes("text-[10px] text-slate-500 mt-8 font-mono")
