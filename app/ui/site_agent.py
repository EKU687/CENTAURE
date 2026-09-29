from nicegui import ui
from app.services.database_service import db_service

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

    content_container = ui.column().classes(
        "w-full px-8 py-4 gap-4 bg-slate-900 h-[calc(100vh-65px)] text-slate-100 items-center justify-start overflow-hidden"
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

            # 1. GRILLE CÔTE À CÔTE (GRID 2 COLONNES)
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

            # 2. BANDEAU DES MOTIFS ET CONSIGNES
            if site.anomalies:
                with ui.card().classes(
                    "w-full max-w-5xl bg-slate-800/90 border border-amber-500/50 p-4 shadow-xl"
                ):
                    with ui.row().classes(
                        "items-center gap-2 mb-2 border-b border-slate-700 pb-1 w-full"
                    ):
                        ui.icon("warning", color="amber", size="xs")
                        ui.label("CONSIGNES & MOTIFS DES ALERTES EN COURS").classes(
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
            else:
                with ui.card().classes(
                    "w-full max-w-5xl bg-slate-800/40 border border-slate-700 p-3 items-center justify-center"
                ):
                    ui.label(
                        "Aucun dysfonctionnement technique ou alerte particulière signalée."
                    ).classes("text-xs text-slate-400 italic")

            # 3. BANDEAU DE CONFIRMATION S4 ACQUITTÉ
            if site.surete_niveau == "S4" and state["acquitte"]:
                with ui.card().classes(
                    "w-full max-w-5xl bg-red-950/80 border-2 border-red-600 p-3 items-center shadow-2xl"
                ):
                    with ui.row().classes("items-center gap-3 text-red-200"):
                        ui.icon("check_circle", color="positive", size="sm")
                        ui.label(
                            "ORDRE DE CONFINEMENT S4 ACQUITTÉ PAR L'AGENT - CONSIGNES EN COURS"
                        ).classes("font-bold text-xs tracking-wide")

            # 4. POP-UP DE CONFINEMENT S4
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

                    raw_protocol = (
                        site.protocole_confinement
                        or "Appliquer la procédure de confinement générale du site."
                    )
                    formatted_protocol = raw_protocol.replace("\\n", "\n")

                    with ui.card().classes(
                        "w-full bg-slate-900 p-5 border border-red-900/80 mb-6 text-left"
                    ):
                        ui.label(formatted_protocol).classes(
                            "text-base text-slate-100 whitespace-pre-line font-mono leading-relaxed"
                        )

                    def acquitter():
                        stop_siren()
                        if db_service.acquitter_alerte_s4(
                            site.id, agent_nom=f"Agent {site.code_site}"
                        ):
                            ui.notify(
                                "Acquittement transmis au PC Crise ! Alarme sonore coupée.",
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

    render_content()
    ui.timer(2.0, render_content)
