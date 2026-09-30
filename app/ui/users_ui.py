import asyncio
from nicegui import ui
from app.services.database_service import DatabaseService


def render_users_management_view():
    """Vue d'administration des utilisateurs et association des YubiKeys."""
    ui.label("Gestion des Accès & Clés de Sécurité YubiKey").classes(
        "text-2xl font-bold mb-4 text-slate-100"
    )

    users_container = ui.column().classes("w-full gap-3")

    async def register_yubikey_action(user_id: str, username: str):
        """Enrôlement YubiKey en mode touch-only (sans exigence de PIN ni resident key)."""
        ui.notify(
            f"👉 Touchez le capteur doré de la YubiKey dès qu'elle clignote...",
            type="info",
            duration=15.0,
        )

        js_register = f"""
        (async () => {{
            try {{
                const challenge = new Uint8Array(32);
                window.crypto.getRandomValues(challenge);

                const credential = await navigator.credentials.create({{
                    publicKey: {{
                        challenge: challenge,
                        rp: {{ name: "CENTAURE SG NC" }},
                        user: {{
                            id: new TextEncoder().encode("{user_id}"),
                            name: "{username}",
                            displayName: "{username}"
                        }},
                        pubKeyCredParams: [
                            {{ type: "public-key", alg: -7 }},   // ES256 (YubiKey standard)
                            {{ type: "public-key", alg: -257 }}  // RS256
                        ],
                        timeout: 60000,
                        authenticatorSelection: {{
                            authenticatorAttachment: "cross-platform", // Clé USB externe
                            requireResidentKey: false,                 // Ne stocke pas de Passkey avec PIN
                            userVerification: "discouraged"             // Désactive la demande de PIN
                        }},
                        attestation: "none"
                    }}
                }});

                const rawIdArray = Array.from(new Uint8Array(credential.rawId));
                const credentialIdHex = rawIdArray.map(b => b.toString(16).padStart(2, '0')).join('');

                return {{
                    id: credentialIdHex,
                    type: credential.type
                }};
            }} catch (err) {{
                return {{ error: err.message || "Erreur WebAuthn" }};
            }}
        }})()
        """

        try:
            res = await ui.run_javascript(js_register, timeout=60.0)

            if res and isinstance(res, dict) and "error" not in res and "id" in res:
                cred_id = res["id"]
                ok = await asyncio.to_thread(
                    DatabaseService.save_yubikey_credential, user_id, cred_id
                )
                if ok:
                    ui.notify(
                        f"🎉 ENRÔLEMENT RÉUSSI ! YubiKey enregistrée pour {username} !",
                        type="positive",
                        duration=6.0,
                    )
                    await refresh_users()
                else:
                    ui.notify(
                        "❌ Erreur lors de la sauvegarde dans Supabase.",
                        type="negative",
                    )
            else:
                err_msg = (
                    res.get("error", "Erreur inconnue")
                    if isinstance(res, dict)
                    else "Aucune réponse reçue"
                )
                ui.notify(
                    f"❌ Échec de l'enrôlement : {err_msg}",
                    type="warning",
                    duration=6.0,
                )

        except TimeoutError:
            ui.notify(
                "⚠️ Temps écoulé (60s).",
                type="warning",
                duration=5.0,
            )

    def register_yubikey_modal(user_id: str, username: str):
        """Modale d'enregistrement instantané YubiKey (Mode Portail GNC)."""
        with ui.dialog() as dlg, ui.card().classes(
            "w-full max-w-md bg-slate-900 border border-amber-600/80 text-slate-100 p-6 rounded-xl text-center"
        ):
            ui.icon("key", size="lg", color="amber-5").classes("mb-2 self-center")
            ui.label(f"Association YubiKey — {username}").classes(
                "text-xl font-bold text-amber-400"
            )
            ui.label(
                "👉 Touchez le capteur doré de votre YubiKey pour l'enregistrer..."
            ).classes("text-xs text-slate-300 my-3")

            # Champ de capture qui reçoit la frappe de la YubiKey
            input_yubi = (
                ui.input(placeholder="Touchez la YubiKey ici...")
                .props("dark outline autofocus icon=vibration password")
                .classes("w-full font-mono text-center mb-4")
            )

            async def process_yubikey_input():
                val = input_yubi.value.strip()
                if len(val) >= 12:
                    # Extraction des 12 premiers caractères (Clé Publique unique)
                    public_id = val[:12]
                    print(f"🔑 [YUBIKEY] Clé Publique détectée : {public_id}")

                    ok = await asyncio.to_thread(
                        DatabaseService.save_yubikey_public_id, user_id, public_id
                    )
                    if ok:
                        ui.notify(
                            f"🎉 YubiKey [{public_id}] associée avec succès à {username} !",
                            type="positive",
                            duration=5.0,
                        )
                        dlg.close()
                        await refresh_users()
                    else:
                        ui.notify(
                            "❌ Erreur lors de l'enregistrement dans Supabase.",
                            type="negative",
                        )
                else:
                    ui.notify(
                        "⚠️ Signal YubiKey trop court, réessayez.", type="warning"
                    )

            # La YubiKey envoie la touche 'Entrée' à la fin de sa frappe
            input_yubi.on("keydown.enter", process_yubikey_input)

            # Bouton de validation manuelle de secours si besoin
            ui.button(
                "VALIDER L'EMPREINTE", icon="check", on_click=process_yubikey_input
            ).props("color=amber-7 class=w-full mb-2")

            with ui.row().classes("w-full justify-center mt-1"):
                ui.button("Annuler", on_click=dlg.close).props("flat color=grey sm")

        dlg.open()

    async def refresh_users():
        users_container.clear()
        users = await asyncio.to_thread(DatabaseService.get_all_users)

        with users_container:
            if not users:
                ui.label("Aucun utilisateur configuré.").classes(
                    "text-slate-400 italic"
                )

            for user in users:
                with ui.card().classes(
                    "w-full bg-slate-900 border border-slate-700 text-slate-100 p-4 rounded-lg"
                ):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.column().classes("gap-0"):
                            with ui.row().classes("items-center gap-2"):
                                ui.label(
                                    user.get("nom_complet") or user["username"]
                                ).classes("font-bold text-base")
                                ui.badge(
                                    user["role"],
                                    color=(
                                        "blue-7"
                                        if user["role"] == "ADMIN"
                                        else "grey-7"
                                    ),
                                ).classes("text-[10px]")
                            ui.label(f"Identifiant : {user['username']}").classes(
                                "text-xs text-slate-400 font-mono"
                            )

                        # Actions : Éditer, Supprimer & Associer YubiKey
                        with ui.row().classes("gap-2 items-center"):
                            ui.button(
                                "Associer YubiKey",
                                icon="key",
                                on_click=lambda u=user: register_yubikey_modal(
                                    u["id"], u["username"]
                                ),
                            ).props("outline color=amber-5 sm").tooltip(
                                "Enregistrer une clé matérielle FIDO2/YubiKey"
                            )

                            ui.button(
                                icon="edit",
                                on_click=lambda u=user: open_user_dialog(u),
                            ).props("flat round color=primary")

                            ui.button(
                                icon="delete",
                                on_click=lambda u=user: confirm_delete_user(u),
                            ).props("flat round color=negative")

    def open_user_dialog(user=None):
        is_edit = user is not None
        u_data = user or {
            "username": "",
            "nom_complet": "",
            "role": "OPERATEUR_SG",
            "password_hash": "",
        }

        with ui.dialog() as dlg, ui.card().classes(
            "w-full max-w-md bg-slate-900 text-slate-100 p-6 border border-slate-700"
        ):
            ui.label(
                "✏️ Modifier Utilisateur" if is_edit else "➕ Nouvel Utilisateur"
            ).classes("text-lg font-bold text-blue-400 mb-4")

            in_user = ui.input(
                label="Identifiant (login)", value=u_data["username"]
            ).classes("w-full mb-2")
            in_nom = ui.input(
                label="Nom Complet", value=u_data.get("nom_complet", "")
            ).classes("w-full mb-2")
            in_pass = ui.input(
                label="Mot de passe"
                + (" (laisser vide si inchangé)" if is_edit else ""),
                password=True,
            ).classes("w-full mb-2")
            sel_role = ui.select(
                options=["OPERATEUR_SG", "SUPERVISEUR_SG", "ADMIN"],
                value=u_data["role"],
                label="Rôle",
            ).classes("w-full mb-4")

            async def save():
                payload = {
                    "username": in_user.value.strip().lower(),
                    "nom_complet": in_nom.value.strip(),
                    "role": sel_role.value,
                }
                if is_edit:
                    payload["id"] = u_data["id"]
                if in_pass.value:
                    payload["password_hash"] = in_pass.value

                ok = await asyncio.to_thread(DatabaseService.save_user, payload)
                if ok:
                    ui.notify("Utilisateur enregistré !", type="positive")
                    dlg.close()
                    await refresh_users()

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Annuler", on_click=dlg.close).props("flat color=grey")
                ui.button("Enregistrer", icon="save", on_click=save).props("color=blue")

        dlg.open()

    def confirm_delete_user(user):
        with ui.dialog() as dlg, ui.card().classes(
            "bg-slate-900 text-white p-6 border border-red-800"
        ):
            ui.label(f"Supprimer l'utilisateur {user['username']} ?").classes(
                "text-lg font-bold text-red-400 mb-4"
            )

            async def do_del():
                ok = await asyncio.to_thread(DatabaseService.delete_user, user["id"])
                if ok:
                    ui.notify("Utilisateur supprimé.", type="warning")
                    dlg.close()
                    await refresh_users()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Annuler", on_click=dlg.close).props("flat color=grey")
                ui.button("Supprimer", color="red", on_click=do_del)

        dlg.open()

    ui.button("➕ Ajouter un Utilisateur", on_click=lambda: open_user_dialog()).props(
        "color=positive sm class='mb-4'"
    )

    ui.timer(0.01, refresh_users, once=True)
