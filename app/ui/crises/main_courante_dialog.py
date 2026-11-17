import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from nicegui import app, ui
from app.services.database_service import DatabaseService
from app.services.export_service import ExportService
from app.ui.crises.sitrep_dialog import SitrepService

LOCAL_TZ = ZoneInfo("Pacific/Noumea")


async def open_main_courante_dialog(crise):
    """Journal de bord de crise avec fenêtre de génération SITREP enrichie."""
    crise_id = None
    if isinstance(crise, str):
        crise_id = crise
    elif isinstance(crise, dict):
        crise_id = crise.get("id") or crise.get("crise_id")
    else:
        crise_id = getattr(crise, "id", None) or getattr(crise, "crise_id", None)

    code_crise = str(
        getattr(crise, "code_crise", None)
        or (crise.get("code_crise") if isinstance(crise, dict) else "CRISE")
    )
    titre_crise = str(
        getattr(crise, "titre", None)
        or (crise.get("titre") if isinstance(crise, dict) else "Sans titre")
    )

    if not crise_id or str(crise_id).strip() in ["", "None"]:
        ui.notify(
            "❌ Impossible d'identifier la crise (UUID manquant).", type="negative"
        )
        return

    directions_db = await asyncio.to_thread(DatabaseService.get_all_directions) or []
    options_directions = ["TOUTES / GÉNÉRAL"] + directions_db

    # Lecture initiale AVANT toute construction d'élément : le dialogue est
    # ensuite bâti de façon 100 % synchrone (contrairement au clear+recréation
    # asynchrone qui déclenchait côté client des re-rendus auto-destructeurs :
    # « Event listeners changed after initial definition », ancres orphelines).
    logs_initiaux = await asyncio.to_thread(
        DatabaseService.get_main_courante_by_crise, crise_id
    ) or []

    with ui.dialog() as dialog, ui.card().classes(
        "w-full max-w-7xl bg-slate-900 border border-red-800 text-slate-100 p-6"
    ).style(
        "display: flex; flex-direction: column; justify-content: flex-start; "
        "gap: 1rem; max-height: 92vh; overflow: hidden"
    ):
        # 1. En-tête
        with ui.row().classes(
            "justify-between items-center w-full border-b border-red-900/60 pb-3"
        ).style("flex: none"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("assignment", color="red-5", size="md")
                with ui.column().classes("gap-0"):
                    ui.label(f"MAIN COURANTE — {code_crise}").classes(
                        "text-xl font-black text-red-400"
                    )
                    ui.label(f"Objet : {titre_crise}").classes("text-xs text-slate-300")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")

        # 2. Formulaire de consignation
        with ui.column().classes(
            "w-full bg-slate-800/90 p-3 rounded border border-slate-700 gap-3"
        ).style("flex: none"):
            ui.label("Consigner une directive ou un événement au journal").classes(
                "text-xs font-bold text-slate-300 tracking-wider"
            )

            with ui.row().classes("w-full gap-3 items-center flex-wrap"):
                select_cat = ui.select(
                    options=["INFORMATION", "ORDRE", "DECISION", "ALERTE", "SITUATION"],
                    value="INFORMATION",
                    label="Catégorie",
                ).classes("w-36 bg-slate-900 text-white dense")

                select_prio = ui.select(
                    options=["NORMALE", "URGENT", "CRITIQUE"],
                    value="NORMALE",
                    label="Priorité",
                ).classes("w-32 bg-slate-900 text-white dense")

                select_direction = ui.select(
                    options=options_directions,
                    value="TOUTES / GÉNÉRAL",
                    label="Assigner à Direction",
                ).classes("w-48 bg-slate-900 text-white dense")

                select_statut_info = ui.select(
                    options={
                        "CONFIRMEE": "🟢 CONFIRMÉE",
                        "A_VERIFIER": "🟡 À VÉRIFIER",
                        "INVALIDEE": "🔴 INVALIDÉE",
                    },
                    value="CONFIRMEE",
                    label="Qualification",
                ).classes("w-40 bg-slate-900 text-white dense")

                checkbox_sitrep = ui.checkbox(
                    "📌 Inclure dans SITREP SG", value=False
                ).classes("text-xs font-bold text-amber-400 mt-2")

            with ui.row().classes("w-full gap-3 items-end"):
                input_desc = (
                    ui.textarea(
                        label="Description de l'événement / Consigne *",
                        placeholder="Saisir la description détaillée ici...",
                    )
                    .props("rows=3")
                    .classes("flex-grow bg-slate-900 text-white text-sm")
                )

                btn_send = (
                    ui.button("CONSIGNER", icon="send")
                    .props("color=red font-bold")
                    .classes("h-12 px-5")
                )

        # 3. Barre d'actions
        with ui.row().classes(
            "w-full items-center justify-between gap-2 bg-slate-950/60 p-2 rounded border border-slate-800"
        ).style("flex: none"):
            ui.label("Journal des événements").classes(
                "text-xs font-bold text-slate-400 uppercase tracking-wider"
            )

            async def generate_sitrep_from_flagged_logs():
                logs = await asyncio.to_thread(
                    DatabaseService.get_main_courante_by_crise, crise_id
                ) or []
                sitrep_logs = [l for l in logs if l.get("is_sitrep") is True]

                if not sitrep_logs:
                    ui.notify(
                        "⚠️ Aucun événement n'a été coché pour le SITREP SG.",
                        type="warning",
                    )
                    return

                lignes_sitrep = [
                    f"{idx}. [{str(l.get('horodatage') or '')[:16].replace('T', ' ')}] [{l.get('categorie', 'INFO')}] {l.get('description', '')}"
                    for idx, l in enumerate(reversed(sitrep_logs), 1)
                ]

                synthese_texte = "\n".join(lignes_sitrep)
                redacteur = app.storage.user.get("nom_complet", "Opérateur PC Crise")

                with ui.dialog() as sitrep_modal, ui.card().classes(
                    "w-full max-w-2xl bg-slate-900 text-slate-100 p-6 border border-blue-600 gap-3"
                ):
                    ui.label(
                        f"📋 SITREP SG — Synthèse Sélectionnée ({len(sitrep_logs)} événements)"
                    ).classes("text-xl font-bold text-blue-400")

                    textarea_sitrep = ui.textarea(
                        label="Synthèse de la situation *", value=synthese_texte
                    ).classes("w-full h-32 font-mono text-xs")

                    textarea_attention = ui.textarea(
                        label="Points d'attention majeurs & Besoins d'arbitrage SG",
                        placeholder="Posez vos questions ou arbitrages attendus du SG ici...",
                    ).classes("w-full h-20 text-xs")

                    textarea_actions = ui.textarea(
                        label="Actions engagées",
                        placeholder="Mesures de sécurité immédiates...",
                    ).classes("w-full h-16 text-xs")

                    input_echeance = ui.input(
                        label="Prochaine échéance / Réunion",
                        placeholder="Ex: Prochain point à 18h00",
                    ).classes("w-full text-xs")

                    async def confirm_sitrep_export():
                        payload = {
                            "crise_id": str(crise_id),
                            "redacteur": str(redacteur),
                            "synthese_situation": str(
                                textarea_sitrep.value or ""
                            ).strip(),
                            "points_attention": str(
                                textarea_attention.value or ""
                            ).strip(),
                            "actions_engagees": str(
                                textarea_actions.value or ""
                            ).strip(),
                            "prochaine_echeance": str(
                                input_echeance.value or ""
                            ).strip(),
                        }

                        ok = await asyncio.to_thread(
                            SitrepService.create_sitrep, payload
                        )
                        if ok:
                            ui.notify(
                                "🎉 SITREP enregistré et disponible dans l'historique SG !",
                                type="positive",
                            )
                            sitrep_modal.close()
                        else:
                            ui.notify(
                                "❌ Échec de l'enregistrement du SITREP.",
                                type="negative",
                            )

                    with ui.row().classes("w-full justify-end gap-2 mt-2"):
                        ui.button("Annuler", on_click=sitrep_modal.close).props(
                            "flat color=grey"
                        )
                        ui.button(
                            "VALIDER & ENREGISTRER LE SITREP",
                            icon="send",
                            on_click=confirm_sitrep_export,
                        ).props("color=blue font-bold")

                sitrep_modal.open()

            with ui.row().classes("gap-2"):
                ui.button(
                    "GÉNÉRER SITREP",
                    icon="auto_awesome",
                    on_click=generate_sitrep_from_flagged_logs,
                ).props("color=blue sm font-bold")

                async def trigger_export():
                    logs = await asyncio.to_thread(
                        DatabaseService.get_main_courante_by_crise, crise_id
                    ) or []
                    if not logs:
                        ui.notify("Aucun événement à exporter.", type="warning")
                        return
                    csv_bytes = ExportService.exporter_csv_main_courante(logs)
                    ui.download(csv_bytes, filename=f"MainCourante_{code_crise}.csv")
                    ui.notify("📜 Main Courante exportée !", type="positive")

                ui.button(
                    "Export CSV", icon="download", on_click=trigger_export
                ).classes(
                    "bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-bold"
                )

        # 4. Zone d'affichage direct des cartes
        journal_container = ui.column().classes(
            "w-full gap-2 pr-2 border border-slate-800 bg-slate-950/60 p-3 rounded"
        ).style(
            "flex: 1 1 0%; min-height: 220px; max-height: 55vh; overflow-y: auto"
        )

        @ui.refreshable
        def render_journal(evenements):
            """Rendu du journal via le mécanisme refreshable de NiceGUI :
            reconstruction propre (suppression réelle des anciens éléments,
            listeners et ancres gérés par le framework)."""
            with journal_container:
                if not evenements:
                    ui.label("⚠️ Aucun événement en BDD pour cette crise.").classes(
                        "text-amber-400 italic text-sm p-4 text-center w-full"
                    )
                    return

                for evt in evenements:
                    log_id = str(evt.get("id") or "")
                    cat_item = str(evt.get("categorie") or "INFO").upper()
                    prio_raw = str(evt.get("niveau_priorite") or "NORMALE").upper()
                    prio_color = (
                        "red"
                        if prio_raw == "CRITIQUE"
                        else ("amber" if prio_raw == "URGENT" else "blue")
                    )
                    raw_date = str(evt.get("horodatage") or evt.get("created_at") or "")
                    horodatage_fmt = "N/A"
                    horodatage_court = "N/A"
                    if raw_date:
                        try:
                            dt_log = datetime.fromisoformat(
                                raw_date.replace("Z", "+00:00")
                            )
                            horodatage_fmt = dt_log.astimezone(LOCAL_TZ).strftime(
                                "%d/%m/%Y à %H:%M"
                            )
                            horodatage_court = dt_log.astimezone(LOCAL_TZ).strftime(
                                "%d/%m %H:%M"
                            )
                        except Exception:
                            horodatage_fmt = raw_date[:19].replace("T", " à ")
                            horodatage_court = horodatage_fmt

                    statut_info = str(evt.get("statut_info") or "CONFIRMEE").upper()
                    assigned_dir = evt.get("direction_concernee")
                    desc_text = str(
                        evt.get("description") or evt.get("message") or "Sans texte"
                    )
                    is_sitrep_flag = bool(evt.get("is_sitrep", False))

                    card_border = (
                        "border-amber-500/80 bg-amber-950/20"
                        if is_sitrep_flag
                        else "border-slate-700"
                    )

                    def make_handler(target_id=log_id, current_val=is_sitrep_flag):
                        async def handle_toggle():
                            new_state = not current_val
                            ok = await asyncio.to_thread(
                                DatabaseService.toggle_sitrep_main_courante,
                                target_id,
                                new_state,
                            )
                            if ok:
                                ui.notify(
                                    f"{'📌 Ajouté au' if new_state else '⚪ Retiré du'} SITREP SG",
                                    type="positive" if new_state else "info",
                                )
                                # Le rafraîchissement partiel d'un dialogue
                                # déjà ouvert passe par le re-render client
                                # (peu fiable) : on rouvre le dialogue au
                                # complet avec un journal à jour.
                                dialog.close()
                                await open_main_courante_dialog(crise)

                        return handle_toggle

                    statut_color = (
                        "text-emerald-400"
                        if statut_info == "CONFIRMEE"
                        else (
                            "text-amber-400"
                            if statut_info == "A_VERIFIER"
                            else "text-red-400"
                        )
                    )
                    with ui.card().classes(
                        f"w-full bg-slate-800/80 border {card_border} p-2 text-sm flex-none"
                    ):
                        # Une seule ligne par événement (format chronologie) :
                        # heure | catégorie | priorité | direction | statut
                        # | description (tronquée à l'écran, complète au survol
                        #   et dans le DOM pour Ctrl+F) | bouton SITREP | auteur
                        with ui.row().classes("items-center gap-2 w-full flex-nowrap"):
                            heure_lbl = ui.label(horodatage_court).classes(
                                "text-slate-400 font-mono text-xs w-[74px] flex-none"
                            )
                            heure_lbl.tooltip(horodatage_fmt)
                            ui.badge(cat_item, color="grey-8").classes(
                                "font-mono font-bold text-[10px]"
                            )
                            ui.badge(prio_raw, color=prio_color).classes(
                                "font-bold text-[10px]"
                            )

                            if assigned_dir and str(assigned_dir) not in [
                                "TOUTES / GÉNÉRAL",
                                "TOUTES / GENERAL",
                                "None",
                                "",
                            ]:
                                ui.badge(
                                    f"🎯 {assigned_dir}", color="purple-9"
                                ).classes("font-bold text-[10px]")

                            ui.label(f"● {statut_info}").classes(
                                f"{statut_color} text-[10px] font-bold flex-none"
                            )
                            ui.label(desc_text).classes(
                                "text-sm text-slate-100 flex-grow truncate min-w-0"
                            ).tooltip(desc_text)
                            ui.button(
                                icon="push_pin" if is_sitrep_flag else "add",
                                on_click=make_handler(log_id, is_sitrep_flag),
                            ).props(
                                "round dense flat "
                                + (
                                    "color=amber text-color=white"
                                    if is_sitrep_flag
                                    else "color=slate-600 text-color=white"
                                )
                            ).tooltip(
                                "Retirer du SITREP SG"
                                if is_sitrep_flag
                                else "Inclure dans le SITREP SG"
                            )
                            ui.label(str(evt.get("auteur") or "Opérateur")).classes(
                                "text-[10px] font-bold text-slate-400 whitespace-nowrap flex-none"
                            )

        async def handle_submit():
            texte = input_desc.value
            if not texte or not str(texte).strip():
                ui.notify(
                    "Veuillez saisir une description avant de consigner.",
                    type="warning",
                )
                return

            selected_dir = select_direction.value
            dir_to_save = (
                None
                if selected_dir in ["TOUTES / GÉNÉRAL", "TOUTES / GENERAL"]
                else selected_dir
            )
            current_author = app.storage.user.get("nom_complet", "Opérateur SG")

            ok = await asyncio.to_thread(
                DatabaseService.consigner_main_courante,
                crise_id=crise_id,
                description=str(texte).strip(),
                categorie=select_cat.value,
                auteur=current_author,
                niveau_priorite=select_prio.value,
                direction_concernee=dir_to_save,
                statut_info=select_statut_info.value,
                is_sitrep=checkbox_sitrep.value,
            )

            if ok:
                ui.notify("Événement consigné !", type="positive")
                # Le rafraîchissement partiel d'un dialogue déjà ouvert passe
                # par le re-render client (peu fiable) : on rouvre le
                # dialogue au complet, journal à jour, nouvel evt en tête.
                dialog.close()
                await open_main_courante_dialog(crise)
            else:
                ui.notify("Échec de la consignation dans Supabase.", type="negative")

        btn_send.on_click(handle_submit)
        render_journal(logs_initiaux)

    # Anti-accumulation : chaque ouverture crée un dialogue neuf ; on le
    # retire du DOM quand il se referme, sinon les ouvertures successives
    # empilent dialogues, formulaires et handlers sur la page cliente.
    dialog.on("hide", dialog.delete)
    dialog.open()
