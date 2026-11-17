import asyncio
import os
import traceback
from nicegui import app, ui
from app.core import config
from app.services.database_service import DatabaseService
from app.models.site import SiteCritique
import app.ui.crises as crises_ui
import app.ui.annuaire_ui as annuaire_ui
import app.ui.users_ui as users_ui

# État global pour le rafraîchissement automatique
current_sites = []
dialog_open = False  # Flag pour désactiver le polling quand un dialogue est ouvert
site_cards_map = {}  # Mapping site_code -> ui.card pour les mises à jour incrémentales


def get_status_color(level: str) -> str:
    mapping = {
        "S1": "positive",
        "T1": "positive",
        "S2": "warning",
        "T2": "warning",
        "S3": "orange-8",
        "T3": "orange-8",
        "S4": "negative",
        "T4": "negative",
    }
    return mapping.get(level, "grey")


def get_status_icon(level: str) -> str:
    """Retourne l'icône correspondante au niveau pour l'accessibilité (daltoniens)."""
    icon_mapping = {
        "S1": "check_circle",
        "T1": "check_circle",
        "S2": "info",
        "T2": "info",
        "S3": "warning",
        "T3": "warning",
        "S4": "gavel",
        "T4": "gavel",
    }
    return icon_mapping.get(level, "help_outline")


async def handle_global_s4():
    """Déclenche le passage S4 direct sur tous les sites."""
    print("🔴 [COCKPIT] Clic sur ALERTE GÉNÉRALE S4")
    ok = await asyncio.to_thread(DatabaseService.declencher_s4_general)
    if ok:
        ui.notify(
            "🚨 ALERTE GÉNÉRALE S4 DÉCLENCHÉE SUR TOUS LES SITES !",
            type="negative",
            duration=5.0,
        )
        ui.run_javascript("""
            const audio = new Audio("https://assets.mixkit.co/sfx/270/270.mp3");
            audio.volume = 0.5;
            audio.play().catch(e => console.log("Audio play failed:", e));
        """)
        ui.navigate.reload()
    else:
        ui.notify("❌ Échec lors du déclenchement de l'alerte S4 !", type="warning")


async def handle_global_s1():
    """Déclenche le retour S1 direct sur tous les sites."""
    print("🟢 [COCKPIT] Clic sur RETOUR S1 GENERAL")
    ok = await asyncio.to_thread(DatabaseService.reinitialiser_tous_sites_s1)
    if ok:
        ui.notify(
            "✅ TOUS LES SITES SONT REPASSÉS EN POSTURE SÛRETÉ S1 !",
            type="positive",
            duration=5.0,
        )
        ui.run_javascript("""
            const audio = new Audio("https://assets.mixkit.co/sfx/286/286.mp3");
            audio.volume = 0.3;
            audio.play().catch(e => console.log("Audio play failed:", e));
        """)
        ui.navigate.reload()
    else:
        ui.notify("❌ Échec lors du retour S1 !", type="warning")


async def open_wall_link_dialog():
    """Affiche l'URL de l'écran mural (copiable/ouvrable) pour l'installer sur un poste."""
    if not current_sites:
        ui.notify("Aucun site suivi : impossible de générer le lien mural.", type="warning")
        return

    # Le mur accepte n'importe quel jeton kiosque valide ; on utilise le 1er site connu.
    code_reference = current_sites[0].code_site
    try:
        kiosk_url = await asyncio.to_thread(
            DatabaseService.get_kiosk_url_for_site, code_reference
        )
    except Exception as err:
        print(f"⚠️ Erreur génération URL murale : {err}")
        kiosk_url = None
    if not kiosk_url:
        ui.notify("Erreur de génération du lien mural.", type="negative")
        return

    wall_url = kiosk_url.replace("/kiosk?", "/wall?")

    with ui.dialog() as dialog, ui.card().classes(
        "w-full max-w-xl bg-slate-900 border border-slate-700 text-slate-100 p-6 gap-4"
    ):
        with ui.row().classes("items-center gap-2 w-full border-b border-slate-800 pb-3 mb-2"):
            ui.icon("monitor", color="amber-4", size="md")
            ui.label("Écran Mural — Supervision Globale").classes(
                "text-lg font-bold text-amber-400"
            )
            ui.button(icon="close", on_click=dialog.close).props(
                "flat round dense color=slate-400"
            )

        ui.label(
            "À installer une seule fois sur l'écran de la salle : ouvrir l'URL "
            "ci-dessous en plein écran (F11), puis cliquer une fois sur "
            "« SON D'ALERTE » pour armer la sirène S4."
        ).classes("text-xs text-slate-400 leading-relaxed")

        champ = (
            ui.input(value=wall_url)
            .props("dense readonly outline dark")
            .classes("w-full font-mono text-xs text-amber-300 select-all")
        )

        with ui.row().classes("w-full justify-end gap-2"):
            ui.button(
                "COPIER",
                icon="content_copy",
                on_click=lambda: ui.run_javascript(
                    f"navigator.clipboard.writeText({wall_url!r})"
                ),
            ).props("color=amber outline sm")

            ui.button(
                "OUVRIR L'ÉCRAN",
                icon="open_in_new",
                on_click=lambda: ui.run_javascript(f"window.open({wall_url!r}, '_blank')"),
            ).props("color=amber sm font-bold")

    dialog.open()


def open_new_site_dialog():
    """Boîte de dialogue de création d'un nouveau site critique."""
    global dialog_open
    dialog_open = True

    with ui.dialog() as dialog, ui.card().classes(
        "w-full max-w-lg bg-slate-900 border border-slate-700 text-slate-100 p-6"
    ):

        def on_dialog_hide():
            global dialog_open
            dialog_open = False

        dialog.on("hide", on_dialog_hide)

        ui.label("Ajouter un Nouveau Site Sensible").classes(
            "text-xl font-bold text-blue-400 mb-4"
        )

        input_code = ui.input(label="Code du site (ex: CTP, CHT, PARC-01)").classes(
            "w-full"
        )
        input_nom = ui.input(label="Nom complet de l'infrastructure").classes("w-full")
        input_loc = ui.input(label="Localisation / Commune").classes("w-full")

        async def save_new_site():
            if input_code.value and input_nom.value:
                ok = await asyncio.to_thread(
                    DatabaseService.update_site_info,
                    input_code.value,
                    input_nom.value,
                    input_loc.value or "",
                    None,
                )
                if ok:
                    ui.notify("Nouveau site ajouté avec succès !", type="positive")
                    dialog.close()
                    ui.navigate.reload()
                else:
                    ui.notify(
                        "Erreur lors de la création (Code probablement existant).",
                        type="negative",
                    )
            else:
                ui.notify(
                    "Le Code et le Nom du site sont obligatoires.", type="warning"
                )

        with ui.row().classes("justify-end w-full gap-2 mt-4"):
            ui.button("Annuler", on_click=dialog.close).props("flat color=grey")
            ui.button("Créer le site", icon="add", on_click=save_new_site).props(
                "color=blue"
            )

    dialog.open()


def open_inspection_dialog(site):
    """Boîte de dialogue d'inspection et de gestion des consignes (Corrigée & Blindée UI)."""
    global dialog_open
    dialog_open = True

    try:
        # Extraction sécurisée des informations du site (dict ou Pydantic/Objet)
        if isinstance(site, dict):
            site_code_val = site.get("code_site") or site.get("code", "")
            site_nom_val = site.get("nom", "Site")
            site_id_val = site.get("id")
            site_loc_val = site.get("localisation", "")
            surete_val = site.get("surete_niveau", "S1")
            tech_val = site.get("technique_niveau", "T1")
            anomalies_list = site.get("anomalies", []) or []
            active_proto_id = site.get("active_protocol_id") or site.get("protocol_id")
        else:
            site_code_val = getattr(site, "code_site", getattr(site, "code", ""))
            site_nom_val = getattr(site, "nom", "Site")
            site_id_val = getattr(site, "id", None)
            site_loc_val = getattr(site, "localisation", "") or ""
            surete_val = getattr(site, "surete_niveau", "S1")
            tech_val = getattr(site, "technique_niveau", "T1")
            anomalies_list = getattr(site, "anomalies", []) or []
            active_proto_id = getattr(
                site, "active_protocol_id", getattr(site, "protocol_id", None)
            )

        print(f"🔍 [DEBUG] Ouverture dialogue pour : {site_nom_val} ({site_code_val})")

        # Generer l'URL Kiosque avec Token UUID
        try:
            real_kiosk_url = DatabaseService.get_kiosk_url_for_site(site_code_val)
        except Exception as kiosk_err:
            print(f"⚠️ Erreur génération URL Kiosque: {kiosk_err}")
            real_kiosk_url = (
                f"https://gnc-centaure.fly.dev/kiosk?token=erreur-recuperation"
            )

        # URL Écran Mural (supervision globale) : même jeton que le poste de garde
        wall_url = real_kiosk_url.replace("/kiosk?", "/wall?")

        # Construction du Dialogue Unique
        with ui.dialog() as dialog, ui.card().classes(
            "w-full max-w-2xl bg-slate-900 border border-slate-700 text-slate-100 p-6 gap-4 shadow-2xl max-h-[90vh] overflow-y-auto"
        ):

            def on_dialog_hide():
                global dialog_open
                dialog_open = False

            dialog.on("hide", on_dialog_hide)

            # En-tête
            with ui.row().classes(
                "w-full items-center justify-between border-b border-slate-800 pb-3"
            ):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("settings", color="blue-4", size="md")
                    ui.label(
                        f"GESTION OPÉRATIONNELLE — {site_nom_val.upper()}"
                    ).classes("text-lg font-bold")
                ui.button(icon="close", on_click=dialog.close).props(
                    "flat round dense color=slate-400"
                )

            # ----------------------------------------------------------------------
            # 1. Admin Niveaux S/T + Sélection du Protocole Spécifique + Motif
            # ----------------------------------------------------------------------
            with ui.column().classes(
                "w-full bg-slate-800/80 p-4 rounded border border-slate-700 my-2 gap-3"
            ):
                ui.label("Administration des Niveaux & Événements").classes(
                    "text-sm font-bold text-slate-300"
                )

                with ui.row().classes("w-full gap-4 items-center flex-wrap"):
                    select_s = ui.select(
                        options=["S1", "S2", "S3", "S4"],
                        value=surete_val,
                        label="Niveau Sûreté",
                    ).classes("w-40")
                    select_t = ui.select(
                        options=["T1", "T2", "T3", "T4"],
                        value=tech_val,
                        label="Niveau Technique",
                    ).classes("w-40")

                select_protocol = ui.select(
                    options={},
                    label="Protocole à appliquer pour cette posture",
                ).classes("w-full mt-1")

                async def load_protocols_for_select():
                    try:
                        protocols = (
                            await asyncio.to_thread(
                                DatabaseService.get_site_protocols, site_code_val
                            )
                            or []
                        )
                        filtered = {
                            p["id"]: f"[{p['niveau']}] {p['titre']}"
                            for p in protocols
                            if p.get("niveau") in [select_s.value, select_t.value]
                        }
                        if not filtered and protocols:
                            filtered = {
                                p["id"]: f"[{p['niveau']}] {p['titre']}"
                                for p in protocols
                            }

                        select_protocol.options = filtered
                        if filtered:
                            if active_proto_id and active_proto_id in filtered:
                                select_protocol.value = active_proto_id
                            else:
                                select_protocol.value = list(filtered.keys())[0]
                        else:
                            select_protocol.value = None
                        select_protocol.update()
                    except Exception as err:
                        print(f"⚠️ Erreur chargement protocoles: {err}")

                select_s.on_value_change(load_protocols_for_select)
                select_t.on_value_change(load_protocols_for_select)

                input_motif = ui.input(
                    label="Motif / Commentaire (ex: Visite du Ministre, Réunion GNC...)",
                    placeholder="Renseigner la raison du changement de niveau...",
                ).classes("w-full mt-1")

                async def save_status():
                    ok = await asyncio.to_thread(
                        DatabaseService.update_site_status,
                        site_id_val,
                        select_s.value,
                        select_t.value,
                        input_motif.value,
                        select_protocol.value,
                    )
                    if ok:
                        if select_s.value == "S4":
                            ui.notify(
                                f"⚠️ ORDRE DE CONFINEMENT DÉCLENCHÉ SUR {site_code_val} !",
                                type="negative",
                            )
                        else:
                            ui.notify(
                                "Statuts S/T et protocole consignés avec succès !",
                                type="positive",
                            )
                        dialog.close()
                        ui.navigate.reload()

                ui.button(
                    "Appliquer & Consigner", icon="save", on_click=save_status
                ).props("color=blue sm").classes("mt-2 self-end")

            # ----------------------------------------------------------------------
            # 2. Gestion Dynamique des Protocoles du Site
            # ----------------------------------------------------------------------
            with ui.expansion(
                "📜 Éditer la Fiche & Identité du Site", icon="edit"
            ).classes("w-full bg-slate-800 border border-slate-700 rounded my-2"):
                with ui.column().classes("p-4 gap-4 w-full"):
                    with ui.row().classes("w-full gap-3"):
                        edit_nom = ui.input(
                            label="Nom du site", value=site_nom_val
                        ).classes("w-1/2")
                        edit_loc = ui.input(
                            label="Localisation", value=site_loc_val
                        ).classes("w-1/2")

                    async def update_info_base():
                        ok = await asyncio.to_thread(
                            DatabaseService.update_site_info,
                            site_id_val,
                            edit_nom.value,
                            edit_loc.value,
                            None,
                        )
                        if ok:
                            ui.notify(
                                "Nom et Localisation mis à jour !", type="positive"
                            )
                            ui.navigate.reload()

                    ui.button(
                        "Mettre à jour l'identité",
                        icon="check",
                        on_click=update_info_base,
                    ).props("color=blue sm")

            # ----------------------------------------------------------------------
            # 3. SÉCURITÉ POSTE DE GARDE : LIEN KIOSQUE SÉCURISÉ (ACCÈS DIRECT)
            # ----------------------------------------------------------------------
            with ui.column().classes(
                "w-full bg-slate-800/90 p-4 rounded border border-slate-700 my-2 gap-2"
            ):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("screen_lock_portrait", color="blue-4", size="sm")
                    ui.label("URL Sécurisée Poste de Garde (24/7)").classes(
                        "text-xs font-bold text-slate-200"
                    )

                ui.input(value=real_kiosk_url).props(
                    "dense readonly outline dark"
                ).classes("w-full font-mono text-xs text-blue-300 select-all")

                with ui.row().classes("items-center gap-2 mt-2"):
                    ui.icon("monitor", color="amber-4", size="sm")
                    ui.label("URL Écran Mural — Supervision Globale (salle PCO)").classes(
                        "text-xs font-bold text-slate-200"
                    )

                ui.input(value=wall_url).props(
                    "dense readonly outline dark"
                ).classes("w-full font-mono text-xs text-amber-300 select-all")

            # ----------------------------------------------------------------------
            # 4. Suivi & Anomalies Enregistrées
            # ----------------------------------------------------------------------
            ui.label("Historique & Maintenances Actives").classes(
                "text-lg font-bold text-amber-400 mt-2"
            )
            if anomalies_list:
                with ui.column().classes("w-full gap-2 mb-4"):
                    for ano in anomalies_list:
                        ano_id = getattr(ano, "id", None) or (
                            ano.get("id") if isinstance(ano, dict) else None
                        )
                        ano_domaine = getattr(ano, "domaine", "") or (
                            ano.get("domaine") if isinstance(ano, dict) else ""
                        )
                        ano_equipement = getattr(ano, "equipement", "") or (
                            ano.get("equipement") if isinstance(ano, dict) else ""
                        )
                        ano_desc = getattr(ano, "description", "") or (
                            ano.get("description") if isinstance(ano, dict) else ""
                        )

                        with ui.row().classes(
                            "w-full justify-between items-center bg-slate-800 p-3 rounded border border-slate-700"
                        ):
                            with ui.column().classes("gap-0"):
                                ui.label(f"[{ano_domaine}] {ano_equipement}").classes(
                                    "font-bold text-sm text-slate-200"
                                )
                                ui.label(ano_desc or "Aucune description").classes(
                                    "text-xs text-slate-400"
                                )

                            async def resolve_ano_action(target_id=ano_id):
                                ok = await asyncio.to_thread(
                                    DatabaseService.resolve_anomalie, target_id
                                )
                                if ok:
                                    ui.notify("Anomalie résolue !", type="positive")
                                    dialog.close()
                                    ui.navigate.reload()

                            ui.button(
                                "Résoudre", icon="check", on_click=resolve_ano_action
                            ).props("color=green flat sm")
            else:
                ui.label("Aucune anomalie active.").classes(
                    "text-sm text-slate-400 italic mb-4"
                )

            # ----------------------------------------------------------------------
            # 5. Supprimer le site & Fermeture
            # ----------------------------------------------------------------------
            with ui.row().classes(
                "w-full justify-between items-center border-t border-slate-700 pt-4 mt-4"
            ):

                def confirm_delete():
                    with ui.dialog() as del_dialog, ui.card().classes(
                        "bg-slate-900 border border-red-800 text-white p-6"
                    ):
                        ui.label(
                            f"Voulez-vous vraiment SUPPRIMER le site {site_code_val} ?"
                        ).classes("text-lg font-bold text-red-400 mb-4")
                        with ui.row().classes("justify-end gap-2 w-full"):
                            ui.button("Annuler", on_click=del_dialog.close).props(
                                "flat color=grey"
                            )

                            async def do_delete():
                                ok = await asyncio.to_thread(
                                    DatabaseService.delete_site, site_id_val
                                )
                                if ok:
                                    ui.notify("Site supprimé !", type="negative")
                                    del_dialog.close()
                                    dialog.close()
                                    ui.navigate.reload()

                            ui.button(
                                "Supprimer définitivement",
                                color="red",
                                on_click=do_delete,
                            )
                    del_dialog.open()

                ui.button(
                    "Supprimer ce site", icon="delete", on_click=confirm_delete
                ).props("flat color=red sm")
                ui.button("FERMER", on_click=dialog.close).props(
                    "color=slate-700 text-slate-200"
                )

            # Chargement initial des protocoles au show
            dialog.on("show", load_protocols_for_select)

        dialog.open()

    except Exception as global_err:
        print(f"🔥 ERREUR CRITIQUE OPEN_DIALOG : {global_err}")
        traceback.print_exc()
        ui.notify(
            f"Impossible d'ouvrir la gestion du site : {global_err}", type="negative"
        )


async def create_cockpit_page():
    """Interface du Cockpit Central avec gestion multi-rôles dont CRISE_SG."""
    await ui.context.client.connected()
    # Anneau de mise en évidence de la cellule de crise ciblée depuis une carte site.
    ui.add_head_html(
        "<style>"
        ".crise-focus-ring{outline:4px solid #fbbf24 !important;"
        " box-shadow:0 0 28px rgba(251,191,36,.65) !important; border-radius:8px;}"
        "</style>"
    )
    user_role = app.storage.user.get("role", "GUEST")
    user_name = app.storage.user.get(
        "nom_complet", app.storage.user.get("username", "Utilisateur")
    )

    # MATRICE DES DROITS RBAC
    is_admin = user_role == "ADMIN"
    is_superviser = user_role == "SUPERVISEUR_SG"
    is_operator = user_role == "OPERATEUR_SG"
    is_crisis_member = user_role in ["CRISE_SG", "CELLULE_CRISE"]

    can_access_hypervision = is_admin or is_superviser or is_operator
    can_access_crises = is_admin or is_superviser or is_crisis_member
    can_trigger_global_alerts = is_admin or is_superviser or is_operator
    can_manage_sites = is_admin or is_superviser

    # HEADER GLOBAL
    with ui.header().classes(
        "bg-slate-900 text-white items-center justify-between px-6 py-2 border-b border-slate-700"
    ):
        with ui.row().classes("items-center gap-4"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("shield", size="md", color="red-5")
                ui.label(config.APP_NAME).classes(
                    "text-xl font-bold tracking-widest text-red-500"
                )
                ui.label("| GNC").classes("text-xs text-slate-400 font-medium")

                ui.badge(config.DISPLAY_VERSION, color="slate-800").classes(
                    "text-[10px] font-mono border border-slate-700 text-slate-300 px-2 py-0.5 ml-1"
                )
                _env = os.getenv("APP_ENV", os.getenv("ENV", "development")).upper()
                ui.badge(
                    f"ENV {_env}",
                    color="positive" if _env in ("PRODUCTION", "PROD") else "warning",
                ).classes(
                    "text-[10px] font-mono border border-slate-700 px-2 py-0.5 ml-1"
                ).tooltip("Environnement d'exécution (APP_ENV)")

            with ui.tabs().classes("text-white") as tabs:
                tab_sites = None
                tab_crises = None
                tab_annuaire = None
                tab_users = None
                tab_journal = None

                if can_access_hypervision:
                    tab_sites = ui.tab("Sites Sensibles", icon="grid_view")

                if can_access_crises:
                    tab_crises = ui.tab("Cellules de Crise", icon="warning")
                    tab_annuaire = ui.tab("Annuaire RH", icon="people")

                if can_access_hypervision:
                    tab_journal = ui.tab("Journal des Alertes", icon="history")

                if is_admin:
                    tab_users = ui.tab("Gestion Accès", icon="manage_accounts")

        with ui.row().classes("items-center gap-3"):
            if can_trigger_global_alerts:
                ui.button(
                    "RETOUR S1 GENERAL", icon="verified", on_click=handle_global_s1
                ).props("color=positive font-bold sm")
                ui.button(
                    "ALERTE GÉNÉRALE S4", icon="gavel", on_click=handle_global_s4
                ).props("color=red font-bold animate-pulse sm")

            ui.badge("TEMPS RÉEL", color="positive")

            role_color_map = {
                "ADMIN": "purple-5",
                "SUPERVISEUR_SG": "blue-5",
                "CRISE_SG": "orange-5",
                "OPERATEUR_SG": "teal-5",
            }
            role_color = role_color_map.get(user_role, "slate-400")

            with ui.row().classes(
                "items-center gap-2 bg-slate-800/80 px-3 py-1 rounded-full border border-slate-700 ml-2"
            ):
                ui.icon("account_circle", size="sm", color="slate-300")
                with ui.column().classes("gap-0 leading-none"):
                    ui.label(user_name).classes("text-xs font-bold text-slate-200")
                    ui.label(user_role).classes(
                        f"text-[9px] font-mono text-{role_color}"
                    )

            def do_logout():
                current_user_name = app.storage.user.get("nom_complet", "Utilisateur")
                app.storage.user.clear()
                ui.notify(
                    f"Déconnexion réussie. À bientôt {current_user_name} !", type="info"
                )
                ui.navigate.to("/login")

            ui.button(icon="logout", on_click=do_logout).props(
                "flat round color=red-4 sm"
            ).tooltip("Se déconnecter du Cockpit")

    default_tab = tab_crises if is_crisis_member else tab_sites

    with ui.tab_panels(tabs, value=default_tab).classes(
        "w-full bg-slate-950 min-h-screen text-slate-100 p-6"
    ):
        # ONGLET 1 : HYPERVISION DES SITES SENSIBLES
        if can_access_hypervision and tab_sites:
            with ui.tab_panel(tab_sites):
                with ui.row().classes("items-center justify-between w-full mb-6"):
                    with ui.row().classes("items-center gap-4"):
                        ui.label("Hypervision des Sites Sensibles").classes(
                            "text-2xl font-bold tracking-tight"
                        )
                        if can_manage_sites:
                            ui.button(
                                "Nouveau Site",
                                icon="add",
                                on_click=open_new_site_dialog,
                            ).props("color=blue sm font-bold")

                    with ui.row().classes("items-center gap-3"):
                        search_input = (
                            ui.input(placeholder="Rechercher un site...")
                            .props("dense dark icon=search outline")
                            .classes("w-64")
                        )
                        ui.button(
                            "Rafraîchir",
                            icon="refresh",
                            on_click=lambda: render_sites_grid(search_input.value),
                        ).props("flat color=white sm")
                        ui.button(
                            "Écran mural",
                            icon="monitor",
                            on_click=open_wall_link_dialog,
                        ).props("color=blue sm outline font-bold").tooltip(
                            "URL d'installation de l'écran de supervision globale (salle PCO)"
                        )

                global current_sites
                current_sites = (
                    await asyncio.to_thread(DatabaseService.get_all_sites) or []
                )

                kpi_banner_container = ui.row().classes(
                    "w-full gap-4 mb-6 justify-center"
                )

                def update_kpi_banner():
                    kpi_banner_container.clear()
                    s4_count = sum(
                        1 for site in current_sites if site.surete_niveau == "S4"
                    )
                    s3_count = sum(
                        1 for site in current_sites if site.surete_niveau == "S3"
                    )
                    t4_count = sum(
                        1 for site in current_sites if site.technique_niveau == "T4"
                    )
                    t3_count = sum(
                        1 for site in current_sites if site.technique_niveau == "T3"
                    )

                    with kpi_banner_container:
                        if s4_count > 0:
                            ui.badge(f"🚨 {s4_count} S4", color="red").classes(
                                "text-2xl font-bold p-4 animate-pulse"
                            )
                        if s3_count > 0:
                            ui.badge(f"⚠️ {s3_count} S3", color="amber").classes(
                                "text-2xl font-bold p-4 animate-pulse"
                            )
                        if t4_count > 0:
                            ui.badge(f"🛠️ {t4_count} T4", color="orange").classes(
                                "text-2xl font-bold p-4 animate-pulse"
                            )
                        if t3_count > 0:
                            ui.badge(f"🔧 {t3_count} T3", color="orange-8").classes(
                                "text-xl font-bold p-4"
                            )

                update_kpi_banner()

                sites_grid_classes = "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 w-full"

                sites_grid = ui.grid().classes(sites_grid_classes)

                def render_sites_grid(filter_text=""):
                    sites_grid.clear()
                    sites_grid.classes(sites_grid_classes)
                    with sites_grid:
                        for site in current_sites:
                            if (
                                filter_text
                                and filter_text.lower() not in site.nom.lower()
                                and filter_text.lower() not in site.code_site.lower()
                            ):
                                continue

                            if site.surete_niveau == "S4":
                                card_style = "bg-red-950/90 border-4 border-red-600 text-slate-100 p-5 shadow-2xl animate-pulse"
                            elif site.surete_niveau == "S3":
                                card_style = "bg-amber-950/40 border-2 border-amber-500 text-slate-100 p-5 shadow-xl shadow-amber-500/20 animate-pulse"
                            elif (
                                site.surete_niveau == "S2"
                                or site.technique_niveau in ["T2", "T3", "T4"]
                            ):
                                card_style = "bg-slate-900 border border-amber-600/60 text-slate-100 p-5 shadow-lg"
                            else:
                                card_style = "bg-slate-800 border border-slate-700 text-slate-100 p-5 shadow-lg"

                            with ui.card().classes(
                                card_style + " cursor-pointer"
                            ) as site_card:

                                def go_to_crises_cellule(site_target=site):
                                    """Branchement direct : clic sur la carte site ->
                                    onglet « Cellules de Crise », avec mise en évidence
                                    de la cellule rattachée à ce site (site_impacte_id)."""
                                    if tab_crises is None:
                                        ui.notify(
                                            "Votre rôle n'a pas accès à l'onglet « Cellules de Crise ».",
                                            type="warning",
                                        )
                                        return
                                    focus_site_id = str(
                                        getattr(site_target, "id", "") or ""
                                    )
                                    if focus_site_id:
                                        app.storage.client["crise_focus_site_id"] = (
                                            focus_site_id
                                        )
                                    tabs.set_value(tab_crises)
                                    if focus_site_id:
                                        ui.run_javascript(
                                            "setTimeout(() => {"
                                            "document.querySelectorAll('.crise-focus-ring')"
                                            ".forEach(e => e.classList.remove('crise-focus-ring'));"
                                            "const el = document.querySelector("
                                            f"'[data-crise-site=\"{focus_site_id}\"]');"
                                            "if (el) { el.classList.add('crise-focus-ring');"
                                            " el.scrollIntoView({behavior:'smooth', block:'center'}); }"
                                            "}, 400);"
                                        )

                                site_card.on("click", go_to_crises_cellule)
                                site_card.tooltip(
                                    "Clic → onglet « Cellules de Crise » (cellule rattachée au site mise en évidence)"
                                )

                                with ui.row().classes(
                                    "justify-between items-center w-full mb-2"
                                ):
                                    ui.label(site.code_site).classes(
                                        "font-extrabold text-xl text-slate-100"
                                    )
                                    ui.label(site.localisation or "N/C").classes(
                                        "text-xs text-slate-400"
                                    )

                                ui.label(site.nom).classes(
                                    "text-sm text-slate-300 mb-2 h-10 line-clamp-2"
                                )

                                if site.surete_niveau == "S4":
                                    with ui.row().classes(
                                        "w-full bg-red-600 text-white p-2 rounded justify-center items-center gap-2 mb-3"
                                    ):
                                        ui.icon("warning", size="sm")
                                        ui.label("CONFINEMENT EN COURS").classes(
                                            "font-black text-xs tracking-wider"
                                        )
                                elif site.surete_niveau == "S3":
                                    with ui.row().classes(
                                        "w-full bg-amber-600/80 text-white p-1.5 rounded justify-center items-center gap-2 mb-3"
                                    ):
                                        ui.icon("priority_high", size="xs")
                                        ui.label("ALERTE SÛRETÉ S3").classes(
                                            "font-bold text-xs tracking-wider"
                                        )

                                with ui.row().classes(
                                    "gap-3 w-full mb-4 justify-start"
                                ):
                                    with ui.row().classes("items-center gap-1"):
                                        ui.label("Sûreté :").classes(
                                            "text-xs text-slate-400"
                                        )
                                        with ui.row().classes("items-center gap-1"):
                                            ui.icon(
                                                get_status_icon(site.surete_niveau),
                                                size="xs",
                                            )
                                            ui.badge(
                                                site.surete_niveau,
                                                color=get_status_color(
                                                    site.surete_niveau
                                                ),
                                            ).classes("font-bold")

                                    with ui.row().classes("items-center gap-1"):
                                        ui.label("Technique :").classes(
                                            "text-xs text-slate-400"
                                        )
                                        with ui.row().classes("items-center gap-1"):
                                            ui.icon(
                                                get_status_icon(site.technique_niveau),
                                                size="xs",
                                            )
                                            ui.badge(
                                                site.technique_niveau,
                                                color=get_status_color(
                                                    site.technique_niveau
                                                ),
                                            ).classes("font-bold")

                                async def open_site_kiosk_screen(site_code: str):
                                    url = await asyncio.to_thread(
                                        DatabaseService.get_kiosk_url_for_site,
                                        site_code,
                                    )
                                    if url:
                                        ui.navigate.to(url, new_tab=True)
                                    else:
                                        ui.notify(
                                            f"❌ Jeton Kiosque introuvable pour {site_code}",
                                            type="warning",
                                        )

                                make_site_screen_handler = lambda code_target=site.code_site: lambda: open_site_kiosk_screen(
                                    code_target
                                )

                                with ui.row().classes("w-full gap-2 mt-auto"):
                                    # Bouton explicite de branchement direct (le clic
                                    # sur la carte entière fait la même chose).
                                    btn_cellule = ui.button(
                                        icon="arrow_circle_right",
                                        on_click=go_to_crises_cellule,
                                    ).props("sm color=red-7").props(
                                        'onclick="event.stopPropagation()"'
                                    ).classes("flex-1").tooltip(
                                        "Basculer sur l'onglet « Cellules de Crise » "
                                        "(cellule rattachée au site mise en évidence)"
                                    )
                                    if can_manage_sites:
                                        make_manage_handler = lambda s_target=site: lambda: open_inspection_dialog(
                                            s_target
                                        )
                                        ui.button(
                                            "Gérer", on_click=make_manage_handler()
                                        ).props("sm outline color=grey-4").props(
                                            'onclick="event.stopPropagation()"'
                                        ).classes(
                                            "flex-1"
                                        )
                                        ui.button(
                                            "Écran Site",
                                            icon="open_in_new",
                                            on_click=make_site_screen_handler(),
                                        ).props("sm color=blue-7").props(
                                            'onclick="event.stopPropagation()"'
                                        ).classes(
                                            "flex-1"
                                        ).tooltip(
                                            "Ouvrir l'écran de supervision Kiosque sécurisé"
                                        )
                                    else:
                                        ui.button(
                                            "Écran Site",
                                            icon="open_in_new",
                                            on_click=make_site_screen_handler(),
                                        ).props("sm color=blue-7").props(
                                            'onclick="event.stopPropagation()"'
                                        ).classes(
                                            "flex-1"
                                        ).tooltip(
                                            "Ouvrir l'écran de supervision Kiosque sécurisé"
                                        )

                async def refresh_sites():
                    global current_sites, dialog_open
                    if not dialog_open:
                        current_sites = (
                            await asyncio.to_thread(DatabaseService.get_all_sites) or []
                        )
                        update_kpi_banner()
                        render_sites_grid(search_input.value)

                ui.timer(5.0, refresh_sites, once=False)
                search_input.on(
                    "update:model-value", lambda e: render_sites_grid(e.value)
                )
                render_sites_grid()

                with ui.row().classes(
                    "w-full items-center gap-2 mt-6 flex-wrap text-[10px] text-slate-500"
                ):
                    ui.label("LÉGENDE").classes(
                        "font-bold text-slate-400 tracking-wider text-[10px]"
                    )
                    ui.badge("S1 / T1 — niveau nominal", color="positive").classes(
                        "text-[9px]"
                    )
                    ui.badge(
                        "S2 / T2 — surveillance renforcée (bordure ambre)",
                        color="warning",
                    ).classes("text-[9px]")
                    ui.badge("S3 / T3 — alerte (carte ambre)", color="orange-8").classes(
                        "text-[9px]"
                    )
                    ui.badge(
                        "S4 / T4 — confinement en cours (carte rouge)", color="negative"
                    ).classes("text-[9px]")

        # ONGLET 2 : CELLULES DE CRISE SG
        if can_access_crises and tab_crises:
            with ui.tab_panel(tab_crises):
                @ui.refreshable
                async def render_crises_tab():
                    await crises_ui.render_crises_view(is_sg_admin=can_access_crises)

                await render_crises_tab()
                # Handle stocké : permet aux dialogues de crise de rafraîchir cet
                # onglet sans recharger la page (on reste sur « Cellules de Crise »).
                app.storage.client["refresh_crises_tab"] = render_crises_tab.refresh

        # ONGLET 3 : ANNUAIRE RH & ASTREINTES
        if can_access_crises and tab_annuaire:
            with ui.tab_panel(tab_annuaire):
                annuaire_ui.render_annuaire_view()

        # ONGLET 3b : JOURNAL DES ALERTES (HISTORIQUE DES CHANGEMENTS)
        if can_access_hypervision and tab_journal:
            with ui.tab_panel(tab_journal):
                with ui.column().classes("w-full gap-4"):
                    ui.label("Journal des Changements de Niveaux S/T").classes(
                        "text-2xl font-bold"
                    )

                    all_sites = (
                        await asyncio.to_thread(DatabaseService.get_all_sites) or []
                    )
                    site_options = {site.code_site: site.nom for site in all_sites}
                    site_options["TOUS"] = "Tous les sites"

                    filter_site = ui.select(
                        options=site_options, value="TOUS", label="Filtrer par site"
                    ).classes("w-full max-w-md")

                    changes = await asyncio.to_thread(
                        DatabaseService.get_recent_level_changes, limit=100
                    )
                    changes_container = ui.column().classes("w-full gap-2")

                    async def render_journal(filter_site_value="TOUS"):
                        changes_container.clear()
                        filtered_changes = changes

                        if filter_site_value != "TOUS":
                            filtered_changes = [
                                c
                                for c in changes
                                if c.get("site_code") == filter_site_value
                            ]

                        if not filtered_changes:
                            with changes_container:
                                ui.label("Aucun changement enregistré.").classes(
                                    "text-slate-400 italic"
                                )
                        else:
                            with changes_container:
                                for change in filtered_changes:
                                    level_badge_color = (
                                        "red"
                                        if "S4" in change.get("domaine", "")
                                        or "T4" in change.get("domaine", "")
                                        else (
                                            "amber"
                                            if "S3" in change.get("domaine", "")
                                            or "T3" in change.get("domaine", "")
                                            else (
                                                "orange-8"
                                                if "S2" in change.get("domaine", "")
                                                or "T2" in change.get("domaine", "")
                                                else "positive"
                                            )
                                        )
                                    )

                                    with ui.card().classes(
                                        "w-full bg-slate-900 border border-slate-700 p-4"
                                    ):
                                        with ui.row().classes(
                                            "w-full justify-between items-start"
                                        ):
                                            with ui.column().classes("gap-1"):
                                                ui.label(
                                                    f"[{change.get('site_code', 'N/C')}] {change.get('site_nom', 'N/C')}"
                                                ).classes("font-bold text-lg")
                                                domaine_info = change.get(
                                                    "domaine", "N/C"
                                                )
                                                equipement_info = change.get(
                                                    "equipement", "N/C"
                                                )
                                                ui.label(
                                                    f"Domaine: {domaine_info} | Équipement: {equipement_info}"
                                                ).classes("text-sm text-slate-400")
                                                ui.label(
                                                    change.get(
                                                        "description",
                                                        "Aucune description",
                                                    )
                                                ).classes("text-sm text-slate-300 mt-1")

                                            with ui.column().classes("items-end gap-2"):
                                                ui.badge(
                                                    change.get("statut", "ACTIF"),
                                                    color=level_badge_color,
                                                ).classes("font-bold")
                                                ui.label(
                                                    str(change.get("timestamp", "N/C"))[
                                                        :19
                                                    ]
                                                ).classes("text-xs text-slate-500")

                    filter_site.on(
                        "update:model-value",
                        lambda e: asyncio.create_task(render_journal(e.value)),
                    )
                    await render_journal()

        # ONGLET 4 : GESTION DES ACCÈS & YUBIKEYS (ADMIN UNIQUEMENT)
        if is_admin and tab_users:
            with ui.tab_panel(tab_users):
                users_ui.render_users_management_view()
