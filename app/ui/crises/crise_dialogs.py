import asyncio
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from nicegui import app, ui
from app.services.database_service import DatabaseService
from app.services.notification_service import NotificationService

LOCAL_TZ = ZoneInfo("Pacific/Noumea")


async def _refresh_crises_tab_or_reload():
    """Rafraîchit l'onglet « Cellules de Crise » sans recharger la page (on y
    reste) ; repli sur ui.navigate.reload() si le handle de refresh est absent."""
    refresh = None
    try:
        refresh = app.storage.client.get("refresh_crises_tab")
    except Exception:
        refresh = None
    if callable(refresh):
        result = refresh()
        if asyncio.iscoroutine(result):
            await result
    else:
        ui.navigate.reload()


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
            categorie="ALERTE",
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


async def open_new_crise_dialog():
    """Boîte de dialogue de déclaration d'une nouvelle Cellule de Crise SG."""
    default_code = generate_default_code_crise()

    # Sélection du site impacté : crise « de niveau site » (site_impacte_id)
    # ou crise nationale (aucun site).
    sites_db = await asyncio.to_thread(DatabaseService.get_all_sites) or []
    options_sites = {"": "🌍 Crise nationale — aucun site rattaché"}
    for s in sites_db:
        sid = str(getattr(s, "id", "") or "")
        if sid:
            options_sites[sid] = f"{s.code_site} — {s.nom}"

    with ui.dialog() as dialog, ui.card().classes(
        "w-full max-w-lg max-h-[90vh] bg-slate-900 border border-red-700 text-slate-100 p-6 flex flex-col"
    ):
        # Zone scrollable interne : la barre de boutons reste visible en bas.
        with ui.column().classes("w-full gap-2 overflow-y-auto min-h-0 flex-1 pr-1"):
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

            select_site = ui.select(
                options=options_sites,
                value="",
                label="Site impacté (crise de niveau site) — vide = crise nationale",
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

            if select_site.value:
                payload["site_impacte_id"] = str(select_site.value)

            new_crise = await asyncio.to_thread(DatabaseService.create_crise, payload)

            if new_crise:
                await asyncio.to_thread(
                    DatabaseService.consigner_main_courante,
                    crise_id=new_crise.get("id"),
                    description=f"🆕 CRÉATION DE LA CRISE [{payload['code_crise']}] — Posture : {payload['statut']}",
                    categorie="INFORMATION",
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


async def open_fichiers_crise_dialog(crise):
    """Dialogue dédié aux pièces jointes d'une crise (upload / édition / suppression).

    Ouvert depuis la carte crise (bouton 📎 à côté de Main Courante / SITREP)
    et depuis le dialogue « Gérer la cellule ».
    """
    crise_id = str(
        getattr(crise, "id", None)
        or (crise.get("id") if isinstance(crise, dict) else "")
    )
    code_crise = str(
        getattr(crise, "code_crise", None)
        or (crise.get("code_crise") if isinstance(crise, dict) else "CRISE")
    )

    with ui.dialog() as dialog, ui.card().classes(
        "w-[650px] max-w-full max-h-[90vh] overflow-y-auto bg-slate-900 border border-slate-700 text-slate-100 p-5"
    ):
        with ui.row().classes(
            "justify-between items-center w-full border-b border-slate-700 pb-2 mb-3"
        ):
            with ui.row().classes("items-center gap-2 overflow-hidden"):
                ui.icon("attach_file", color="amber-4", size="sm")
                ui.label(f"Pièces jointes : {code_crise}").classes(
                    "text-lg font-bold text-amber-300 truncate"
                )
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")

        # Pièces jointes de la crise (upload / édition / suppression)
        with ui.expansion(f"📎 Pièces jointes ({code_crise})", icon="attach_file", value=True).classes(
            "w-full bg-slate-800/80 border border-slate-700 rounded mb-3"
        ):
            with ui.column().classes("p-3 gap-3 w-full"):
                fichiers_container = ui.column().classes("w-full gap-1")

                async def refresh_fichiers():
                    fichiers_container.clear()
                    fichiers = (
                        await asyncio.to_thread(
                            DatabaseService.get_fichiers_crise, crise_id
                        )
                        or []
                    )
                    with fichiers_container:
                        if not fichiers:
                            ui.label("Aucune pièce jointe pour cette cellule.").classes(
                                "text-slate-400 italic text-xs p-1"
                            )
                            return
                        for f in fichiers:
                            fid = str(f.get("id", ""))
                            nom = str(f.get("nom_fichier", "fichier"))
                            mime = str(f.get("mime") or "")
                            taille = f.get("taille_octets")
                            commentaire = str(f.get("commentaire") or "")
                            uploade = str(f.get("uploade_par") or "")
                            cree_le = str(f.get("created_at") or "")[:16].replace("T", " ")

                            def icone_mime(m=mime):
                                if m.startswith("image/"):
                                    return "image"
                                if m == "application/pdf":
                                    return "picture_as_pdf"
                                if "word" in m or "document" in m:
                                    return "description"
                                if "excel" in m or "spreadsheet" in m:
                                    return "table_chart"
                                if "mail" in m or "rfc822" in m:
                                    return "mail"
                                if "zip" in m or "rar" in m:
                                    return "archive"
                                return "insert_drive_file"

                            taille_txt = f"{int(taille) / 1024:.0f} Ko" if taille else ""

                            async def telecharger(spath=str(f.get("storage_path") or "")):
                                url = await asyncio.to_thread(
                                    DatabaseService.url_signee_fichier_crise, spath
                                )
                                if url:
                                    ui.run_javascript(
                                        f"window.open({url!r}, '_blank')"
                                    )
                                else:
                                    ui.notify(
                                        "Lien de téléchargement indisponible.",
                                        type="negative",
                                    )

                            async def modifier_f(
                                fid=fid, nom_actuel=nom, com_actuel=commentaire
                            ):
                                with ui.dialog() as dlg, ui.card().classes(
                                    "bg-slate-900 border border-slate-700 text-slate-100 p-5 w-[420px] max-w-full"
                                ):
                                    ui.label("Modifier la pièce jointe").classes(
                                        "text-base font-bold text-blue-300 mb-2"
                                    )
                                    inp_nom = ui.input(
                                        label="Nom affiché", value=nom_actuel
                                    ).classes("w-full")
                                    inp_com = ui.input(
                                        label="Commentaire", value=com_actuel
                                    ).classes("w-full")

                                    async def valider_modif():
                                        ok = await asyncio.to_thread(
                                            DatabaseService.update_fichier_crise,
                                            fid,
                                            inp_nom.value,
                                            inp_com.value,
                                        )
                                        if ok:
                                            ui.notify(
                                                "Pièce jointe mise à jour.",
                                                type="positive",
                                            )
                                            dlg.close()
                                            await refresh_fichiers()
                                        else:
                                            ui.notify(
                                                "Erreur de mise à jour.",
                                                type="negative",
                                            )

                                    with ui.row().classes("w-full justify-end gap-2 mt-3"):
                                        ui.button("Annuler", on_click=dlg.close).props(
                                            "flat color=grey"
                                        )
                                        ui.button(
                                            "Enregistrer",
                                            icon="save",
                                            on_click=valider_modif,
                                        ).props("color=blue sm font-bold")
                                dlg.open()

                            async def supprimer_f(fid=fid, nom_f=nom):
                                with ui.dialog() as dlg, ui.card().classes(
                                    "bg-slate-900 border border-red-800 text-white p-5"
                                ):
                                    ui.label(
                                        f"Supprimer « {nom_f} » ?"
                                    ).classes("text-base font-bold text-red-400 mb-2")
                                    ui.label(
                                        "Le fichier sera supprimé définitivement"
                                        " (stockage + fiche)."
                                    ).classes("text-xs text-slate-400")

                                    async def valider_suppr():
                                        ok = await asyncio.to_thread(
                                            DatabaseService.supprimer_fichier_crise, fid
                                        )
                                        if ok:
                                            ui.notify(
                                                "Pièce jointe supprimée.",
                                                type="negative",
                                            )
                                            dlg.close()
                                            await refresh_fichiers()
                                        else:
                                            ui.notify(
                                                "Erreur lors de la suppression.",
                                                type="negative",
                                            )

                                    with ui.row().classes("w-full justify-end gap-2 mt-3"):
                                        ui.button("Annuler", on_click=dlg.close).props(
                                            "flat color=grey"
                                        )
                                        ui.button(
                                            "Supprimer définitivement",
                                            icon="delete",
                                            color="red",
                                            on_click=valider_suppr,
                                        )
                                dlg.open()

                            with ui.row().classes(
                                "w-full justify-between items-center bg-slate-900/90 p-2 rounded border border-slate-700 text-xs"
                            ):
                                with ui.row().classes("items-center gap-2 overflow-hidden"):
                                    ui.icon(icone_mime(), color="blue-4", size="sm")
                                    with ui.column().classes("gap-0 overflow-hidden"):
                                        ui.label(nom).classes(
                                            "font-bold text-slate-200 truncate max-w-[260px]"
                                        )
                                        meta_bits = " | ".join(
                                            x for x in [taille_txt, cree_le] if x
                                        )
                                        if uploade:
                                            meta_bits += f" — {uploade}"
                                        ui.label(meta_bits).classes(
                                            "text-[10px] text-slate-500"
                                        )
                                        if commentaire:
                                            ui.label(commentaire).classes(
                                                "text-[10px] text-slate-400 italic truncate max-w-[300px]"
                                            )
                                with ui.row().classes("items-center gap-1"):
                                    ui.button(
                                        icon="download", on_click=telecharger
                                    ).props("flat color=blue-4 dense sm").tooltip(
                                        "Télécharger (lien signé 1 h)"
                                    )
                                    ui.button(
                                        icon="edit", on_click=modifier_f
                                    ).props("flat color=amber-4 dense sm").tooltip(
                                        "Modifier (nom / commentaire)"
                                    )
                                    ui.button(
                                        icon="delete", on_click=supprimer_f
                                    ).props("flat color=red dense sm").tooltip("Supprimer")

                MAX_TAILLE_PJ = 20 * 1024 * 1024  # 20 Mo

                async def on_upload_pj(e):
                    try:
                        fichier = e.file
                        nom = getattr(fichier, "name", "fichier")
                        mime = getattr(fichier, "content_type", "") or ""
                        if hasattr(fichier, "read"):
                            contenu = await fichier.read()
                        else:
                            contenu = getattr(fichier, "data", b"") or b""
                        if len(contenu) > MAX_TAILLE_PJ:
                            ui.notify(
                                f"« {nom} » dépasse 20 Mo — non ajouté.",
                                type="warning",
                            )
                            return
                        user_name = ""
                        try:
                            user_name = str(
                                app.storage.user.get("nom_complet", "") or ""
                            )
                        except Exception:
                            user_name = ""
                        row = await asyncio.to_thread(
                            DatabaseService.upload_fichier_crise,
                            crise_id,
                            nom,
                            contenu,
                            mime,
                            "",
                            user_name,
                        )
                        if row:
                            ui.notify(f"📎 {nom} ajouté à la cellule.", type="positive")
                            await refresh_fichiers()
                        else:
                            ui.notify(
                                f"Erreur lors de l'ajout de « {nom} ».",
                                type="negative",
                            )
                    except Exception as err:
                        print(f"❌ Erreur upload PJ crise : {err}")
                        ui.notify("Erreur lors de l'upload.", type="negative")

                ui.upload(
                    label="Ajouter des fichiers (jpg, png, pdf, office, eml, zip… — max 20 Mo)",
                    on_upload=on_upload_pj,
                    multiple=True,
                    auto_upload=True,
                ).props(
                    'accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.txt,.csv,.md,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.eml,.msg,.zip,.rar"'
                ).classes("w-full")

                await refresh_fichiers()
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

    # Liaison crise <-> site : crise « de niveau site » (site_impacte_id) ou crise nationale.
    site_impacte_actuel = str(
        (
            crise.get("site_impacte_id")
            if isinstance(crise, dict)
            else getattr(crise, "site_impacte_id", None)
        )
        or ""
    )
    sites_db = await asyncio.to_thread(DatabaseService.get_all_sites) or []
    options_sites = {"": "🌍 Crise nationale — aucun site rattaché"}
    for s in sites_db:
        sid = str(getattr(s, "id", "") or "")
        if sid:
            options_sites[sid] = f"{s.code_site} — {s.nom}"

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

                select_site = ui.select(
                    options=options_sites,
                    value=(
                        site_impacte_actuel
                        if site_impacte_actuel in options_sites
                        else ""
                    ),
                    label="Site impacté (crise de niveau site) — vide = crise nationale",
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
                        site_impacte_id=select_site.value or "",
                    )

                    if ok:
                        ui.notify("Fiche mise à jour !", type="positive")
                        dialog.close()
                        ui.navigate.reload()

                ui.button("Enregistrer", icon="save", on_click=update_crise_info).props(
                    "color=blue sm font-bold"
                ).classes("self-end")

        # Pièces jointes : dialogue dédié, ouvert depuis la carte crise
        # (bouton 📎 à côté de Main Courante / SITREP) et depuis ici.
        nb_pj = len(
            await asyncio.to_thread(DatabaseService.get_fichiers_crise, crise_id) or []
        )
        with ui.row().classes(
            "w-full items-center justify-between bg-slate-800/80 border border-slate-700 rounded mb-3 p-3"
        ):
            with ui.row().classes("items-center gap-2 overflow-hidden"):
                ui.icon("attach_file", color="amber-4", size="sm")
                ui.label(f"Pièces jointes ({code_crise})").classes(
                    "font-bold text-slate-200 text-sm truncate"
                )
                ui.label(f"{nb_pj} fichier(s)").classes("text-xs text-slate-400")
            ui.button(
                "Ouvrir",
                icon="open_in_new",
                on_click=lambda c=crise: open_fichiers_crise_dialog(c),
            ).props("color=amber sm font-bold")

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
                                categorie="DECISION",
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
            await _refresh_crises_tab_or_reload()

        async def archive_crise_action():
            await asyncio.to_thread(DatabaseService.archiver_crise, crise_id)
            dialog.close()
            await _refresh_crises_tab_or_reload()

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
