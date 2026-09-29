from typing import Callable, Optional
from nicegui import ui
from app.services.database_service import DatabaseService


def open_manage_directions_dialog(on_refresh_callback: Optional[Callable] = None):
    """Boîte de dialogue CRUD pour Ajouter, Modifier et Supprimer les Directions / Services."""

    with ui.dialog() as dialog, ui.card().classes(
        "w-full max-w-2xl bg-slate-900 border border-slate-700 text-slate-100 p-6"
    ):
        with ui.row().classes(
            "justify-between items-center w-full mb-4 border-b border-slate-800 pb-2"
        ):
            ui.label("🏢 Référentiel des Directions & Services").classes(
                "text-xl font-bold text-blue-400"
            )
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")

        # Zone d'ajout/édition rapide
        with ui.row().classes(
            "w-full gap-2 items-center bg-slate-800 p-3 rounded mb-4"
        ):
            input_code = ui.input(placeholder="Code (ex: DINUM)*").classes(
                "w-32 bg-slate-900 text-white dense"
            )
            input_nom = ui.input(
                placeholder="Intitulé complet (ex: Direction du Numérique)*"
            ).classes("flex-grow bg-slate-900 text-white dense")

            editing_state = {"id": None}

            def save_direction_action():
                code_val = input_code.value
                nom_val = input_nom.value

                if not code_val or not nom_val:
                    ui.notify(
                        "Le code et l'intitulé sont obligatoires.", type="warning"
                    )
                    return

                if editing_state["id"]:
                    # Mode Modification
                    if DatabaseService.update_direction(
                        editing_state["id"], code_val, nom_val
                    ):
                        ui.notify(
                            f"Direction {code_val} mise à jour !", type="positive"
                        )
                        reset_form()
                        refresh_list()
                    else:
                        ui.notify("Erreur lors de la mise à jour.", type="negative")
                else:
                    # Mode Création
                    success, err = DatabaseService.add_direction(code_val, nom_val)
                    if success:
                        ui.notify(
                            f"Direction {code_val} ajoutée avec succès !",
                            type="positive",
                        )
                        reset_form()
                        refresh_list()
                    else:
                        ui.notify(f"Erreur : {err}", type="negative")

            btn_save_dir = ui.button(
                "Ajouter", icon="add", on_click=save_direction_action
            ).props("color=blue sm font-bold")

            def reset_form():
                editing_state["id"] = None
                input_code.set_value("")
                input_nom.set_value("")
                btn_save_dir.set_text("Ajouter")
                btn_save_dir.props("icon=add color=blue")

        # Container de la liste des directions
        list_container = ui.column().classes(
            "w-full gap-2 max-h-[50vh] overflow-y-auto pr-1"
        )

        def refresh_list():
            list_container.clear()
            directions = DatabaseService.get_all_directions_full()

            with list_container:
                if not directions:
                    ui.label("Aucune direction enregistrée.").classes(
                        "text-slate-400 italic p-4 text-center w-full"
                    )
                    return

                for d in directions:
                    d_id = str(d.get("id", ""))
                    d_code = d.get("code", "")
                    d_nom = d.get("nom_complet", "")

                    with ui.row().classes(
                        "w-full justify-between items-center bg-slate-800/60 p-2 rounded border border-slate-700 text-xs"
                    ):
                        with ui.row().classes("items-center gap-3"):
                            ui.badge(d_code, color="blue-9").classes(
                                "font-mono font-bold text-xs"
                            )
                            ui.label(d_nom).classes("font-bold text-slate-200")

                        with ui.row().classes("gap-1"):
                            # Préparer la modification
                            def prepare_edit(
                                id_target=d_id, code_target=d_code, nom_target=d_nom
                            ):
                                editing_state["id"] = id_target
                                input_code.set_value(code_target)
                                input_nom.set_value(nom_target)
                                btn_save_dir.set_text("Enregistrer")
                                btn_save_dir.props("icon=save color=amber")

                            ui.button(icon="edit", on_click=prepare_edit).props(
                                "flat round dense color=blue sm"
                            ).tooltip("Éditer")

                            # Supprimer la direction
                            def delete_action(id_target=d_id, code_target=d_code):
                                if DatabaseService.delete_direction(id_target):
                                    ui.notify(
                                        f"Direction {code_target} supprimée.",
                                        type="warning",
                                    )
                                    refresh_list()
                                else:
                                    ui.notify(
                                        f"Échec de la suppression de {code_target}.",
                                        type="negative",
                                    )

                            ui.button(
                                icon="delete",
                                on_click=lambda c=d_code, i=d_id: delete_action(i, c),
                            ).props("flat round dense color=red sm").tooltip(
                                "Supprimer"
                            )

            if on_refresh_callback:
                on_refresh_callback()

        refresh_list()

    dialog.open()


def open_edit_agent_dialog(agent: dict, on_success_callback: Optional[Callable] = None):
    """Boîte de dialogue pour modifier un agent existant."""
    personne_id = str(agent.get("id", ""))

    # Récupération dynamique de la liste des directions depuis la BDD
    directions_db = DatabaseService.get_all_directions_full()
    options_directions = [d.get("code") for d in directions_db if d.get("code")]
    if not options_directions:
        options_directions = DatabaseService.get_all_directions()

    service_actuel = agent.get("service", "SG")
    if service_actuel and service_actuel not in options_directions:
        options_directions.append(service_actuel)

    with ui.dialog() as dialog, ui.card().classes(
        "w-full max-w-md bg-slate-900 border border-slate-700 text-slate-100 p-6"
    ):
        ui.label(f"Éditer l'Agent : {agent.get('nom')} {agent.get('prenom')}").classes(
            "text-xl font-bold text-blue-400 mb-4"
        )

        input_nom = ui.input(label="Nom *", value=agent.get("nom", "")).classes(
            "w-full"
        )
        input_prenom = ui.input(
            label="Prénom *", value=agent.get("prenom", "")
        ).classes("w-full")
        input_email = ui.input(
            label="Email Professionnel *", value=agent.get("email", "")
        ).classes("w-full")
        input_tel = ui.input(
            label="Téléphone / Flotte", value=agent.get("telephone", "")
        ).classes("w-full")

        # Sélection dynamique de la Direction
        select_service = ui.select(
            options=options_directions,
            value=service_actuel,
            label="Direction / Service d'appartenance *",
            with_input=True,
        ).classes("w-full my-2 bg-slate-900 text-white")

        async def save_changes():
            if not input_nom.value or not input_prenom.value or not input_email.value:
                ui.notify(
                    "Le Nom, le Prénom et l'Email sont obligatoires.", type="warning"
                )
                return

            direction_val = str(select_service.value or "SG").strip().upper()

            payload = {
                "nom": input_nom.value.strip().upper(),
                "prenom": input_prenom.value.strip().capitalize(),
                "email": input_email.value.strip().lower(),
                "telephone": (input_tel.value or "").strip(),
                "service": direction_val,
            }

            btn_save.props("loading")
            success, err = await DatabaseService.update_agent_annuaire(
                personne_id, payload
            )
            btn_save.props(remove="loading")

            if success:
                ui.notify("Agent mis à jour avec succès !", type="positive")
                dialog.close()
                if on_success_callback:
                    on_success_callback()
            else:
                ui.notify(f"Erreur lors de la mise à jour : {err}", type="negative")

        with ui.row().classes("justify-end w-full gap-2 mt-4"):
            ui.button("Annuler", on_click=dialog.close).props("flat color=grey")
            btn_save = ui.button(
                "Enregistrer", icon="save", on_click=save_changes
            ).props("color=blue font-bold")

    dialog.open()


def confirm_delete_agent(agent: dict, on_success_callback: Optional[Callable] = None):
    """Dialogue de confirmation de suppression d'un agent."""
    personne_id = str(agent.get("id", ""))
    nom_complet = f"{agent.get('nom', '')} {agent.get('prenom', '')}"

    with ui.dialog() as dialog, ui.card().classes(
        "bg-slate-900 border border-red-800 text-white p-6"
    ):
        ui.label(f"Supprimer l'agent {nom_complet} ?").classes(
            "text-lg font-bold text-red-400 mb-2"
        )
        ui.label(
            "Attention : Si cet agent est lié à une crise active, l'action sera rejetée par la BDD."
        ).classes("text-xs text-slate-400 mb-4")

        async def do_delete():
            btn_del.props("loading")
            success, err = await DatabaseService.delete_agent_annuaire(personne_id)
            btn_del.props(remove="loading")

            if success:
                ui.notify(f"Agent {nom_complet} supprimé.", type="negative")
                dialog.close()
                if on_success_callback:
                    on_success_callback()
            else:
                ui.notify(f"Impossible de supprimer : {err}", type="warning")

        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button("Annuler", on_click=dialog.close).props("flat color=grey")
            btn_del = ui.button(
                "Supprimer définitivement", color="red", on_click=do_delete
            )

    dialog.open()


def open_new_agent_dialog(on_success_callback: Optional[Callable] = None):
    """Boîte de dialogue pour inscrire un nouvel agent RH."""
    directions_db = DatabaseService.get_all_directions_full()
    options_directions = [d.get("code") for d in directions_db if d.get("code")]
    if not options_directions:
        options_directions = DatabaseService.get_all_directions()

    with ui.dialog() as dialog, ui.card().classes(
        "w-full max-w-md bg-slate-900 border border-slate-700 text-slate-100 p-6"
    ):
        ui.label("Inscrire un Nouvel Agent RH").classes(
            "text-xl font-bold text-blue-400 mb-4"
        )

        input_nom = ui.input(label="Nom *").classes("w-full")
        input_prenom = ui.input(label="Prénom *").classes("w-full")
        input_email = ui.input(label="Email Professionnel *").classes("w-full")
        input_tel = ui.input(label="Téléphone / Flotte").classes("w-full")

        select_service = ui.select(
            options=options_directions,
            value=(
                "SG"
                if "SG" in options_directions
                else (options_directions[0] if options_directions else "SG")
            ),
            label="Direction / Service d'appartenance *",
            with_input=True,
        ).classes("w-full my-2 bg-slate-900 text-white")

        async def save_agent():
            if not input_nom.value or not input_prenom.value or not input_email.value:
                ui.notify(
                    "Le Nom, le Prénom et l'Email sont obligatoires.", type="warning"
                )
                return

            direction_val = str(select_service.value or "SG").strip().upper()

            payload = {
                "nom": input_nom.value.strip().upper(),
                "prenom": input_prenom.value.strip().capitalize(),
                "email": input_email.value.strip().lower(),
                "telephone": (input_tel.value or "").strip(),
                "service": direction_val,
            }

            btn_create.props("loading")
            success, err = await DatabaseService.insert_agent_annuaire(payload)
            btn_create.props(remove="loading")

            if success:
                ui.notify(
                    f"Agent inscrit avec succès (Direction: {direction_val}) !",
                    type="positive",
                )
                dialog.close()
                if on_success_callback:
                    on_success_callback()
            else:
                ui.notify(f"Erreur lors de l'inscription : {err}", type="negative")

        with ui.row().classes("justify-end w-full gap-2 mt-4"):
            ui.button("Annuler", on_click=dialog.close).props("flat color=grey")
            btn_create = ui.button(
                "Enregistrer", icon="person_add", on_click=save_agent
            ).props("color=blue font-bold")

    dialog.open()


def render_annuaire_view():
    """Rendu de l'Annuaire RH avec gestion des directions et tableau réactif."""
    all_agents = DatabaseService.get_annuaire() or []

    with ui.column().classes("w-full gap-4"):
        # En-tête avec les actions principales
        with ui.row().classes("items-center justify-between w-full mb-2"):
            ui.label("Annuaire RH & Effectifs de Crise").classes(
                "text-2xl font-bold tracking-tight text-slate-100"
            )
            with ui.row().classes("gap-2 items-center"):
                # Bouton de gestion du Référentiel des Directions
                ui.button(
                    "Gérer les Directions",
                    icon="domain",
                    on_click=lambda: open_manage_directions_dialog(
                        on_refresh_callback=refresh_table
                    ),
                ).props("color=slate-700 sm font-bold text-white")

                # Bouton d'ajout d'agent
                ui.button(
                    "Ajouter un Agent",
                    icon="person_add",
                    on_click=lambda: open_new_agent_dialog(
                        on_success_callback=lambda: ui.navigate.reload()
                    ),
                ).props("color=blue sm font-bold")

        # Barre de recherche dynamique
        with ui.row().classes(
            "w-full items-center justify-between bg-slate-900 p-3 rounded border border-slate-800"
        ):
            search_input = ui.input(
                placeholder="🔍 Rechercher un agent (Nom, Email, Direction)..."
            ).classes("w-full max-w-md bg-slate-800 text-white dense")

        # Container principal de la liste
        table_container = ui.column().classes("w-full gap-0")

        def refresh_table():
            table_container.clear()
            query = (search_input.value or "").lower().strip()

            filtered_agents = [
                a
                for a in all_agents
                if query in a.get("nom", "").lower()
                or query in a.get("prenom", "").lower()
                or query in a.get("email", "").lower()
                or query in a.get("service", "").lower()
            ]

            with table_container:
                if not filtered_agents:
                    with ui.card().classes(
                        "w-full bg-slate-800/40 border border-slate-700 p-8 text-center"
                    ):
                        ui.label("Aucun agent ne correspond à la recherche.").classes(
                            "text-slate-400 italic text-base"
                        )
                    return

                # Tableau aligné via CSS Grid
                with ui.card().classes(
                    "w-full bg-slate-900 border border-slate-700 p-4 gap-0"
                ):
                    # Header
                    with ui.grid(columns="2fr 1fr 2fr 1fr 100px").classes(
                        "w-full text-xs font-bold text-slate-400 border-b border-slate-700 pb-2 mb-2 px-2 items-center"
                    ):
                        ui.label("NOM & PRÉNOM")
                        ui.label("DIRECTION / SERVICE")
                        ui.label("EMAIL")
                        ui.label("TÉLÉPHONE")
                        ui.label("ACTIONS").classes("text-center")

                    # Lignes
                    for agent in filtered_agents:
                        with ui.grid(columns="2fr 1fr 2fr 1fr 100px").classes(
                            "w-full text-sm text-slate-200 border-b border-slate-800/60 py-2 px-2 hover:bg-slate-800/50 items-center transition-colors"
                        ):
                            ui.label(
                                f"{agent.get('nom', '')} {agent.get('prenom', '')}"
                            ).classes("font-bold text-slate-100")
                            ui.badge(
                                agent.get("service", "SG"), color="blue-9"
                            ).classes("w-fit text-[10px] font-bold")
                            ui.label(agent.get("email", "")).classes(
                                "font-mono text-xs text-slate-300 truncate"
                            )
                            ui.label(agent.get("telephone") or "N/C").classes(
                                "text-xs text-slate-400"
                            )

                            # Actions
                            with ui.row().classes("justify-center gap-1"):
                                ui.button(
                                    icon="edit",
                                    on_click=lambda a=agent: open_edit_agent_dialog(
                                        a,
                                        on_success_callback=lambda: ui.navigate.reload(),
                                    ),
                                ).props("flat round dense color=blue sm").tooltip(
                                    "Modifier"
                                )

                                ui.button(
                                    icon="delete",
                                    on_click=lambda a=agent: confirm_delete_agent(
                                        a,
                                        on_success_callback=lambda: ui.navigate.reload(),
                                    ),
                                ).props("flat round dense color=red sm").tooltip(
                                    "Supprimer"
                                )

        search_input.on("update:model-value", refresh_table)
        refresh_table()
