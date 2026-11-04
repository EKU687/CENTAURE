import asyncio
from nicegui import app, ui
from app.services.sitrep_service import SitrepService


def open_sitrep_dialog(crise: dict):
    """Boîte de dialogue d'édition et de consultation des SITREPs pour le SG."""
    crise_id = crise.get("id")
    code_crise = crise.get("code_crise", "CRISE")
    titre_crise = crise.get("titre", "Sans titre")

    with ui.dialog() as dialog, ui.card().classes(
        "w-full max-w-4xl bg-slate-900 border border-blue-600/80 text-slate-100 p-6 max-h-[90vh] overflow-y-auto"
    ):
        # En-tête
        with ui.row().classes(
            "justify-between items-center w-full border-b border-slate-700 pb-3 mb-4"
        ):
            with ui.row().classes("items-center gap-3"):
                ui.icon("description", color="blue-4", size="md")
                with ui.column().classes("gap-0"):
                    ui.label(f"BULLETIN DE SITUATION (SITREP) — {code_crise}").classes(
                        "text-xl font-black text-blue-400"
                    )
                    ui.label(
                        f"Destination : Secrétariat Général (SG) | {titre_crise}"
                    ).classes("text-xs text-slate-400")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")

        # Chargement de l'agrégation automatique BDD
        auto_data = SitrepService.generate_auto_summary(crise_id)

        with ui.expansion(
            "➕ Rédiger un nouveau SITREP", icon="edit_note", value=True
        ).classes("w-full bg-slate-800/80 border border-slate-700 rounded mb-4"):
            with ui.column().classes("p-4 gap-3 w-full"):

                # Zone de rappel automatique des postures terrain
                with ui.row().classes(
                    "w-full bg-slate-950 p-3 rounded border border-slate-800 gap-4 text-xs"
                ):
                    ui.label(
                        f"🚨 Confinement (S4) : {', '.join(auto_data['sites_s4']) if auto_data['sites_s4'] else 'Aucun'}"
                    ).classes("text-red-400 font-bold")
                    ui.label(
                        f"⚠️ Alerte (S3) : {', '.join(auto_data['sites_s3']) if auto_data['sites_s3'] else 'Aucun'}"
                    ).classes("text-amber-400 font-bold")

                input_synthese = ui.textarea(
                    label="Synthèse Générale de la Situation *",
                    placeholder="Résumer l'état d'avancement, les risques immédiats...",
                    value=f"Faits marquants récents :\n{auto_data['faits_marquants']}",
                ).classes("w-full h-28")

                input_attention = ui.textarea(
                    label="Points d'attention majeurs & Besoins d'arbitrage SG",
                    placeholder="Besoins de renforts, points juridiques, communication...",
                ).classes("w-full h-20")

                input_actions = ui.textarea(
                    label="Actions engagées / Mesures prises",
                    placeholder="Mesures de sécurité déployées, cellules armées...",
                ).classes("w-full h-20")

                input_echeance = ui.input(
                    label="Prochaine échéance / Réunion de crise",
                    placeholder="Ex: Prochain point de situation à 16h00",
                ).classes("w-full")

                async def save_new_sitrep():
                    if not input_synthese.value.strip():
                        ui.notify("La synthèse est obligatoire.", type="warning")
                        return

                    redacteur = app.storage.user.get(
                        "nom_complet", "Opérateur PC Crise"
                    )
                    payload = {
                        "crise_id": crise_id,
                        "redacteur": redacteur,
                        "synthese_situation": input_synthese.value.strip(),
                        "points_attention": input_attention.value.strip(),
                        "actions_engagees": input_actions.value.strip(),
                        "prochaine_echeance": input_echeance.value.strip(),
                    }

                    ok = await asyncio.to_thread(SitrepService.create_sitrep, payload)
                    if ok:
                        ui.notify(
                            "✅ SITREP enregistré et disponible pour le SG !",
                            type="positive",
                        )
                        await refresh_sitreps_list()
                    else:
                        ui.notify(
                            "❌ Échec lors de l'enregistrement du SITREP.",
                            type="negative",
                        )

                ui.button(
                    "GÉNÉRER ET DIFFUSER LE SITREP",
                    icon="send",
                    on_click=save_new_sitrep,
                ).props("color=blue font-bold class='self-end mt-2'")

        # Historique des SITREPs émis
        ui.label("Historique des bulletins SITREP émis").classes(
            "text-sm font-bold text-slate-300 mt-2 mb-1"
        )
        sitreps_container = ui.column().classes("w-full gap-2")

        async def refresh_sitreps_list():
            sitreps_container.clear()
            sitreps = await asyncio.to_thread(
                SitrepService.get_sitreps_by_crise, crise_id
            )

            with sitreps_container:
                if not sitreps:
                    ui.label(
                        "Aucun SITREP n'a encore été émis pour cette crise."
                    ).classes("text-slate-500 italic text-xs p-2")
                    return

                for s in sitreps:
                    with ui.card().classes(
                        "w-full bg-slate-800/90 border border-slate-700 p-3 rounded text-xs"
                    ):
                        with ui.row().classes(
                            "justify-between items-center w-full mb-1"
                        ):
                            ui.badge(
                                f"SITREP #{s['numero_sitrep']}", color="blue-7"
                            ).classes("font-bold")
                            ui.label(
                                f"Rédacteur : {s['redacteur']} | Horodatage : {s['horodatage'][:16].replace('T', ' à ')}"
                            ).classes("text-slate-400 font-mono")

                        ui.label("Synthèse :").classes("font-bold text-slate-200 mt-1")
                        ui.label(s["synthese_situation"]).classes(
                            "text-slate-300 whitespace-pre-line"
                        )

        ui.timer(0.1, refresh_sitreps_list, once=True)

    dialog.open()
