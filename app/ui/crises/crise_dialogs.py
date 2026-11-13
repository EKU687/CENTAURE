import asyncio
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from nicegui import app, ui
from app.services.database_service import DatabaseService
from app.services.notification_service import NotificationService

LOCAL_TZ = ZoneInfo("Pacific/Noumea")


def generate_default_code_crise() -> str:
    """Génère un code de crise unique au format CRISE-YYYY-XXXX."""
    year = datetime.now(LOCAL_TZ).year
    suffix = uuid.uuid4().hex[:4].upper()
    return f"CRISE-{year}-{suffix}"


async def activer_et_notifier_crise(
    crise_id: str, code_crise: str, titre_crise: str, dialog
):
    """Active la crise, journalise l'événement et envoie les e-mails SMTP."""
    try:
        ui.notify(f"Activation de la crise {code_crise}...", type="info")

        ok_update = await asyncio.to_thread(
            DatabaseService.update_crise, crise_id=crise_id, statut="ACTIVEE"
        )

        if not ok_update:
            ui.notify("❌ Échec de la mise à jour du statut en BDD.", type="negative")
            return

        # Horodatage d'activation pour le chrono PCO (mise à jour silencieuse :
        # la colonne peut être absente tant que la migration PCO n'est pas appliquée).
        await asyncio.to_thread(
            DatabaseService.update_crise,
            crise_id=crise_id,
            activated_at=datetime.now(LOCAL_TZ).isoformat(),
        )

        await asyncio.to_thread(
            DatabaseService.consigner_main_courante,
            crise_id=crise_id,
            description=f"🚀 ACTIVATION DE LA CELLULE DE CRISE [{code_crise}] : {titre_crise}",
            categorie="INITIALISATION",
            auteur="PC CRISTAL",
            statut_info="CONFIRMEE",
        )

        ui.notify("✅ Crise ACTIVÉE et journalisée.", type="positive")

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
                    options=["1", "2", "3", "4"],
                    value="2",
                    label="Niveau de Gravité",
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
                    app.storage.user.get("nom_complet")
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
                                "Directeur de crise",
                                "Responsable sûreté",
                                "Responsable de cellule",
                                "Chef de cellule",
                                "Chef de service",
                                "Officier de liaison",
                                "Référent Cyber / SSI",
                                "Rédacteur Main Courante",
                                "Agent",
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
                                            icon="delete", on_click=delete_m
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
            ui.button("Supprimer", icon="delete", on_click=delete_crise_action).props(
                "flat color=red sm"
            )
            ui.button(
                "Clôturer / Archiver", icon="archive", on_click=archive_crise_action
            ).props("color=orange sm font-bold")

    dialog.open()
