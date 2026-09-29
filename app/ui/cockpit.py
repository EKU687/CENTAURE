import asyncio
from nicegui import app, ui
from app.core.config import settings
from app.services.database_service import DatabaseService
from app.models.site import SiteCritique
import app.ui.crises_ui as crises_ui  # <--- Module autonome des crises
import app.ui.annuaire_ui as annuaire_ui  # <--- Import du composant RH


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
        ui.navigate.reload()
    else:
        ui.notify("❌ Échec lors du retour S1 !", type="warning")


def open_new_site_dialog():
    """Boîte de dialogue de création d'un nouveau site critique."""
    with ui.dialog() as dialog, ui.card().classes(
        "w-full max-w-lg bg-slate-900 border border-slate-700 text-slate-100 p-6"
    ):
        ui.label("Ajouter un Nouveau Site Sensible").classes(
            "text-xl font-bold text-blue-400 mb-4"
        )

        input_code = ui.input(label="Code du site (ex: CTP, CHT, PARC-01)").classes(
            "w-full"
        )
        input_nom = ui.input(label="Nom complet de l'infrastructure").classes("w-full")
        input_loc = ui.input(label="Localisation / Commune").classes("w-full")
        input_proto = ui.textarea(
            label="Protocole de Confinement (Consignes S4)"
        ).classes("w-full")

        async def save_new_site():
            if input_code.value and input_nom.value:
                ok = await asyncio.to_thread(
                    DatabaseService.create_site,
                    input_code.value,
                    input_nom.value,
                    input_loc.value or "",
                    input_proto.value or "",
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


def open_inspection_dialog(site: SiteCritique):
    """Boîte de dialogue d'inspection, d'édition et d'administration du site avec motifs."""
    with ui.dialog() as dialog, ui.card().classes(
        "w-full max-w-2xl bg-slate-900 border border-slate-700 text-slate-100 p-6"
    ):
        with ui.row().classes(
            "justify-between items-center w-full border-b border-slate-700 pb-3"
        ):
            with ui.row().classes("items-center gap-2"):
                ui.icon("search", color="blue-4", size="md")
                ui.label(f"Gestion Site : {site.nom} ({site.code_site})").classes(
                    "text-xl font-bold"
                )
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")

        # 1. Admin Niveaux S/T + Saisie du Motif
        with ui.column().classes(
            "w-full bg-slate-800/80 p-4 rounded border border-slate-700 my-4 gap-3"
        ):
            ui.label("Administration des Niveaux (Doctrine)").classes(
                "text-sm font-bold text-slate-300"
            )

            with ui.row().classes("w-full gap-4 items-center flex-wrap"):
                select_s = ui.select(
                    options=["S1", "S2", "S3", "S4"],
                    value=site.surete_niveau,
                    label="Niveau Sûreté",
                ).classes("w-40")
                select_t = ui.select(
                    options=["T1", "T2", "T3", "T4"],
                    value=site.technique_niveau,
                    label="Niveau Technique",
                ).classes("w-40")

            input_motif = ui.input(
                label="Motif / Commentaire (ex: Panne contrôle d'accès, Infiltration...)",
                placeholder="Renseigner la raison du changement de niveau...",
            ).classes("w-full mt-1")

            async def save_status():
                ok = await asyncio.to_thread(
                    DatabaseService.update_site_status,
                    site.id,
                    select_s.value,
                    select_t.value,
                    input_motif.value,
                )
                if ok:
                    if select_s.value == "S4":
                        ui.notify(
                            f"⚠️ ORDRE DE CONFINEMENT DÉCLENCHÉ SUR {site.code_site} !",
                            type="negative",
                        )
                    else:
                        ui.notify(
                            "Statuts S/T et motif consignés avec succès !",
                            type="positive",
                        )
                    dialog.close()
                    ui.navigate.reload()

            ui.button("Applique & Consigner", icon="save", on_click=save_status).props(
                "color=blue sm"
            ).classes("mt-2 self-end")

        # 2. Édition Fiche & Protocole
        with ui.expansion("Éditer la Fiche & Protocole S4", icon="edit").classes(
            "w-full bg-slate-800 border border-slate-700 rounded mb-4"
        ):
            with ui.column().classes("p-3 gap-3 w-full"):
                edit_nom = ui.input(label="Nom du site", value=site.nom).classes(
                    "w-full"
                )
                edit_loc = ui.input(
                    label="Localisation", value=site.localisation or ""
                ).classes("w-full")
                edit_proto = ui.textarea(
                    label="Protocole S4", value=site.protocole_confinement or ""
                ).classes("w-full")

                async def update_info():
                    ok = await asyncio.to_thread(
                        DatabaseService.update_site_info,
                        site.id,
                        edit_nom.value,
                        edit_loc.value,
                        edit_proto.value,
                    )
                    if ok:
                        ui.notify("Fiche site mise à jour !", type="positive")
                        dialog.close()
                        ui.navigate.reload()

                ui.button(
                    "Enregistrer les modifications", icon="check", on_click=update_info
                ).props("color=blue sm")

        # 3. Suivi & Anomalies Enregistrées
        ui.label("Historique & Maintenances Actives").classes(
            "text-lg font-bold text-amber-400 mt-2"
        )
        if site.anomalies:
            with ui.column().classes("w-full gap-2 mb-4"):
                for ano in site.anomalies:
                    with ui.row().classes(
                        "w-full justify-between items-center bg-slate-800 p-3 rounded border border-slate-700"
                    ):
                        with ui.column().classes("gap-0"):
                            ui.label(f"[{ano.domaine}] {ano.equipement}").classes(
                                "font-bold text-sm text-slate-200"
                            )
                            ui.label(ano.description or "Aucune description").classes(
                                "text-xs text-slate-400"
                            )

                        async def resolve_ano_action(anomalie_id=ano.id):
                            ok = await asyncio.to_thread(
                                DatabaseService.resolve_anomalie, anomalie_id
                            )
                            if ok:
                                ui.notify("Anomalie résolue !", type="positive")
                                dialog.close()
                                ui.navigate.reload()

                        ui.button(
                            "Résoudre",
                            icon="check",
                            on_click=resolve_ano_action,
                        ).props("color=green flat sm")
        else:
            ui.label("Aucune anomalie active.").classes(
                "text-sm text-slate-400 italic mb-4"
            )

        # 4. Supprimer le site
        with ui.row().classes(
            "w-full justify-between items-center border-t border-slate-700 pt-4 mt-4"
        ):

            def confirm_delete():
                with ui.dialog() as del_dialog, ui.card().classes(
                    "bg-slate-900 border border-red-800 text-white p-6"
                ):
                    ui.label(
                        f"Voulez-vous vraiment SUPPRIMER le site {site.code_site} ?"
                    ).classes("text-lg font-bold text-red-400 mb-4")
                    with ui.row().classes("justify-end gap-2 w-full"):
                        ui.button("Annuler", on_click=del_dialog.close).props(
                            "flat color=grey"
                        )

                        async def do_delete():
                            ok = await asyncio.to_thread(
                                DatabaseService.delete_site, site.id
                            )
                            if ok:
                                ui.notify("Site supprimé !", type="negative")
                                del_dialog.close()
                                dialog.close()
                                ui.navigate.reload()

                        ui.button(
                            "Supprimer définitivement", color="red", on_click=do_delete
                        )
                del_dialog.open()

            ui.button(
                "Supprimer ce site", icon="delete", on_click=confirm_delete
            ).props("flat color=red sm")

    dialog.open()


async def create_cockpit_page():
    """Interface du Cockpit Central réorganisée par Onglets avec RBAC."""
    user_role = app.storage.user.get("role", "ADMIN")
    is_sg_admin = user_role in ["ADMIN", "SUPERVISEUR_SG", "OPERATEUR_SG"]

    # Header Global
    with ui.header().classes(
        "bg-slate-900 text-white items-center justify-between px-6 py-2 border-b border-slate-700"
    ):
        with ui.row().classes("items-center gap-4"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("shield", size="md", color="red-5")
                ui.label(settings.APP_NAME).classes(
                    "text-xl font-bold tracking-widest text-red-500"
                )
                ui.label("| SG").classes("text-xs text-slate-400 font-medium")

            # Barre de navigation par Onglets
            with ui.tabs().classes("text-white") as tabs:
                tab_sites = ui.tab("Sites Sensibles", icon="grid_view")
                if is_sg_admin:
                    tab_crises = ui.tab("Cellules de Crise", icon="warning")
                    tab_annuaire = ui.tab("Annuaire RH", icon="people")

        # Actions Globales à droite
        with ui.row().classes("items-center gap-3"):
            ui.button(
                "RETOUR S1 GENERAL", icon="verified", on_click=handle_global_s1
            ).props("color=positive font-bold sm")

            ui.button(
                "ALERTE GÉNÉRALE S4", icon="gavel", on_click=handle_global_s4
            ).props("color=red font-bold animate-pulse sm")

            ui.badge("TEMPS RÉEL", color="positive")

    # Contenu Principal via Tab Panels
    with ui.tab_panels(tabs, value=tab_sites).classes(
        "w-full bg-slate-950 min-h-screen text-slate-100 p-6"
    ):
        # ----------------------------------------------------------------------
        # ONGLET 1 : HYPERVISION DES SITES SENSIBLES
        # ----------------------------------------------------------------------
        with ui.tab_panel(tab_sites):
            with ui.row().classes("items-center justify-between w-full mb-6"):
                with ui.row().classes("items-center gap-4"):
                    ui.label("Hypervision des Sites Sensibles").classes(
                        "text-2xl font-bold tracking-tight"
                    )
                    ui.button(
                        "Nouveau Site", icon="add", on_click=open_new_site_dialog
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
                        on_click=lambda: ui.navigate.reload(),
                    ).props("flat color=white sm")

            sites = await asyncio.to_thread(DatabaseService.get_all_sites) or []

            # Grille Responsive (1 col mobile, 2 tablette, 4 grand écran)
            sites_grid = ui.grid().classes(
                "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 w-full"
            )

            def render_sites_grid(filter_text=""):
                sites_grid.clear()
                with sites_grid:
                    for site in sites:
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
                        elif site.surete_niveau == "S2" or site.technique_niveau in [
                            "T2",
                            "T3",
                            "T4",
                        ]:
                            card_style = "bg-slate-900 border border-amber-600/60 text-slate-100 p-5 shadow-lg"
                        else:
                            card_style = "bg-slate-800 border border-slate-700 text-slate-100 p-5 shadow-lg"

                        with ui.card().classes(card_style):
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

                            with ui.row().classes("gap-3 w-full mb-4 justify-start"):
                                with ui.row().classes("items-center gap-1"):
                                    ui.label("Sûreté :").classes(
                                        "text-xs text-slate-400"
                                    )
                                    ui.badge(
                                        site.surete_niveau,
                                        color=get_status_color(site.surete_niveau),
                                    ).classes("font-bold")

                                with ui.row().classes("items-center gap-1"):
                                    ui.label("Technique :").classes(
                                        "text-xs text-slate-400"
                                    )
                                    ui.badge(
                                        site.technique_niveau,
                                        color=get_status_color(site.technique_niveau),
                                    ).classes("font-bold")

                            make_manage_handler = (
                                lambda s_target=site: lambda: open_inspection_dialog(
                                    s_target
                                )
                            )
                            make_site_screen_handler = lambda code_target=site.code_site: lambda: ui.navigate.to(
                                f"/site/{code_target}"
                            )

                            with ui.row().classes("w-full gap-2 mt-auto"):
                                ui.button(
                                    "Gérer", on_click=make_manage_handler()
                                ).props("sm outline color=grey-4").classes("w-1/2")
                                ui.button(
                                    "Écran Site",
                                    on_click=make_site_screen_handler(),
                                ).props("sm color=blue-7").classes("w-1/2")

            search_input.on("update:model-value", lambda e: render_sites_grid(e.value))
            render_sites_grid()

        # ----------------------------------------------------------------------
        # ONGLET 2 : CELLULES DE CRISE SG (ACCÈS RESTREINT RBAC)
        # ----------------------------------------------------------------------
        if is_sg_admin:
            with ui.tab_panel(tab_crises):
                # 🟢 Appel avec await pour exécuter la coroutine de crises_ui
                await crises_ui.render_crises_view(is_sg_admin=is_sg_admin)

        # ----------------------------------------------------------------------
        # ONGLET 3 : ANNUAIRE RH & ASTREINTES
        # ----------------------------------------------------------------------
        if is_sg_admin:
            with ui.tab_panel(tab_annuaire):
                annuaire_ui.render_annuaire_view()
