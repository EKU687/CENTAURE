import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from nicegui import ui
from app.services.database_service import db_service, DatabaseService

LOCAL_TZ = ZoneInfo("Pacific/Noumea")

# Référentiel de la Doctrine officielle CENTAURE
DOCTRINE_INFO = {
    "S1": {"titre": "Normal", "desc": "Posture nominale"},
    "S2": {"titre": "Renforcé", "desc": "Vigilance accrue"},
    "S3": {"titre": "Élevé", "desc": "Risque sérieux"},
    "S4": {"titre": "Critique", "desc": "Crise / menace imminente"},
    "T1": {"titre": "Optimal", "desc": "Systèmes opérationnels"},
    "T2": {"titre": "Dégradé", "desc": "Impact limité"},
    "T3": {"titre": "Critique", "desc": "Pannes majeures"},
    "T4": {"titre": "Hors-Service", "desc": "Perte totale"},
}


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


def create_site_page(code_site: str):
    """Génère la page de supervision locale ultra-compacte avec alertes visuelles progressives."""
    state = {
        "current_surete": None,
        "dialog_open": False,
        "acquitte": False,
        "audio_armed": False,
    }

    # Header Local Agent
    with ui.header().classes(
        "bg-slate-950 text-white items-center justify-between px-6 py-3 border-b border-slate-800"
    ):
        with ui.row().classes("items-center gap-3"):
            ui.icon("location_city", size="md", color="blue-4")
            ui.label(f"POSTE DE SUPERVISION LOCAL : {code_site.upper()}").classes(
                "text-xl font-bold"
            )

        with ui.row().classes("items-center gap-4"):

            def arm_audio():
                ui.run_javascript("""
                    if (!window.audioCtx) {
                        window.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                        window.audioCtx.resume();
                    }
                """)
                state["audio_armed"] = True
                btn_arm.set_visibility(False)
                badge_armed.set_visibility(True)
                ui.notify(
                    "Système audio armé et prêt pour les alertes S4 !", type="positive"
                )

            btn_arm = ui.button(
                "INITIALISER L'AUDIO DU POSTE", icon="volume_up", on_click=arm_audio
            ).props("color=positive sm font-bold")
            badge_armed = ui.badge(
                "AUDIO ARMÉ & SURVEILLANCE ACTIVE", color="positive"
            ).classes("animate-pulse")
            badge_armed.set_visibility(False)

    with ui.column().classes(
        "w-full h-[calc(100vh-65px)] bg-slate-900 text-slate-100 gap-0"
    ):
        content_container = ui.column().classes(
            "w-full px-8 py-4 gap-4 items-center justify-start overflow-y-auto flex-1"
        )
        # Section Main Courante terrain, hors de content_container : elle n'est
        # PAS reconstruite par le rafraîchissement 2 s (sinon le formulaire de
        # saisie serait vidé en cours de frappe).
        mc_container = ui.column().classes(
            "w-full px-8 pt-2 pb-3 gap-2 flex-none border-t border-slate-800 bg-slate-950/80"
        )

    def start_siren():
        ui.run_javascript("""
            if (!window.sirenInterval) {
                if (!window.audioCtx) {
                    window.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                }
                window.audioCtx.resume();

                window.sirenInterval = setInterval(() => {
                    if (window.audioCtx && window.audioCtx.state === 'running') {
                        const osc = window.audioCtx.createOscillator();
                        const gain = window.audioCtx.createGain();
                        osc.type = 'sawtooth';
                        osc.frequency.setValueAtTime(880, window.audioCtx.currentTime);
                        osc.frequency.exponentialRampToValueAtTime(440, window.audioCtx.currentTime + 0.4);
                        gain.gain.setValueAtTime(0.25, window.audioCtx.currentTime);
                        osc.connect(gain);
                        gain.connect(window.audioCtx.destination);
                        osc.start();
                        osc.stop(window.audioCtx.currentTime + 0.4);
                    }
                }, 600);
            }
        """)

    def stop_siren():
        ui.run_javascript("""
            if (window.sirenInterval) {
                clearInterval(window.sirenInterval);
                window.sirenInterval = null;
            }
        """)

    def render_content():
        sites = db_service.get_all_sites()
        site = next(
            (s for s in sites if s.code_site.upper() == code_site.upper()), None
        )

        if not site:
            content_container.clear()
            with content_container:
                ui.label(f"Site '{code_site}' non trouvé.").classes(
                    "text-red-500 text-2xl p-6"
                )
            return

        if site.surete_niveau != "S4":
            state["acquitte"] = False
            state["dialog_open"] = False
            stop_siren()

        if state["current_surete"] == site.surete_niveau and (
            state["dialog_open"] or state["acquitte"]
        ):
            return

        state["current_surete"] = site.surete_niveau
        content_container.clear()

        # Récupération du protocole actif en cours d'application sur ce site
        active_proto = DatabaseService.get_active_protocol_for_site(code_site)

        # Calcul dynamique des styles CSS de la carte Sûreté selon le niveau (S1 à S4)
        if site.surete_niveau == "S4":
            surete_card_style = "w-full p-5 bg-red-950/80 border-2 border-red-600 items-center justify-between shadow-2xl animate-pulse"
        elif site.surete_niveau == "S3":
            surete_card_style = "w-full p-5 bg-amber-950/70 border-2 border-amber-500 items-center justify-between shadow-xl animate-pulse"
        else:
            surete_card_style = "w-full p-5 bg-slate-800 border border-slate-700 items-center justify-between shadow-xl"

        with content_container:
            ui.label(f"État Opérationnel - {site.nom}").classes(
                "text-2xl font-extrabold tracking-tight text-slate-200"
            )

            # 1. GRILLE CÔTE À CÔTE (GRID 2 COLONNES : SÛRETÉ / TECHNIQUE)
            with ui.grid(columns=2).classes("w-full max-w-5xl gap-6 my-2"):

                # --- CARTE SÛRETÉ DYNAMIQUE ---
                s_info = DOCTRINE_INFO.get(
                    site.surete_niveau, {"titre": "", "desc": ""}
                )
                with ui.card().classes(surete_card_style):
                    ui.label("POSTURE SÛRETÉ").classes(
                        "text-xs font-bold text-slate-300 tracking-wider mb-1"
                    )

                    with ui.row().classes(
                        "items-center gap-4 my-1 w-full justify-center"
                    ):
                        ui.badge(
                            site.surete_niveau,
                            color=get_status_color(site.surete_niveau),
                        ).classes("text-4xl p-3 font-black rounded-xl")
                        with ui.column().classes("gap-0 text-left"):
                            ui.label(s_info["titre"]).classes(
                                "text-lg font-bold text-slate-100"
                            )
                            ui.label(s_info["desc"]).classes(
                                "text-xs text-slate-300 italic"
                            )

                # --- CARTE TECHNIQUE ---
                t_info = DOCTRINE_INFO.get(
                    site.technique_niveau, {"titre": "", "desc": ""}
                )
                with ui.card().classes(
                    "w-full p-5 bg-slate-800 border border-slate-700 items-center justify-between shadow-xl"
                ):
                    ui.label("ÉTAT TECHNIQUE").classes(
                        "text-xs font-bold text-slate-400 tracking-wider mb-1"
                    )

                    with ui.row().classes(
                        "items-center gap-4 my-1 w-full justify-center"
                    ):
                        ui.badge(
                            site.technique_niveau,
                            color=get_status_color(site.technique_niveau),
                        ).classes("text-4xl p-3 font-black rounded-xl")
                        with ui.column().classes("gap-0 text-left"):
                            ui.label(t_info["titre"]).classes(
                                "text-lg font-bold text-slate-100"
                            )
                            ui.label(t_info["desc"]).classes(
                                "text-xs text-slate-400 italic"
                            )

            # 2. BANDEAU DES CONSIGNES OPÉRATIONNELLES EN VIGUEUR (AMÉLIORÉ & ADOUCI)
            if active_proto:
                level = active_proto.get("niveau", site.surete_niveau)

                # Thème adouci (moins agressif) selon le niveau S
                if level == "S4":
                    border_color = "border-red-600/80 bg-red-950/40 animate-pulse"
                    badge_color = "negative"
                elif level == "S3":
                    border_color = "border-orange-500/50 bg-slate-800/90"
                    badge_color = "orange-8"
                elif level == "S2":
                    border_color = "border-amber-500/40 bg-slate-800/90 shadow-lg"  # Ambre doux & fond Slate reposant
                    badge_color = "warning"
                else:
                    border_color = "border-emerald-500/40 bg-slate-800/90"
                    badge_color = "positive"

                # Traitement propre des retours à la ligne (\n)
                raw_consignes = active_proto.get(
                    "consignes", "_Aucune consigne rédigée._"
                )
                formatted_consignes = raw_consignes.replace("\\n", "\n")

                with ui.card().classes(
                    f"w-full max-w-5xl border {border_color} p-4 rounded-xl my-2"
                ):
                    with ui.row().classes(
                        "items-center justify-between mb-3 border-b border-slate-700/80 pb-2 w-full"
                    ):
                        with ui.row().classes("items-center gap-2.5"):
                            ui.icon(
                                "assignment",
                                color="amber-4" if level == "S2" else "blue-4",
                                size="sm",
                            )
                            ui.label(
                                f"PROTOCOLE EN VIGUEUR : {active_proto.get('titre')}"
                            ).classes(
                                "font-bold text-base text-slate-100 tracking-wide"
                            )
                        ui.badge(f"POSTURE {level}", color=badge_color).classes(
                            "font-extrabold text-xs px-2.5 py-1"
                        )

                    ui.label(
                        "DIRECTIVES & CONSIGNES OPÉRATIONNELLES TERRAIN :"
                    ).classes(
                        "text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2"
                    )

                    # Boîte de consignes à fond sombre doux avec saut de ligne respecté (whitespace-pre-line / markdown)
                    with ui.column().classes(
                        "w-full bg-slate-950/70 p-4 rounded-lg border border-slate-800"
                    ):
                        ui.markdown(formatted_consignes).classes(
                            "text-sm text-slate-200 leading-relaxed space-y-1"
                        )
            else:
                with ui.card().classes(
                    "w-full max-w-5xl bg-slate-800/40 border border-slate-700 p-3 items-center justify-center my-2"
                ):
                    ui.label(
                        "Aucun protocole spécifique n'est actuellement sélectionné pour cette posture."
                    ).classes("text-xs text-slate-400 italic")

            # 3. ANOMALIES & DYSFONCTIONNEMENTS TECHNIQUES EN COURS
            if site.anomalies:
                with ui.card().classes(
                    "w-full max-w-5xl bg-slate-800/90 border border-amber-500/50 p-4 shadow-xl mb-2"
                ):
                    with ui.row().classes(
                        "items-center gap-2 mb-2 border-b border-slate-700 pb-1 w-full"
                    ):
                        ui.icon("warning", color="amber", size="xs")
                        ui.label("ANOMALIES ET MAINTENANCES EN COURS").classes(
                            "font-bold text-xs text-amber-400 tracking-wide"
                        )

                    with ui.column().classes("w-full gap-2 max-h-40 overflow-y-auto"):
                        for ano in site.anomalies:
                            with ui.row().classes(
                                "w-full justify-between items-center bg-slate-900/80 p-2 rounded border border-slate-700 text-xs"
                            ):
                                with ui.row().classes("items-center gap-2"):
                                    ui.badge(
                                        ano.domaine,
                                        color=(
                                            "orange-9"
                                            if ano.domaine == "SURETE"
                                            else "blue-9"
                                        ),
                                    ).classes("font-bold text-[10px]")
                                    ui.label(ano.equipement).classes(
                                        "font-bold text-slate-200"
                                    )
                                ui.label(ano.description or "Aucune précision").classes(
                                    "text-slate-300 italic"
                                )

            # 4. BANDEAU DE CONFIRMATION S4 ACQUITTÉ
            if site.surete_niveau == "S4" and state["acquitte"]:
                with ui.card().classes(
                    "w-full max-w-5xl bg-red-950/80 border-2 border-red-600 p-3 items-center shadow-2xl"
                ):
                    with ui.row().classes("items-center gap-3 text-red-200"):
                        ui.icon("check_circle", color="positive", size="sm")
                        ui.label(
                            "ORDRE DE CONFINEMENT S4 ACQUITTÉ PAR L'AGENT - CONSIGNES EN COURS"
                        ).classes("font-bold text-xs tracking-wide")

            # 5. POP-UP DE CONFINEMENT S4
            if (
                site.surete_niveau == "S4"
                and not state["dialog_open"]
                and not state["acquitte"]
            ):
                state["dialog_open"] = True
                start_siren()

                with ui.dialog() as dialog_s4, ui.card().classes(
                    "w-full max-w-3xl bg-slate-950 border-4 border-red-600 text-white p-8 items-center text-center shadow-2xl"
                ):
                    ui.icon("gavel", size="xl", color="red-5").classes(
                        "mb-2 animate-pulse"
                    )
                    ui.label("⚠️ ORDRE DE CONFINEMENT IMMÉDIAT (S4) ⚠️").classes(
                        "text-3xl font-black tracking-wider text-red-500 mb-4"
                    )

                    ui.label("CONSIGNES ET PROTOCOLE DE SÛRETÉ À APPLIQUER :").classes(
                        "text-sm font-bold text-slate-300 mb-2"
                    )

                    # Utilisation du protocole S4 actif sinon texte par défaut
                    s4_proto_text = (
                        active_proto.get("consignes")
                        if active_proto and active_proto.get("niveau") == "S4"
                        else site.protocole_confinement
                        or "Appliquer la procédure de confinement générale du site."
                    )
                    formatted_protocol = s4_proto_text.replace("\\n", "\n")

                    with ui.card().classes(
                        "w-full bg-slate-900 p-5 border border-red-900/80 mb-6 text-left"
                    ):
                        ui.markdown(formatted_protocol).classes(
                            "text-base text-slate-100 font-mono leading-relaxed"
                        )

                    def acquitter():
                        stop_siren()
                        if db_service.acquitter_alerte_s4(
                            site.id, agent_nom=f"Agent {site.code_site}"
                        ):
                            ui.notify(
                                "Acquittement transmitted au PC Crise ! Alarme sonore coupée.",
                                type="positive",
                            )
                            state["dialog_open"] = False
                            state["acquitte"] = True
                            dialog_s4.close()
                            render_content()

                    ui.button(
                        "J'ACQUITTE L'ORDRE DE CONFINEMENT",
                        icon="check_circle",
                        on_click=acquitter,
                    ).props("color=red-7 size=lg font-bold").classes(
                        "w-full py-4 shadow-xl cursor-pointer"
                    )

                dialog_s4.open()

    # ------------------------------------------------------------------
    # MAIN COURANTE TERRAIN (poste de garde) — les événements sont consignés
    # dans la cellule de crise rattachée au site (site_impacte_id), si elle
    # existe. Crise nationale (site_impacte_id NULL) => pas de consignation
    # terrain sur ce poste.
    # ------------------------------------------------------------------
    mc_state = {"crise": None, "journal": None}

    def _site_courant():
        sites = db_service.get_all_sites()
        return next(
            (s for s in sites if s.code_site.upper() == code_site.upper()), None
        )

    def _fmt_heure_mc(raw) -> str:
        if not raw:
            return "--:--"
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return dt.astimezone(LOCAL_TZ).strftime("%H:%M")
        except Exception:
            return str(raw)[11:16]

    def _render_mc_journal(logs):
        """Remplit le journal (appelé dans le contexte du conteneur journal)."""
        if not logs:
            ui.label("Aucun événement consigné pour le moment.").classes(
                "text-xs text-slate-500 italic p-1"
            )
            return
        for l in logs[:10]:
            cat = str(l.get("categorie") or "INFO").upper()
            prio = str(l.get("niveau_priorite") or "NORMALE").upper()
            prio_color = (
                "red"
                if prio == "CRITIQUE"
                else ("amber" if prio == "URGENT" else "slate-7")
            )
            desc = str(l.get("description") or l.get("message") or "")
            with ui.row().classes("w-full items-center gap-2 text-xs flex-none"):
                ui.label(
                    _fmt_heure_mc(l.get("horodatage") or l.get("created_at"))
                ).classes("font-mono font-bold text-slate-300 w-10 flex-none")
                ui.badge(cat, color="grey-8").classes("font-mono text-[10px]")
                ui.badge(prio, color=prio_color).classes("text-[10px]")
                ui.label(desc).classes("text-slate-200 flex-grow truncate").tooltip(desc)
                ui.label(str(l.get("auteur") or "")).classes(
                    "text-slate-400 font-bold whitespace-nowrap flex-none"
                )

    def render_mc():
        """Rebuild complet de la section main courante terrain."""
        mc_container.clear()
        site = _site_courant()
        crise = DatabaseService.get_active_crise_for_site(site.id) if site else None
        mc_state["crise"] = crise
        mc_state["journal"] = None

        with mc_container:
            with ui.row().classes(
                "w-full max-w-5xl items-center justify-between flex-wrap gap-2"
            ):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("assignment", color="amber-4", size="sm")
                    ui.label(f"MAIN COURANTE TERRAIN — {code_site.upper()}").classes(
                        "text-sm font-black text-amber-400 tracking-wider"
                    )
                if crise:
                    badge_color = "red" if crise.get("statut") == "ACTIVEE" else "amber"
                    ui.badge(
                        f"Cellule : {crise.get('code_crise')} ({crise.get('statut')})",
                        color=badge_color,
                    ).classes("font-bold text-[10px]")
                else:
                    ui.badge("AUCUNE CELLULE RATTACHÉE", color="grey-7").classes(
                        "font-bold text-[10px]"
                    )

            if not crise:
                ui.label(
                    "Aucune cellule de crise n'est rattachée à ce site : la consignation "
                    "terrain est indisponible. Le PCO peut lier une cellule à ce site "
                    "depuis l'onglet « Cellules de Crise » (champ « Site impacté »)."
                ).classes("text-xs text-slate-400 italic max-w-5xl")
                return

            with ui.row().classes("w-full max-w-5xl gap-2 items-end flex-wrap"):
                select_cat = ui.select(
                    options=[
                        "RONDE",
                        "INCIDENT",
                        "PRISE_DE_POSTE",
                        "ANOMALIE",
                        "INFORMATION",
                    ],
                    value="INFORMATION",
                    label="Catégorie",
                ).classes("w-44 bg-slate-900").props("dense")
                select_prio = ui.select(
                    options=["NORMALE", "URGENT", "CRITIQUE"],
                    value="NORMALE",
                    label="Priorité",
                ).classes("w-36 bg-slate-900").props("dense")
                input_mc = ui.input(
                    label="Événement à consigner",
                    placeholder="Ex : Ronde 14h00 effectuée — RAS...",
                ).classes("flex-grow min-w-[240px] bg-slate-900")

                async def consigner_terrain():
                    texte = str(input_mc.value or "").strip()
                    if not texte:
                        ui.notify("Saisissez d'abord un événement.", type="warning")
                        return
                    ok = await asyncio.to_thread(
                        DatabaseService.consigner_main_courante,
                        crise_id=crise.get("id"),
                        description=texte,
                        categorie=select_cat.value,
                        auteur=f"Agent {code_site.upper()}",
                        niveau_priorite=select_prio.value,
                        statut_info="CONFIRMEE",
                        is_sitrep=False,
                    )
                    if ok:
                        ui.notify(
                            "Événement consigné dans la main courante.", type="positive"
                        )
                        input_mc.value = ""
                        await refresh_mc_journal()
                    else:
                        ui.notify(
                            "Échec de la consignation dans Supabase.", type="negative"
                        )

                ui.button(
                    "CONSIGNER", icon="send", on_click=consigner_terrain
                ).props("color=amber-7 text-white font-bold sm")

            mc_journal = ui.column().classes(
                "w-full max-w-5xl gap-1 max-h-36 overflow-y-auto bg-slate-900/60 "
                "border border-slate-800 rounded p-2"
            )
            mc_state["journal"] = mc_journal
            with mc_journal:
                _render_mc_journal(
                    DatabaseService.get_main_courante_by_crise(crise.get("id")) or []
                )

    async def refresh_mc_journal():
        crise = mc_state.get("crise")
        journal = mc_state.get("journal")
        if not crise or journal is None:
            return
        logs = (
            await asyncio.to_thread(
                DatabaseService.get_main_courante_by_crise, crise.get("id")
            )
            or []
        )
        journal.clear()
        with journal:
            _render_mc_journal(logs)

    async def tick_mc():
        """Re-vérifie la liaison crise/site toutes les 10 s : rebuild de la section
        si la cellule rattachée a changé, sinon simple rafraîchissement du journal."""
        site = await asyncio.to_thread(_site_courant)
        crise = (
            await asyncio.to_thread(DatabaseService.get_active_crise_for_site, site.id)
            if site
            else None
        )
        old_id = str((mc_state.get("crise") or {}).get("id") or "")
        new_id = str((crise or {}).get("id") or "")
        if old_id != new_id:
            render_mc()
        else:
            await refresh_mc_journal()

    render_mc()
    ui.timer(10.0, tick_mc)

    render_content()
    ui.timer(2.0, render_content)
