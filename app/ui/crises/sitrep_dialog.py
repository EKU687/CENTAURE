import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Optional

from nicegui import app, ui
from app.services.database_service import DatabaseService
from app.services.notification_service import NotificationService
from app.services.supabase_client import supabase, run_supabase

LOCAL_TZ = ZoneInfo("Pacific/Noumea")


def _parse_dt(raw: Any) -> Optional[datetime]:
    """Convertit un horodatage ISO en datetime conscient du fuseau."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


class SitrepService:

    @staticmethod
    def generate_auto_summary(crise_id: str) -> dict:
        """Agrège automatiquement les données du cockpit pour pré-remplir le SITREP."""
        sites = DatabaseService.get_all_sites() or []
        sites_s4 = [
            s.code_site for s in sites if getattr(s, "surete_niveau", "") == "S4"
        ]
        sites_s3 = [
            s.code_site for s in sites if getattr(s, "surete_niveau", "") == "S3"
        ]
        sites_critiques = [
            s.code_site
            for s in sites
            if getattr(s, "technique_niveau", "") in ["T3", "T4"]
        ]

        logs = DatabaseService.get_main_courante_by_crise(crise_id) or []
        sitrep_logs = [l for l in logs if l.get("is_sitrep") is True]
        if not sitrep_logs:
            sitrep_logs = logs[:5]

        faits_marquants = [
            f"[{log.get('categorie', 'INFO')}] {log.get('description', '')}"
            for log in sitrep_logs
        ]

        return {
            "sites_s4": sites_s4,
            "sites_s3": sites_s3,
            "sites_critiques_tech": sites_critiques,
            "faits_marquants": (
                "\n".join(faits_marquants)
                if faits_marquants
                else "Aucun fait marquant consigné."
            ),
        }

    @staticmethod
    def create_sitrep(payload: dict) -> bool:
        """Enregistre un nouveau SITREP dans Supabase avec horodatage en heure locale."""
        try:
            clean_crise_id = str(payload.get("crise_id", "")).strip()
            if not clean_crise_id:
                print("❌ [SITREP SERVICE ERROR] crise_id manquant.")
                return False

            next_num = 1
            try:
                existing = run_supabase(
                    lambda: supabase.table("centaure_sitreps")
                    .select("numero_sitrep")
                    .eq("crise_id", clean_crise_id)
                    .order("numero_sitrep", desc=True)
                    .limit(1)
                    .execute(),
                    "lecture dernier numero_sitrep",
                )
                if existing and existing.data and len(existing.data) > 0:
                    last_num = existing.data[0].get("numero_sitrep")
                    if last_num is not None:
                        next_num = int(last_num) + 1
            except Exception as e_num:
                print(f"⚠️️ [SITREP SERVICE] Fallback numero_sitrep=1 : {e_num}")

            db_payload = {
                "crise_id": clean_crise_id,
                "numero_sitrep": int(next_num),
                "redacteur": str(payload.get("redacteur") or "Opérateur SG").strip(),
                "synthese_situation": str(
                    payload.get("synthese_situation") or ""
                ).strip(),
                "points_attention": str(payload.get("points_attention") or "").strip(),
                "actions_engagees": str(payload.get("actions_engagees") or "").strip(),
                "prochaine_echeance": str(
                    payload.get("prochaine_echeance") or ""
                ).strip(),
                "horodatage": datetime.now(LOCAL_TZ).isoformat(),
                "type_sitrep": str(payload.get("type_sitrep") or "STANDARD").strip(),
            }

            try:
                res = run_supabase(
                    lambda: supabase.table("centaure_sitreps").insert(db_payload).execute(),
                    "insertion SITREP",
                )
            except Exception as err_col:
                # Colonne type_sitrep absente tant que la migration PCO n'est pas
                # appliquée : on réinsère sans le typage.
                print(f"⚠️ [SITREP SERVICE] Retry sans type_sitrep : {err_col}")
                db_payload.pop("type_sitrep", None)
                res = run_supabase(
                    lambda: supabase.table("centaure_sitreps").insert(db_payload).execute(),
                    "insertion SITREP (sans typage)",
                )
            return bool(res and res.data)

        except Exception as err:
            print(f"❌ [SITREP SERVICE ERROR] {err}")
            return False

    @staticmethod
    def update_sitrep(sitrep_id: str, payload: dict) -> bool:
        """Met à jour un SITREP existant dans Supabase."""
        try:
            db_payload = {
                "synthese_situation": str(
                    payload.get("synthese_situation") or ""
                ).strip(),
                "points_attention": str(payload.get("points_attention") or "").strip(),
                "actions_engagees": str(payload.get("actions_engagees") or "").strip(),
                "prochaine_echeance": str(
                    payload.get("prochaine_echeance") or ""
                ).strip(),
            }
            res = run_supabase(
                lambda: supabase.table("centaure_sitreps")
                .update(db_payload)
                .eq("id", str(sitrep_id))
                .execute(),
                "mise à jour SITREP",
            )
            return bool(res and res.data)
        except Exception as err:
            print(f"❌ [SITREP UPDATE ERROR] {err}")
            return False

    @staticmethod
    def get_sitreps_by_crise(crise_id: str) -> list[dict]:
        """Récupère l'historique des SITREPs d'une crise."""
        try:
            res = run_supabase(
                lambda: supabase.table("centaure_sitreps")
                .select("*")
                .eq("crise_id", str(crise_id))
                .order("numero_sitrep", desc=True)
                .execute(),
                "lecture historique SITREPs",
            )
            return res.data or []
        except Exception as err:
            print(f"❌ [SITREP SERVICE ERROR] {err}")
            return []

    @staticmethod
    def get_last_sitrep_by_crise(crise_id: str) -> Optional[dict]:
        """Récupère le dernier SITREP émis pour une crise (suivi PCO)."""
        try:
            res = run_supabase(
                lambda: supabase.table("centaure_sitreps")
                .select("*")
                .eq("crise_id", str(crise_id))
                .order("numero_sitrep", desc=True)
                .limit(1)
                .execute(),
                "lecture dernier SITREP",
            )
            return res.data[0] if res and res.data else None
        except Exception as err:
            print(f"❌ [SITREP SERVICE ERROR] {err}")
            return None

    @staticmethod
    def generate_fin_de_journee_summary(crise_id: str) -> dict:
        """Agrège les événements consignés depuis minuit (heure locale NC) pour
        construire le pré-remplissage du SITREP de fin de journée."""
        debut_jour = datetime.now(LOCAL_TZ).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        sites = DatabaseService.get_all_sites() or []
        sites_s4 = [
            s.code_site for s in sites if getattr(s, "surete_niveau", "") == "S4"
        ]
        sites_s3 = [
            s.code_site for s in sites if getattr(s, "surete_niveau", "") == "S3"
        ]

        logs = DatabaseService.get_main_courante_by_crise(crise_id) or []
        logs_du_jour = []
        for log in logs:
            dt_log = _parse_dt(log.get("horodatage") or log.get("created_at"))
            if dt_log is not None and dt_log >= debut_jour:
                logs_du_jour.append(log)

        def _fmt(log) -> str:
            dt_log = _parse_dt(log.get("horodatage") or log.get("created_at"))
            heure = dt_log.strftime("%Hh%M") if dt_log else "?"
            return (
                f"[{heure}] [{log.get('categorie', 'INFO')}] "
                f"{log.get('description', '')}"
            )

        decisions = [l for l in logs_du_jour if l.get("categorie") == "DECISION"]
        alertes = [
            l for l in logs_du_jour
            if l.get("categorie") == "ALERTE"
            or str(l.get("niveau_priorite", "")).upper() == "CRITIQUE"
        ]
        ordres = [l for l in logs_du_jour if l.get("categorie") == "ORDRE"]
        flagges_sitrep = [l for l in logs_du_jour if l.get("is_sitrep") is True]

        len_dec = len(decisions)
        len_al = len(alertes)
        synthese_lignes = [
            f"Consignation de la journée ({datetime.now(LOCAL_TZ).strftime('%d/%m/%Y')}) :",
            f"- {len(logs_du_jour)} événement(s) consigné(s) à la main courante, "
            f"dont {len_dec} décision(s) et {len_al} alerte(s)/élément(s) critique(s).",
        ]
        if ordres:
            synthese_lignes.append(f"- {len(ordres)} ordre(s)/directive(s) diffusé(s).")
        for l in flagges_sitrep or logs_du_jour:
            synthese_lignes.append(_fmt(l))

        return {
            "postures": {
                "sites_s4": sites_s4,
                "sites_s3": sites_s3,
            },
            "nb_evt_jour": len(logs_du_jour),
            "nb_decisions": len_dec,
            "nb_alertes": len_al,
            "nb_ordres": len(ordres),
            "synthese_preremplie": "\n".join(synthese_lignes),
            "actions_preremplie": (
                "\n".join(f"• {_fmt(d)}" for d in decisions)
                if decisions
                else "Aucune décision formelle consignée aujourd'hui."
            ),
        }


def open_sitrep_dialog(crise: Any):
    """Boîte de dialogue de création et consultation des bulletins SITREP pour le SG."""
    crise_id = (
        crise.get("id") if isinstance(crise, dict) else getattr(crise, "id", None)
    )
    code_crise = str(
        getattr(crise, "code_crise", None)
        or (crise.get("code_crise") if isinstance(crise, dict) else "CRISE")
    )
    titre_crise = str(
        getattr(crise, "titre", None)
        or (crise.get("titre") if isinstance(crise, dict) else "Sans titre")
    )

    with ui.dialog() as dialog, ui.card().classes(
        "w-full max-w-4xl bg-slate-900 border border-blue-600/80 text-slate-100 p-6 max-h-[90vh] overflow-y-auto"
    ):
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

        auto_data = SitrepService.generate_auto_summary(crise_id)

        with ui.expansion(
            "➕ Rédiger un nouveau SITREP complet", icon="edit_note", value=True
        ).classes("w-full bg-slate-800/80 border border-slate-700 rounded mb-4"):
            with ui.column().classes("p-4 gap-3 w-full"):

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
                    placeholder="Besoins de renforts, points juridiques, arbitrages exigés...",
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
                            "✅ SITREP enregistré dans l'historique !",
                            type="positive",
                        )
                        await refresh_sitreps_list()
                    else:
                        ui.notify(
                            "❌ Échec lors de l'enregistrement du SITREP.",
                            type="negative",
                        )

                ui.button(
                    "ENREGISTRER LE SITREP",
                    icon="save",
                    on_click=save_new_sitrep,
                ).props("color=blue font-bold class='self-end mt-2'")

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
                    sitrep_num = s.get("numero_sitrep", 1)
                    raw_h = str(s.get("horodatage") or "")
                    fmt_date = "N/A"
                    if raw_h:
                        try:
                            dt_obj = datetime.fromisoformat(
                                raw_h.replace("Z", "+00:00")
                            )
                            fmt_date = dt_obj.astimezone(LOCAL_TZ).strftime(
                                "%d/%m/%Y à %H:%M"
                            )
                        except Exception:
                            fmt_date = raw_h[:16].replace("T", " à ")

                    async def open_diffusion_sg_dialog(
                        sitrep_obj=s, fmt_date_str=fmt_date
                    ):
                        try:
                            membres_crise = (
                                await asyncio.to_thread(
                                    DatabaseService.get_membres_crise, crise_id
                                )
                                or []
                            )

                            membres_valides = []
                            for m in membres_crise:
                                agent = m.get("centaure_annuaire", {}) or {}
                                email = agent.get("email") or m.get("email")
                                if email:
                                    membres_valides.append(
                                        {
                                            "id": str(m.get("id")),
                                            "email": email,
                                            "nom": agent.get("nom", m.get("nom", "")),
                                            "prenom": agent.get(
                                                "prenom", m.get("prenom", "")
                                            ),
                                            "fonction": m.get(
                                                "fonction_crise", "Membre SG"
                                            ),
                                        }
                                    )

                            with ui.dialog() as send_modal, ui.card().classes(
                                "w-full max-w-lg bg-slate-900 text-slate-100 p-5 border border-blue-600 gap-3"
                            ):
                                ui.label(
                                    f"📧 Diffuser le SITREP #{sitrep_num} par E-mail"
                                ).classes("text-lg font-bold text-blue-400")
                                ui.label(
                                    "Sélectionnez les membres du SG à notifier :"
                                ).classes("text-xs text-slate-300")

                                if not membres_valides:
                                    ui.label(
                                        "⚠️ Aucun membre n'a d'adresse e-mail renseignée pour cette crise."
                                    ).classes("text-amber-400 italic text-xs p-2")
                                    ui.button(
                                        "Fermer", on_click=send_modal.close
                                    ).props("flat color=grey self-end")
                                    send_modal.open()
                                    return

                                checkboxes = {}
                                with ui.column().classes(
                                    "w-full max-h-60 overflow-y-auto bg-slate-950 p-2 rounded border border-slate-800 gap-1"
                                ):
                                    for m in membres_valides:
                                        label_m = f"{m['nom']} {m['prenom']} ({m['fonction']}) — {m['email']}"
                                        checkboxes[m["id"]] = ui.checkbox(
                                            label_m, value=True
                                        ).classes("text-xs text-slate-200")

                                def toggle_all(val: bool):
                                    for cb in checkboxes.values():
                                        cb.set_value(val)

                                with ui.row().classes(
                                    "w-full justify-between items-center text-xs"
                                ):
                                    with ui.row().classes("gap-1"):
                                        ui.button(
                                            "Tout cocher",
                                            on_click=lambda: toggle_all(True),
                                        ).props("flat dense color=blue sm")
                                        ui.button(
                                            "Tout décocher",
                                            on_click=lambda: toggle_all(False),
                                        ).props("flat dense color=grey sm")

                                async def confirm_send_email():
                                    selected_dests = [
                                        m
                                        for m in membres_valides
                                        if checkboxes[m["id"]].value
                                    ]

                                    if not selected_dests:
                                        ui.notify(
                                            "Veuillez sélectionner au moins un destinataire.",
                                            type="warning",
                                        )
                                        return

                                    ui.notify(
                                        "🚀 Envoi des e-mails en cours...", type="info"
                                    )

                                    crise_info = {
                                        "code_crise": code_crise,
                                        "titre": titre_crise,
                                    }
                                    sitrep_payload = dict(sitrep_obj)
                                    sitrep_payload["horodatage_fmt"] = fmt_date_str

                                    try:
                                        report = (
                                            await NotificationService.send_sitrep_email(
                                                crise_data=crise_info,
                                                sitrep_data=sitrep_payload,
                                                destinataires=selected_dests,
                                            )
                                        )
                                        send_modal.close()

                                        succes = report.get("success", 0)
                                        echecs = report.get("failed", 0)

                                        if echecs == 0 and succes > 0:
                                            ui.notify(
                                                f"🎉 SITREP #{sitrep_num} envoyé par mail avec succès !",
                                                type="positive",
                                            )
                                        else:
                                            ui.notify(
                                                f"⚠️ Envoi : {succes} réussi(s), {echecs} échec(s). Regardez la console.",
                                                type="warning",
                                                duration=8.0,
                                            )

                                    except Exception as exc:
                                        send_modal.close()
                                        print(f"❌ [EXCEPTION CLIENT EMAIL] : {exc}")
                                        ui.notify(
                                            f"❌ Erreur lors de l'envoi : {exc}",
                                            type="negative",
                                            duration=10.0,
                                        )

                                with ui.row().classes("w-full justify-end gap-2 mt-2"):
                                    ui.button(
                                        "Annuler", on_click=send_modal.close
                                    ).props("flat color=grey")
                                    ui.button(
                                        "ENVOYER LES E-MAILS",
                                        icon="send",
                                        on_click=confirm_send_email,
                                    ).props("color=blue font-bold")

                            send_modal.open()
                        except Exception as e_dialog:
                            print(f"❌ Erreur ouverture modal email: {e_dialog}")
                            ui.notify(f"Erreur UI : {e_dialog}", type="negative")

                    def open_edit_sitrep_modal(sitrep_data=s):
                        with ui.dialog() as edit_modal, ui.card().classes(
                            "w-full max-w-2xl bg-slate-900 text-slate-100 p-6 border border-amber-600 gap-3"
                        ):
                            ui.label(
                                f"✏️ Modifier le SITREP #{sitrep_data.get('numero_sitrep')}"
                            ).classes("text-xl font-bold text-amber-400")

                            edit_synthese = ui.textarea(
                                label="Synthèse Générale de la Situation *",
                                value=sitrep_data.get("synthese_situation", ""),
                            ).classes("w-full h-28 text-xs")

                            edit_attention = ui.textarea(
                                label="Points d'attention majeurs & Besoins d'arbitrage SG",
                                value=sitrep_data.get("points_attention", ""),
                            ).classes("w-full h-20 text-xs")

                            edit_actions = ui.textarea(
                                label="Actions engagées / Mesures prises",
                                value=sitrep_data.get("actions_engagees", ""),
                            ).classes("w-full h-20 text-xs")

                            edit_echeance = ui.input(
                                label="Prochaine échéance / Réunion",
                                value=sitrep_data.get("prochaine_echeance", ""),
                            ).classes("w-full text-xs")

                            async def save_edit():
                                if not edit_synthese.value.strip():
                                    ui.notify(
                                        "La synthèse est obligatoire.", type="warning"
                                    )
                                    return

                                payload = {
                                    "synthese_situation": edit_synthese.value,
                                    "points_attention": edit_attention.value,
                                    "actions_engagees": edit_actions.value,
                                    "prochaine_echeance": edit_echeance.value,
                                }

                                ok = await asyncio.to_thread(
                                    SitrepService.update_sitrep,
                                    sitrep_data.get("id"),
                                    payload,
                                )
                                if ok:
                                    ui.notify(
                                        "✅ SITREP mis à jour avec succès !",
                                        type="positive",
                                    )
                                    edit_modal.close()
                                    await refresh_sitreps_list()
                                else:
                                    ui.notify(
                                        "❌ Échec de la modification.", type="negative"
                                    )

                            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                                ui.button("Annuler", on_click=edit_modal.close).props(
                                    "flat color=grey"
                                )
                                ui.button(
                                    "ENREGISTRER LES MODIFICATIONS",
                                    icon="save",
                                    on_click=save_edit,
                                ).props("color=amber-8 font-bold")

                        edit_modal.open()

                    with ui.card().classes(
                        "w-full bg-slate-800/90 border border-slate-700 p-4 rounded text-xs flex flex-col gap-2"
                    ):
                        with ui.row().classes(
                            "justify-between items-center w-full border-b border-slate-700 pb-2"
                        ):
                            with ui.row().classes("items-center gap-2"):
                                ui.badge(
                                    f"SITREP #{sitrep_num}", color="blue-7"
                                ).classes("font-bold text-sm")
                                ui.label(
                                    f"Rédacteur : {s.get('redacteur', 'N/A')} | {fmt_date}"
                                ).classes("text-slate-300 font-mono")

                            with ui.row().classes("items-center gap-2"):
                                ui.button(
                                    icon="edit",
                                    on_click=lambda s_item=s: open_edit_sitrep_modal(
                                        s_item
                                    ),
                                ).props("flat color=amber-4 sm").tooltip(
                                    "Modifier ce SITREP"
                                )

                                ui.button(
                                    "DIFFUSER AU SG (EMAIL)",
                                    icon="send",
                                    on_click=lambda s_item=s, d_str=fmt_date: open_diffusion_sg_dialog(
                                        s_item, d_str
                                    ),
                                ).props("color=blue-6 sm font-bold")

                        ui.label("📌 Synthèse :").classes(
                            "font-bold text-blue-300 mt-1"
                        )
                        ui.label(s.get("synthese_situation", "")).classes(
                            "text-slate-200 whitespace-pre-line bg-slate-950/50 p-2 rounded border border-slate-800"
                        )

                        if s.get("points_attention"):
                            ui.label("⚠️ Points d'attention / Arbitrages SG :").classes(
                                "font-bold text-amber-400 mt-1"
                            )
                            ui.label(s.get("points_attention")).classes(
                                "text-slate-300 bg-amber-950/20 p-2 rounded border border-amber-900/40"
                            )

                        if s.get("actions_engagees"):
                            ui.label("🚀 Actions engagées :").classes(
                                "font-bold text-emerald-400 mt-1"
                            )
                            ui.label(s.get("actions_engagees")).classes(
                                "text-slate-300 bg-emerald-950/20 p-2 rounded border border-emerald-900/40"
                            )

                        if s.get("prochaine_echeance"):
                            ui.label("⏱️ Prochaine échéance / Réunion :").classes(
                                "font-bold text-purple-400 mt-1"
                            )
                            ui.label(s.get("prochaine_echeance")).classes(
                                "text-slate-300 font-mono"
                            )

        ui.timer(0.1, refresh_sitreps_list, once=True)

    dialog.open()
