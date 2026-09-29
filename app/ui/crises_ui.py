import asyncio
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from nicegui import app, ui
from app.services.database_service import DatabaseService
from app.services.notification_service import NotificationService
from app.services.export_service import ExportService


def generate_default_code_crise() -> str:
    """Génère un code de crise unique au format CRISE-YYYY-XXXX."""
    year = datetime.now().year
    suffix = uuid.uuid4().hex[:4].upper()
    return f"CRISE-{year}-{suffix}"


# =========================================================================
# 🔄 CALLBACKS & ALERTES ASYNCHRONES
# =========================================================================


async def activer_et_notifier_crise(
    crise_id: str, code_crise: str, titre_crise: str, dialog
):
    """Active la crise, journalise l'événement et envoie les e-mails SMTP."""
    try:
        ui.notify(f"Activation de la crise {code_crise}...", type="info")

        # 1. Mise à jour statut BDD
        ok_update = await asyncio.to_thread(
            DatabaseService.update_crise, crise_id=crise_id, statut="ACTIVEE"
        )

        if not ok_update:
            ui.notify("❌ Échec de la mise à jour du statut en BDD.", type="negative")
            return

        # 2. Main Courante
        await asyncio.to_thread(
            DatabaseService.consigner_main_courante,
            crise_id=crise_id,
            description=f"🚀 ACTIVATION DE LA CELLULE DE CRISE [{code_crise}] : {titre_crise}",
            categorie="INITIALISATION",
            auteur="PC CRISTAL",
            statut_info="CONFIRMEE",
        )

        ui.notify("✅ Crise ACTIVÉE et journalisée.", type="positive")

        # 3. Récupération des données et membres
        crise_data = await asyncio.to_thread(DatabaseService.get_crise_by_id, crise_id)
        if not crise_data:
            crise_data = {
                "nom": titre_crise,
                "code_crise": code_crise,
                "niveau_gravite": "CRITIQUE",
            }

        membres = (
            await asyncio.to_thread(DatabaseService.get_membres_crise, crise_id) or []
        )

        membres_formatted = []
        for m in membres:
            agent = m.get("centaure_annuaire", {}) or {}
            email = agent.get("email") or m.get("email")
            if email:
                membres_formatted.append(
                    {
                        "email": email,
                        "nom": agent.get("nom", m.get("nom", "")),
                        "prenom": agent.get("prenom", m.get("prenom", "")),
                    }
                )

        # 4. Notification SMTP Statique
        if membres_formatted:
            report = await NotificationService.notify_crise_activation(
                crise_data=crise_data, membres=membres_formatted
            )

            ui.notify(
                f"📧 Convocations envoyées ! Succès : {report.get('success', 0)} | Échecs : {report.get('failed', 0)}",
                type="positive" if report.get("failed", 0) == 0 else "warning",
                duration=6.0,
            )
        else:
            ui.notify(
                "⚠️ Crise activée mais aucun membre rattaché avec email.",
                type="warning",
                duration=5.0,
            )

        dialog.close()
        ui.navigate.reload()

    except Exception as e:
        print(f"❌ Erreur activation : {e}")
        ui.notify(f"Erreur traitement : {e}", type="negative")


# =========================================================================
# 💬 DIALOG : MAIN COURANTE DE CRISE
# =========================================================================


async def open_main_courante_dialog(crise):
    """Journal de bord avec rendu réactif garanti par @ui.refreshable."""
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

    with ui.dialog() as dialog, ui.card().classes(
        "w-full max-w-5xl bg-slate-900 border border-red-800 text-slate-100 p-6 h-[85vh] flex flex-col justify-start gap-4 overflow-hidden"
    ):
        # 1. En-tête
        with ui.row().classes(
            "justify-between items-center w-full border-b border-red-900/60 pb-3 flex-none"
        ):
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
            "w-full bg-slate-800/90 p-3 rounded border border-slate-700 flex-none gap-3"
        ):
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

            with ui.row().classes("w-full gap-3 items-end"):
                input_desc = (
                    ui.textarea(
                        label="Description de l'événement / Consigne *",
                        placeholder="Saisir la description détaillée ici...",
                    )
                    .props("rows=2")
                    .classes("flex-grow bg-slate-900 text-white text-sm")
                )

                btn_send = (
                    ui.button("CONSIGNER", icon="send")
                    .props("color=red font-bold")
                    .classes("h-12 px-5")
                )

        # 3. Barre de filtres & Export CSV
        with ui.row().classes(
            "w-full items-center justify-between gap-2 bg-slate-950/60 p-2 rounded border border-slate-800 flex-none"
        ):
            search_input = ui.input(
                placeholder="🔍 Rechercher dans les logs..."
            ).classes("w-1/4 bg-slate-900 text-white dense")

            filter_cat = ui.select(
                options=[
                    "TOUS",
                    "INFORMATION",
                    "ORDRE",
                    "DECISION",
                    "ALERTE",
                    "SITUATION",
                ],
                value="TOUS",
                label="Catégorie",
            ).classes("w-32 bg-slate-900 text-white dense")

            filter_dir = ui.select(
                options=["TOUTES"] + directions_db,
                value="TOUTES",
                label="Direction",
            ).classes("w-36 bg-slate-900 text-white dense")

            filter_statut = ui.select(
                options=["TOUS", "CONFIRMEE", "A_VERIFIER", "INVALIDEE"],
                value="TOUS",
                label="Statut Info",
            ).classes("w-32 bg-slate-900 text-white dense")

            async def trigger_export():
                logs = (
                    await asyncio.to_thread(
                        DatabaseService.get_main_courante_by_crise, crise_id
                    )
                    or []
                )
                if not logs:
                    ui.notify("Aucun événement à exporter.", type="warning")
                    return
                csv_bytes = ExportService.exporter_csv_main_courante(logs)
                ui.download(csv_bytes, filename=f"MainCourante_{code_crise}.csv")
                ui.notify("📜 Main Courante exportée !", type="positive")

            ui.button("Export CSV", icon="download", on_click=trigger_export).classes(
                "bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-bold"
            )

        # 4. Rendu Réactif
        @ui.refreshable
        async def render_journal_content():
            logs = (
                await asyncio.to_thread(
                    DatabaseService.get_main_courante_by_crise, crise_id
                )
                or []
            )

            q = (search_input.value or "").lower().strip()
            c = str(filter_cat.value or "TOUS").upper()
            d = str(filter_dir.value or "TOUTES").upper()
            s = str(filter_statut.value or "TOUS").upper()

            filtered = []
            for item in logs:
                if c != "TOUS" and str(item.get("categorie")).upper() != c:
                    continue
                if (
                    s != "TOUS"
                    and str(item.get("statut_info", "CONFIRMEE")).upper() != s
                ):
                    continue
                if d != "TOUTES" and d != "TOUTES / GÉNÉRAL":
                    if d not in str(item.get("direction_concernee", "")).upper():
                        continue

                txt = str(item.get("description") or item.get("message") or "").lower()
                aut = str(item.get("auteur") or "").lower()
                if q and (q not in txt and q not in aut):
                    continue

                filtered.append(item)

            with ui.column().classes(
                "w-full flex-grow overflow-y-auto gap-2 pr-2 border border-slate-800 bg-slate-950/40 p-3 rounded h-[350px]"
            ):
                if not filtered:
                    ui.label("Aucun événement à afficher.").classes(
                        "text-slate-400 italic text-sm p-4 text-center w-full"
                    )
                    return

                for evt in filtered:
                    prio_raw = str(evt.get("niveau_priorite") or "NORMALE").upper()
                    prio_color = (
                        "red"
                        if prio_raw == "CRITIQUE"
                        else ("amber" if prio_raw == "URGENT" else "blue")
                    )
                    raw_date = str(evt.get("horodatage") or evt.get("created_at") or "")
                    horodatage_fmt = (
                        raw_date[:19].replace("T", " à ") if raw_date else "N/A"
                    )
                    statut_info = str(evt.get("statut_info") or "CONFIRMEE").upper()
                    assigned_dir = evt.get("direction_concernee")

                    card_border = "border-slate-700"
                    if statut_info == "A_VERIFIER":
                        card_border = "border-amber-500/80 bg-amber-950/20"
                    elif statut_info == "INVALIDEE":
                        card_border = "border-red-600/60 opacity-60 bg-red-950/20"

                    with ui.card().classes(
                        f"w-full bg-slate-800/80 border {card_border} p-3 text-xs flex-none"
                    ):
                        with ui.row().classes(
                            "justify-between items-center w-full mb-1"
                        ):
                            with ui.row().classes("items-center gap-2 flex-wrap"):
                                ui.badge(
                                    evt.get("categorie", "INFO"), color="grey-8"
                                ).classes("font-mono font-bold")
                                ui.badge(prio_raw, color=prio_color).classes(
                                    "font-bold"
                                )

                                if assigned_dir and assigned_dir not in [
                                    "TOUTES / GÉNÉRAL",
                                    "TOUTES / GENERAL",
                                    "None",
                                    "",
                                ]:
                                    ui.badge(
                                        f"🎯 {assigned_dir}", color="purple-9"
                                    ).classes("font-bold text-[10px]")

                                ui.label(f"🟢 {statut_info}").classes(
                                    "text-slate-300 font-bold"
                                )
                                ui.label(horodatage_fmt).classes(
                                    "text-slate-400 font-mono"
                                )

                            ui.label(
                                f"Auteur : {evt.get('auteur', 'Opérateur')}"
                            ).classes("font-bold text-slate-300")

                        desc_text = str(
                            evt.get("description") or evt.get("message") or ""
                        )
                        ui.label(desc_text).classes(
                            "text-sm text-slate-100 font-sans mt-1 whitespace-pre-line"
                        )

        await render_journal_content()

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

            ok = await asyncio.to_thread(
                DatabaseService.consigner_main_courante,
                crise_id=crise_id,
                description=str(texte).strip(),
                categorie=select_cat.value,
                auteur="Opérateur SG",
                niveau_priorite=select_prio.value,
                direction_concernee=dir_to_save,
                statut_info=select_statut_info.value,
            )

            if ok:
                ui.notify("Événement consigné !", type="positive")
                input_desc.set_value("")
                render_journal_content.refresh()
            else:
                ui.notify("Échec de la consignation dans Supabase.", type="negative")

        btn_send.on_click(handle_submit)
        search_input.on("update:model-value", lambda: render_journal_content.refresh())
        filter_cat.on("update:model-value", lambda: render_journal_content.refresh())
        filter_dir.on("update:model-value", lambda: render_journal_content.refresh())
        filter_statut.on("update:model-value", lambda: render_journal_content.refresh())

    dialog.open()


# =========================================================================
# 💬 DIALOG : CREATION & EDIT CRISE
# =========================================================================


def open_new_crise_dialog():
    """Boîte de dialogue de déclaration d'une nouvelle Cellule de Crise SG."""
    default_code = generate_default_code_crise()

    with ui.dialog() as dialog, ui.card().classes(
        "w-full max-w-lg max-h-[90vh] overflow-y-auto bg-slate-900 border border-red-700 text-slate-100 p-6 flex flex-col justify-between"
    ):
        with ui.column().classes("w-full gap-2"):
            ui.label("Déclarer une Nouvelle Cellule de Crise SG").classes(
                "text-xl font-bold text-red-400 mb-2"
            )

            input_code = ui.input(label="Code Crise", value=default_code).classes(
                "w-full"
            )
            input_titre = ui.input(label="Intitulé de la crise").classes("w-full")

            with ui.row().classes("w-full gap-3"):
                select_type = ui.select(
                    options=[
                        "GEOPOLITIQUE",
                        "CYBER",
                        "SURETE",
                        "SANITAIRE",
                        "TECHNIQUE",
                    ],
                    value="SURETE",
                    label="Type de crise",
                ).classes("w-1/2")
                select_gravite = ui.select(
                    options=["1", "2", "3", "4"], value="2", label="Niveau de Gravité"
                ).classes("w-1/2")

            select_statut_initial = ui.select(
                options={
                    "EN_SOMMEIL": "EN SOMMEIL (Veille / Pre-armement)",
                    "ACTIVEE": "ACTIVÉE (Déclenchement direct)",
                },
                value="EN_SOMMEIL",
                label="Posture initiale",
            ).classes("w-full my-1")

            input_lieu = ui.input(
                label="Lieu / PC Crise (ex: Salle Commandement SG)",
                placeholder="Optionnel",
            ).classes("w-full")

            input_desc = ui.textarea(label="Description synthétique").classes("w-full")

        async def save_crise():
            if not input_code.value or not input_titre.value:
                ui.notify("Le Code et l'Intitulé sont obligatoires.", type="warning")
                return

            declencheur = "SG"
            try:
                declencheur = (
                    app.storage.user.get("nom")
                    or app.storage.user.get("username")
                    or "SG"
                )
            except Exception:
                pass

            payload = {
                "code_crise": input_code.value.strip().upper(),
                "titre": input_titre.value.strip(),
                "type_crise": select_type.value,
                "niveau_gravite": str(select_gravite.value),
                "description": (input_desc.value or "").strip(),
                "declenchee_par": declencheur,
                "statut": select_statut_initial.value,
            }

            if input_lieu.value and input_lieu.value.strip():
                payload["lieu_pc"] = input_lieu.value.strip()

            new_crise = await asyncio.to_thread(DatabaseService.create_crise, payload)

            if new_crise:
                await asyncio.to_thread(
                    DatabaseService.consigner_main_courante,
                    crise_id=new_crise.get("id"),
                    description=f"🆕 CRÉATION DE LA CRISE [{payload['code_crise']}] — Posture : {payload['statut']}",
                    categorie="INITIALISATION",
                    auteur=declencheur,
                    statut_info="CONFIRMEE",
                )

                ui.notify("Cellule de Crise enregistrée !", type="positive")
                dialog.close()
                ui.navigate.reload()
            else:
                ui.notify("Échec de la création en BDD.", type="negative")

        with ui.row().classes(
            "justify-end w-full gap-2 mt-4 pt-3 border-t border-slate-800 flex-none"
        ):
            ui.button("Annuler", on_click=dialog.close).props("flat color=grey")
            ui.button("Enregistrer la Crise", icon="save", on_click=save_crise).props(
                "color=red font-bold"
            )

    dialog.open()


async def open_edit_crise_dialog(crise):
    """Boîte de dialogue d'édition, gestion d'équipe et activation."""
    crise_id = str(
        getattr(crise, "id", None)
        or (crise.get("id") if isinstance(crise, dict) else "")
    )
    code_crise = str(
        getattr(crise, "code_crise", None)
        or (crise.get("code_crise") if isinstance(crise, dict) else "CRISE")
    )
    titre_actuel = str(
        getattr(crise, "titre", None)
        or (crise.get("titre") if isinstance(crise, dict) else "")
    )
    type_actuel = str(
        getattr(crise, "type_crise", None)
        or (crise.get("type_crise") if isinstance(crise, dict) else "SURETE")
    )
    gravite_raw = getattr(crise, "niveau_gravite", None) or (
        crise.get("niveau_gravite") if isinstance(crise, dict) else "2"
    )
    gravite_actuelle = str(gravite_raw).replace("N", "").strip() if gravite_raw else "2"
    lieu_actuel = str(
        getattr(crise, "lieu_pc", None)
        or (crise.get("lieu_pc") if isinstance(crise, dict) else "")
    )
    desc_actuelle = str(
        getattr(crise, "description", None)
        or (crise.get("description") if isinstance(crise, dict) else "")
    )
    statut_actuel = str(
        getattr(crise, "statut", None)
        or (crise.get("statut") if isinstance(crise, dict) else "EN_SOMMEIL")
    )

    with ui.dialog() as dialog, ui.card().classes(
        "w-[650px] max-w-full max-h-[90vh] overflow-y-auto bg-slate-900 border border-slate-700 text-slate-100 p-5"
    ):
        with ui.row().classes(
            "justify-between items-center w-full border-b border-slate-700 pb-2 mb-3"
        ):
            with ui.row().classes("items-center gap-2 overflow-hidden"):
                ui.icon("tune", color="red-4", size="sm")
                ui.label(f"Gestion : {code_crise}").classes(
                    "text-lg font-bold text-red-400 truncate"
                )
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")

        if statut_actuel == "EN_SOMMEIL":
            with ui.card().classes(
                "w-full bg-amber-950/40 border border-amber-600/80 p-3 rounded mb-3"
            ):
                with ui.row().classes("w-full items-center justify-between gap-2"):
                    with ui.column().classes("gap-0"):
                        ui.label("CELLULE EN SOMMEIL (VEILLE)").classes(
                            "font-black text-amber-400 text-xs tracking-wider"
                        )
                        ui.label("Pré-armée. Données prêtes.").classes(
                            "text-[11px] text-amber-200/80"
                        )

                    ui.button(
                        "ACTIVATION & ALERTER",
                        icon="notifications_active",
                        on_click=lambda: activer_et_notifier_crise(
                            crise_id, code_crise, titre_actuel, dialog
                        ),
                    ).props("color=red font-bold sm animate-pulse")
        else:
            with ui.row().classes(
                "w-full bg-red-950/40 border border-red-600/60 p-2 rounded items-center gap-2 mb-3"
            ):
                ui.icon("check_circle", color="positive", size="xs")
                ui.label("CELLULE ACTIVÉE — OPÉRATIONNELLE").classes(
                    "font-bold text-xs text-red-200"
                )

        with ui.expansion(
            "Paramètres de la crise", icon="settings", value=True
        ).classes("w-full bg-slate-800/80 border border-slate-700 rounded mb-3"):
            with ui.column().classes("p-3 gap-3 w-full"):
                edit_titre = ui.input(label="Intitulé", value=titre_actuel).classes(
                    "w-full"
                )

                with ui.row().classes("w-full gap-2 items-center justify-between"):
                    edit_type = ui.select(
                        options=[
                            "GEOPOLITIQUE",
                            "CYBER",
                            "SURETE",
                            "SANITAIRE",
                            "TECHNIQUE",
                        ],
                        value=(
                            type_actuel
                            if type_actuel
                            in [
                                "GEOPOLITIQUE",
                                "CYBER",
                                "SURETE",
                                "SANITAIRE",
                                "TECHNIQUE",
                            ]
                            else "SURETE"
                        ),
                        label="Type",
                    ).classes("w-[160px]")

                    edit_gravite = ui.select(
                        options=["1", "2", "3", "4"],
                        value=(
                            gravite_actuelle
                            if gravite_actuelle in ["1", "2", "3", "4"]
                            else "2"
                        ),
                        label="Gravité",
                    ).classes("w-[100px]")

                    edit_statut = ui.select(
                        options=["EN_SOMMEIL", "ACTIVEE"],
                        value=(
                            statut_actuel
                            if statut_actuel in ["EN_SOMMEIL", "ACTIVEE"]
                            else "EN_SOMMEIL"
                        ),
                        label="Posture",
                    ).classes("w-[160px]")

                edit_lieu = ui.input(
                    label="Lieu / PC Crise", value=lieu_actuel
                ).classes("w-full")
                edit_desc = ui.textarea(
                    label="Description", value=desc_actuelle
                ).classes("w-full")

                async def update_crise_info():
                    ok = await asyncio.to_thread(
                        DatabaseService.update_crise,
                        crise_id=crise_id,
                        titre=edit_titre.value,
                        type_crise=edit_type.value,
                        gravite=edit_gravite.value,
                        lieu_pc=edit_lieu.value,
                        description=edit_desc.value,
                        statut=edit_statut.value,
                    )

                    if ok:
                        ui.notify("Fiche mise à jour !", type="positive")
                        dialog.close()
                        ui.navigate.reload()

                ui.button("Enregistrer", icon="save", on_click=update_crise_info).props(
                    "color=blue sm font-bold"
                ).classes("self-end")

        # Affectation RH
        with ui.expansion("Équipe & Convocations RH", icon="groups").classes(
            "w-full bg-slate-800/80 border border-slate-700 rounded mb-3"
        ):
            with ui.column().classes("p-3 gap-2 w-full"):
                options_annuaire = {}
                try:
                    annuaire = await asyncio.to_thread(DatabaseService.get_annuaire)
                    if annuaire:
                        for p in annuaire:
                            pid = str(p.get("id", ""))
                            nom = str(p.get("nom", ""))
                            prenom = str(p.get("prenom", ""))
                            service = str(p.get("service", "N/A"))
                            if pid:
                                options_annuaire[pid] = f"{nom} {prenom} ({service})"
                except Exception as err:
                    print(f"⚠️ Erreur annuaire : {err}")

                with ui.column().classes(
                    "w-full gap-2 bg-slate-900/60 p-2 rounded border border-slate-700"
                ):
                    select_personne = ui.select(
                        options=options_annuaire, label="Agent"
                    ).classes("w-full")

                    with ui.row().classes("w-full justify-between items-center gap-2"):
                        select_role = ui.select(
                            options=[
                                "Directeur",
                                "Responsable de cellule",
                                "Chef de cellule",
                                "Chef de service",
                                "Agent",
                                "Rédacteur",
                                "Administratif",
                            ],
                            value="Agent",
                            label="Fonction",
                        ).classes("w-[220px]")

                        membres_container = ui.column().classes("w-full gap-1 mt-1")

                        async def refresh_membres():
                            membres_container.clear()
                            membres = (
                                await asyncio.to_thread(
                                    DatabaseService.get_membres_crise, crise_id
                                )
                                or []
                            )

                            with membres_container:
                                if not membres:
                                    ui.label("Aucun membre désigné.").classes(
                                        "text-slate-400 italic text-xs p-1"
                                    )
                                    return

                                for m in membres:
                                    p = m.get("centaure_annuaire", {}) or {}
                                    link_id = str(m.get("id", ""))
                                    fonction = str(m.get("fonction_crise", "Agent"))
                                    nom = str(p.get("nom", ""))
                                    prenom = str(p.get("prenom", ""))

                                    async def delete_m(mid=link_id):
                                        await asyncio.to_thread(
                                            DatabaseService.retirer_membre_crise, mid
                                        )
                                        await refresh_membres()

                                    with ui.row().classes(
                                        "w-full justify-between items-center bg-slate-900/90 p-2 rounded border border-slate-700 text-xs"
                                    ):
                                        with ui.row().classes("items-center gap-2"):
                                            ui.badge(fonction, color="blue-9").classes(
                                                "font-bold text-[10px]"
                                            )
                                            ui.label(f"{nom} {prenom}").classes(
                                                "font-bold text-slate-200"
                                            )

                                        ui.button(
                                            icon="delete",
                                            on_click=delete_m,
                                        ).props("flat color=red dense sm")

                        async def add_membre():
                            personne_id = select_personne.value
                            fonction_role = select_role.value

                            if not personne_id:
                                ui.notify(
                                    "Veuillez sélectionner un agent.", type="warning"
                                )
                                return

                            ok = await asyncio.to_thread(
                                DatabaseService.affecter_membre_crise,
                                crise_id,
                                personne_id,
                                fonction_role,
                            )
                            if not ok:
                                ui.notify("Erreur affectation en BDD.", type="negative")
                                return

                            annuaire_list = await asyncio.to_thread(
                                DatabaseService.get_annuaire
                            )
                            agent_target = next(
                                (
                                    a
                                    for a in annuaire_list
                                    if str(a.get("id")) == str(personne_id)
                                ),
                                None,
                            )
                            agent_nom = (
                                f"{agent_target.get('prenom', '')} {agent_target.get('nom', '')}".strip()
                                if agent_target
                                else "Agent"
                            )

                            await asyncio.to_thread(
                                DatabaseService.consigner_main_courante,
                                crise_id=crise_id,
                                description=f"👤 AFFECTATION : {agent_nom} affecté(e) au rôle de [{fonction_role}].",
                                categorie="AFFECTATION",
                                auteur="OPERATEUR",
                                statut_info="CONFIRMEE",
                            )

                            ui.notify("Membre affecté !", type="positive")
                            await refresh_membres()

                            if (
                                statut_actuel == "ACTIVEE"
                                and agent_target
                                and agent_target.get("email")
                            ):
                                await NotificationService.notify_membre_affectation(
                                    {
                                        "nom": edit_titre.value or titre_actuel,
                                        "code_crise": code_crise,
                                        "niveau_gravite": edit_gravite.value
                                        or gravite_actuelle,
                                        "lieu_pc": edit_lieu.value or lieu_actuel,
                                        "description": edit_desc.value or desc_actuelle,
                                    },
                                    {
                                        "email": agent_target.get("email"),
                                        "nom": agent_target.get("nom", ""),
                                        "prenom": agent_target.get("prenom", ""),
                                        "fonction": fonction_role,
                                    },
                                )

                        ui.button(
                            "Ajouter", icon="person_add", on_click=add_membre
                        ).props("color=green sm font-bold")

                await refresh_membres()

        async def delete_crise_action():
            await asyncio.to_thread(DatabaseService.delete_crise, crise_id)
            dialog.close()
            ui.navigate.reload()

        async def archive_crise_action():
            await asyncio.to_thread(DatabaseService.archiver_crise, crise_id)
            dialog.close()
            ui.navigate.reload()

        with ui.row().classes(
            "justify-between w-full border-t border-slate-700 pt-3 mt-2"
        ):
            ui.button(
                "Supprimer",
                icon="delete",
                on_click=delete_crise_action,
            ).props("flat color=red sm")
            ui.button(
                "Clôturer / Archiver",
                icon="archive",
                on_click=archive_crise_action,
            ).props("color=orange sm font-bold")

    dialog.open()


# =========================================================================
# 🖥️ VUE PRINCIPALE
# =========================================================================


async def render_crises_view(is_sg_admin: bool):
    """Rendu autonome de la section Cellules de Crise SG."""
    with ui.column().classes("w-full gap-4"):
        with ui.row().classes("items-center justify-between w-full mb-2"):
            ui.label("Cellules de Crise Strategiques (SG)").classes(
                "text-2xl font-bold tracking-tight text-red-400"
            )

            if is_sg_admin:
                ui.button(
                    "Déclarer une Crise",
                    icon="add_alert",
                    on_click=open_new_crise_dialog,
                ).props("color=red sm font-bold")

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
                                color=(
                                    "amber-9" if c_statut == "EN_SOMMEIL" else "red"
                                ),
                            ).classes("font-mono font-bold")
                            ui.label(c_titre).classes(
                                "text-xl font-bold text-slate-100"
                            )
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
                            "Main Courante de Crise",
                            icon="assignment",
                            on_click=lambda c=crise: open_main_courante_dialog(c),
                        ).props("color=red sm font-bold")

                ui.label(c_desc).classes(
                    "text-sm text-slate-300 mt-3 bg-slate-900/40 p-3 rounded border border-slate-800"
                )
