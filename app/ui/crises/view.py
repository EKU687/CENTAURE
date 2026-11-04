import asyncio
from nicegui import ui
from app.services.database_service import DatabaseService
from app.ui.crises.sitrep_dialog import open_sitrep_dialog
from app.ui.crises.main_courante_dialog import open_main_courante_dialog
from app.ui.crises.crise_dialogs import open_new_crise_dialog, open_edit_crise_dialog


async def render_crises_view(is_sg_admin: bool = False):
    """Vue principale du gestionnaire de crises."""
    with ui.row().classes("items-center justify-between w-full mb-6"):
        ui.label("Gestion des Cellules de Crise SG").classes("text-2xl font-bold")

        if is_sg_admin:
            ui.button(
                "DÉCLARER UNE CRISE",
                icon="add_alert",
                on_click=open_new_crise_dialog,
            ).props("color=red font-bold sm animate-pulse")

    crises = await asyncio.to_thread(DatabaseService.get_active_crises) or []

    if not crises:
        with ui.card().classes(
            "w-full bg-slate-800/40 border border-slate-700 p-8 text-center"
        ):
            ui.label("Aucune cellule de crise active en ce moment.").classes(
                "text-slate-400 italic text-base"
            )

    for crise in crises:
        c_code = getattr(crise, "code_crise", None) or (
            crise.get("code_crise") if isinstance(crise, dict) else "CRISE"
        )
        c_titre = getattr(crise, "titre", None) or (
            crise.get("titre") if isinstance(crise, dict) else "Sans titre"
        )
        c_type = getattr(crise, "type_crise", None) or (
            crise.get("type_crise") if isinstance(crise, dict) else "SURETE"
        )
        c_gravite = str(
            getattr(crise, "niveau_gravite", None)
            or (crise.get("niveau_gravite") if isinstance(crise, dict) else "2")
        ).replace("N", "")
        c_declencheur = getattr(crise, "declenchee_par", None) or (
            crise.get("declenchee_par") if isinstance(crise, dict) else "SG"
        )
        c_desc = getattr(crise, "description", None) or (
            crise.get("description") if isinstance(crise, dict) else ""
        )
        c_statut = getattr(crise, "statut", None) or (
            crise.get("statut") if isinstance(crise, dict) else "ACTIVEE"
        )

        card_bg = (
            "bg-amber-950/20 border-amber-800/60"
            if c_statut == "EN_SOMMEIL"
            else "bg-red-950/30 border-red-800/80"
        )

        with ui.card().classes(f"w-full {card_bg} border p-5 shadow-lg mb-4"):
            with ui.row().classes("justify-between items-start w-full"):
                with ui.column().classes("gap-1"):
                    with ui.row().classes("items-center gap-3"):
                        ui.badge(
                            c_code,
                            color=("amber-9" if c_statut == "EN_SOMMEIL" else "red"),
                        ).classes("font-mono font-bold")
                        ui.label(c_titre).classes("text-xl font-bold text-slate-100")
                        ui.badge(f"Gravité {c_gravite}", color="purple").classes(
                            "font-bold"
                        )

                        if c_statut == "EN_SOMMEIL":
                            ui.badge("EN SOMMEIL", color="warning").classes(
                                "font-bold animate-pulse"
                            )

                    ui.label(
                        f"Type : {c_type} | Déclenchée par : {c_declencheur}"
                    ).classes("text-xs text-slate-400 mt-1")

                with ui.row().classes("items-center gap-2"):
                    if is_sg_admin:
                        ui.button(
                            icon="edit",
                            on_click=lambda c=crise: open_edit_crise_dialog(c),
                        ).props("flat color=slate-400 sm").tooltip("Gérer la crise")

                    ui.button(
                        "SITREP SG",
                        icon="description",
                        on_click=lambda c=crise: open_sitrep_dialog(c),
                    ).props("color=blue sm font-bold")

                    ui.button(
                        "Main Courante de Crise",
                        icon="assignment",
                        on_click=lambda c=crise: open_main_courante_dialog(c),
                    ).props("color=red sm font-bold")

            ui.label(c_desc).classes(
                "text-sm text-slate-300 mt-3 bg-slate-900/40 p-3 rounded border border-slate-800"
            )
