import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from nicegui import app, ui
from app.services.database_service import DatabaseService
from app.services.notification_service import NotificationService
from app.ui.crises.sitrep_dialog import SitrepService

LOCAL_TZ = ZoneInfo("Pacific/Noumea")


async def collect_emails_destinataires(crise_id: str) -> list[dict]:
    """Récupère les membres de la cellule disposant d'une adresse e-mail."""
    membres = (
        await asyncio.to_thread(DatabaseService.get_membres_crise, crise_id) or []
    )
    destinataires = []
    for m in membres:
        agent = m.get("centaure_annuaire", {}) or {}
        email = agent.get("email") or m.get("email")
        if email:
            destinataires.append(
                {
                    "id": str(m.get("id")),
                    "email": email,
                    "nom": agent.get("nom", m.get("nom", "")),
                    "prenom": agent.get("prenom", m.get("prenom", "")),
                    "fonction": m.get("fonction_crise", "Membre SG"),
                }
            )
    return destinataires


async def open_fin_de_journee_dialog(crise=None):
    """SITREP de clôture journalière.

    - `crise` fournie : bulletin pour cette cellule uniquement.
    - `crise=None` : bulletin consolidé pour toutes les cellules ACTIVÉES.
    """
    if crise is not None:
        crises = [crise]
    else:
        crises = await asyncio.to_thread(DatabaseService.get_active_crises) or []
        crises = [c for c in crises if str(c.get("statut")) == "ACTIVEE"]

    if not crises:
        ui.notify("Aucune cellule de crise active à consigner.", type="warning")
        return

    redacteur = app.storage.user.get("nom_complet", "Opérateur PC Crise")
    aujourdhui = datetime.now(LOCAL_TZ).strftime("%d/%m/%Y")

    # Préparation asynchrone des agrégats de journée pour chaque cellule.
    fiches = []
    for c in crises:
        summary = await asyncio.to_thread(
            SitrepService.generate_fin_de_journee_summary, c.get("id")
        )
        fiches.append({"crise": c, "summary": summary})

    with ui.dialog() as dialog, ui.card().classes(
        "w-full max-w-4xl max-h-[90vh] overflow-y-auto bg-slate-900 "
        "border border-indigo-600/80 text-slate-100 p-6"
    ):
        with ui.row().classes(
            "justify-between items-center w-full border-b border-slate-700 pb-3 mb-4"
        ):
            with ui.row().classes("items-center gap-3"):
                ui.icon("nightlight_round", color="indigo-4", size="md")
                with ui.column().classes("gap-0"):
                    ui.label("SITREP DE FIN DE JOURNÉE — CLÔTURE JOURNALIÈRE").classes(
                        "text-xl font-black text-indigo-400"
                    )
                    ui.label(
                        f"Consignation au {aujourdhui} | Rédacteur : {redacteur}"
                    ).classes("text-xs text-slate-400")
            ui.button(icon="close", on_click=dialog.close).props(
                "flat round dense"
            )

        ui.label(
            "Chaque bulletin enregistré porte le prochain numéro de SITREP de sa "
            "cellule et est typé « Clôture Journalière »."
        ).classes("text-xs text-slate-400 mb-2")

        sections = []
        for fiche in fiches:
            c = fiche["crise"]
            summary = fiche["summary"]
            code_crise = str(c.get("code_crise", "CRISE"))
            titrec = str(c.get("titre", "Sans titre"))
            postures = summary.get("postures", {})

            with ui.card().classes(
                "w-full bg-slate-800/60 border border-slate-700 p-4 rounded mb-3"
            ):
                with ui.row().classes("w-full justify-between items-center mb-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.badge(code_crise, color="indigo").classes(
                            "font-mono font-bold"
                        )
                        ui.label(titrec).classes("text-sm font-bold text-slate-200")
                    section_incluse = ui.checkbox(
                        "Inclure ce bulletin", value=True
                    ).classes("text-xs text-slate-300")

                with ui.row().classes(
                    "w-full bg-slate-950 p-2 rounded border border-slate-800 gap-4 "
                    "text-xs mb-2 flex-wrap"
                ):
                    ui.label(
                        f"📜 {summary.get('nb_evt_jour', 0)} evt | "
                        f"⚖️ {summary.get('nb_decisions', 0)} décision(s) | "
                        f"🚨 {summary.get('nb_alertes', 0)} alerte(s)"
                    ).classes("text-slate-300 font-mono")
                    ui.label(
                        f"🚨 Confinement (S4) : "
                        f"{', '.join(postures.get('sites_s4', [])) or 'Aucun'}"
                    ).classes("text-red-400 font-bold")
                    ui.label(
                        f"⚠️ Alerte (S3) : "
                        f"{', '.join(postures.get('sites_s3', [])) or 'Aucun'}"
                    ).classes("text-amber-400 font-bold")

                txt_synthese = ui.textarea(
                    label="Synthèse de la journée *",
                    value=summary.get("synthese_preremplie", ""),
                ).classes("w-full h-32 text-xs")

                txt_actions = ui.textarea(
                    label="Actions engagées / décisions marquantes",
                    value=summary.get("actions_preremplie", ""),
                ).classes("w-full h-16 text-xs")

                txt_attention = ui.textarea(
                    label="Points d'attention / Arbitrages SG",
                    placeholder="Situations en suspens à suivre demain...",
                ).classes("w-full h-14 text-xs")

                inp_echeance = ui.input(
                    label="Relèves / prochaine échéance",
                    value="Reprise de la veille demain — point de situation à 08h00",
                ).classes("w-full text-xs")

                sections.append(
                    {
                        "crise": c,
                        "incluse": section_incluse,
                        "synthese": txt_synthese,
                        "actions": txt_actions,
                        "attention": txt_attention,
                        "echeance": inp_echeance,
                    }
                )

        chk_email = ui.checkbox(
            "📧 Diffuser chaque bulletin par e-mail aux membres des cellules",
            value=False,
        ).classes("text-xs text-blue-400 font-bold mb-2")

        async def confirmer_cloture_journaliere():
            traitees = 0
            ok_email, ko_email = 0, 0

            for section in sections:
                if not section["incluse"].value:
                    continue
                synthese = str(section["synthese"].value or "").strip()
                if not synthese:
                    continue

                c = section["crise"]
                crise_id = c.get("id")
                code_crise = str(c.get("code_crise", "CRISE"))

                payload = {
                    "crise_id": crise_id,
                    "redacteur": redacteur,
                    "synthese_situation": synthese,
                    "points_attention": str(
                        section["attention"].value or ""
                    ).strip(),
                    "actions_engagees": str(section["actions"].value or "").strip(),
                    "prochaine_echeance": str(section["echeance"].value or "").strip(),
                    "type_sitrep": "CLOTURE_JOURNALIERE",
                }

                ok = await asyncio.to_thread(SitrepService.create_sitrep, payload)
                if not ok:
                    ui.notify(
                        f"❌ Échec enregistrement du bulletin {code_crise}.",
                        type="negative",
                    )
                    continue
                traitees += 1

                await asyncio.to_thread(
                    DatabaseService.consigner_main_courante,
                    crise_id=crise_id,
                    description=(
                        f"🌙 SITREP DE FIN DE JOURNÉE émis pour [{code_crise}] "
                        f"par {redacteur}."
                    ),
                    categorie="SITUATION",
                    auteur=redacteur,
                    statut_info="CONFIRMEE",
                    is_sitrep=True,
                )

                if chk_email.value:
                    last = await asyncio.to_thread(
                        SitrepService.get_last_sitrep_by_crise, crise_id
                    )
                    if last:
                        last = dict(last)
                        last["horodatage_fmt"] = str(
                            last.get("horodatage", "")
                        )[:16].replace("T", " à ")
                        last["redacteur"] = redacteur
                        last["synthese_situation"] = synthese
                        last["points_attention"] = str(
                            section["attention"].value or ""
                        ).strip()
                        last["actions_engagees"] = str(
                            section["actions"].value or ""
                        ).strip()
                        last["prochaine_echeance"] = str(
                            section["echeance"].value or ""
                        ).strip()
                        destinataires = await collect_emails_destinataires(crise_id)
                        if destinataires:
                            report = await NotificationService.send_sitrep_email(
                                crise_data=c, sitrep_data=last,
                                destinataires=destinataires,
                            )
                            ok_email += report.get("success", 0)
                            ko_email += report.get("failed", 0)
                        else:
                            ui.notify(
                                f"⚠️ {code_crise} : aucun membre avec e-mail.",
                                type="warning",
                            )

            if traitees == 0:
                ui.notify(
                    "Aucun bulletin valide (synthèse vide ou non incluse).",
                    type="warning",
                )
                return

            message = f"✅ {traitees} SITREP(s) de fin de journée enregistré(s)."
            if chk_email.value:
                message += (
                    f" | 📧 E-mails : {ok_email} envoyé(s), {ko_email} échec(s)."
                )
            ui.notify(message, type="positive", duration=8.0)
            dialog.close()

        with ui.row().classes("w-full justify-end gap-2 pt-2"):
            ui.button("Annuler", on_click=dialog.close).props("flat color=grey")
            ui.button(
                "VALIDER LES SITREPS DE FIN DE JOURNÉE",
                icon="nightlight_round",
                on_click=confirmer_cloture_journaliere,
            ).props("color=indigo font-bold")

    dialog.open()
