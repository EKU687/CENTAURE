"""Écran mural de supervision globale (CENTAURE — GNC).

Page dédiée à l'affichage type « salle de surveillance » : tous les sites
sensibles en grille dense, statuts sûreté (S) et technique (T), rafraîchis
automatiquement. Lecture seule — aucune action n'est possible depuis cette
page (les arbitrages se font depuis le cockpit, jeton agent requis).
Accès par jeton kiosque valide, identique aux postes de garde /site/<CODE>.

Alerte sonore S4 (confinement) : au passage d'un site en S4, bannière rouge
+ sirène Web Audio en boucle jusqu'à acquittement. Le son doit être « armé »
une fois par clic (règle d'autoplay des navigateurs) ; le retour d'un site
en S4 après en être sorti déclenche un nouvel épisode d'alarme.
"""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from nicegui import background_tasks, ui

from app.services.database_service import DatabaseService

LOCAL_TZ = ZoneInfo("Pacific/Noumea")
REFRESH_SECONDS = 10.0

_COLOR_NIVEAU = {
    "S1": "positive",
    "T1": "positive",
    "S2": "warning",
    "T2": "warning",
    "S3": "orange-8",
    "T3": "orange-8",
    "S4": "negative",
    "T4": "negative",
}

# Initialisation Web Audio + sirène nucléaire : oscillateur dent de scie
# dont la fréquence monte et descend en continu (~0.2 Hz, 390-1250 Hz),
# plus perçant qu'un bip. Le son doit être « armé » par un clic.
_JS_ALARME = """
if (!window.__centaure_alarme) { window.__centaure_alarme = {ctx: null, armed: false, noeuds: null}; }
const a = window.__centaure_alarme;
a.bip = (freq, t0, dur) => {
    if (!a.ctx) return;
    const osc = a.ctx.createOscillator();
    const g = a.ctx.createGain();
    osc.type = 'square';
    osc.frequency.value = freq;
    osc.connect(g); g.connect(a.ctx.destination);
    const t = a.ctx.currentTime + t0;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.10, t + 0.02);
    g.gain.setValueAtTime(0.10, Math.max(t + 0.02, t + dur - 0.05));
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    osc.start(t); osc.stop(t + dur + 0.05);
};
a.start = () => {
    if (a.noeuds || !a.armed || !a.ctx) return;
    const t = a.ctx.currentTime;
    const osc = a.ctx.createOscillator();
    const lfo = a.ctx.createOscillator();
    const lfoGain = a.ctx.createGain();
    const g = a.ctx.createGain();
    osc.type = 'sawtooth';
    osc.frequency.value = 820;
    lfo.type = 'triangle';
    lfo.frequency.value = 0.2;
    lfoGain.gain.value = 430;
    lfo.connect(lfoGain);
    lfoGain.connect(osc.frequency);
    osc.connect(g);
    g.connect(a.ctx.destination);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.15, t + 0.2);
    osc.start(t);
    lfo.start(t);
    a.noeuds = { osc: osc, lfo: lfo, g: g };
};
a.stop = () => {
    if (!a.noeuds) return;
    const n = a.noeuds;
    a.noeuds = null;
    const t = a.ctx.currentTime;
    try {
        n.g.gain.cancelScheduledValues(t);
        n.g.gain.setValueAtTime(Math.max(n.g.gain.value, 0.0001), t);
        n.g.gain.exponentialRampToValueAtTime(0.0001, t + 0.3);
        setTimeout(() => {
            try { n.osc.stop(); n.lfo.stop(); } catch (e) {}
        }, 350);
    } catch (e) {}
};
a.ctx = a.ctx || new (window.AudioContext || window.webkitAudioContext)();
a.ctx.resume().then(() => {
    a.armed = true;
    /* confirmation d'armement : trois notes montantes */
    a.bip(660, 0, 0.12);
    a.bip(880, 0.16, 0.12);
    a.bip(1170, 0.32, 0.16);
});
"""


def _statut_tile(site) -> str:
    """Classe de tuile selon la gravité (logique identique au cockpit)."""
    if site.surete_niveau == "S4":
        return "bg-red-950/90 border-4 border-red-600 text-slate-100 shadow-2xl animate-pulse"
    if site.surete_niveau == "S3":
        return "bg-amber-950/40 border-2 border-amber-500 text-slate-100 shadow-xl animate-pulse"
    if site.surete_niveau == "S2" or site.technique_niveau in ["T2", "T3", "T4"]:
        return "bg-slate-900 border border-amber-600/60 text-slate-100 shadow-lg"
    return "bg-slate-800 border border-slate-700 text-slate-100 shadow-lg"


def _jeton_niveau(niveau: str) -> ui.badge:
    return ui.badge(niveau, color=_COLOR_NIVEAU.get(niveau, "grey")).classes(
        "text-xs font-mono font-bold px-2"
    )


def create_wall_page():
    """Construit l'écran mural complet (appelé après validation du jeton)."""

    # État par écran (instance de page = un écran mural) :
    # sites en S4 au tour précédent, épisodes acquittés, son armé ou non.
    etat = {
        "armed": False,
        "prev_s4": set(),
        "acked": set(),
        "unacked": set(),
    }

    # ------------------------------------------------------------------
    # Bandeau supérieur : identité + horloge + armement sonore
    # ------------------------------------------------------------------
    with ui.header().classes(
        "bg-slate-950 text-white items-center justify-between px-8 py-3 border-b border-slate-700"
    ):
        with ui.row().classes("items-center gap-4"):
            ui.icon("shield", size="md", color="red-5")
            ui.label("CENTAURE").classes(
                "text-2xl font-black tracking-widest text-red-500"
            )
            ui.label("| ÉCRAN DE SUPERVISION GLOBALE").classes(
                "text-sm text-slate-400 font-medium tracking-wide"
            )

        with ui.row().classes("items-center gap-6"):
            btn_son = (
                ui.button("SON D'ALERTE : INACTIF", icon="volume_off")
                .props("color=grey-8 outline sm")
                .tooltip(
                    "Cliquer une fois pour armer la sirène S4 "
                    "(obligatoire : les navigateurs exigent un clic avant tout son)"
                )
            )

            def armer_son():
                ui.run_javascript(_JS_ALARME)
                etat["armed"] = True
                btn_son.set_text("SON D'ALERTE : ARMÉ")
                btn_son.props("color=positive outline sm")
                btn_son.props(remove="color=grey-8")
                btn_son.props("icon=volume_up")

            btn_son.on_click(armer_son)

            horloge = ui.label().classes("text-3xl font-mono font-bold text-slate-100")
            maj_label = ui.label().classes("text-[10px] text-slate-500 font-mono")

    # ------------------------------------------------------------------
    # Bannière d'alarme S4 (visible seulement si épisode non acquitté)
    # ------------------------------------------------------------------
    alarme_container = ui.column().classes("hidden w-full px-6 pt-4")
    client_page = alarme_container.client

    # ------------------------------------------------------------------
    # Bandeau KPI d'alertes
    # ------------------------------------------------------------------
    kpi_container = ui.row().classes("w-full gap-6 justify-center py-4")

    # ------------------------------------------------------------------
    # Grille des sites
    # ------------------------------------------------------------------
    with ui.column().classes("w-full max-w-[1800px] mx-auto p-6 gap-4"):
        with ui.row().classes("w-full justify-between items-center"):
            ui.label("SITES SENSIBLES — HYPERVISION").classes(
                "text-xl font-bold text-slate-300 tracking-wide"
            )
            nb_sites_label = ui.label().classes("text-sm text-slate-500 font-mono")

        sites_grid = ui.grid().classes(
            "grid-cols-2 md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-6 gap-3 w-full"
        )

    erreur_liaison = ui.label().classes("hidden w-full text-center")

    def _maj_horloge():
        now = datetime.now(LOCAL_TZ)
        horloge.set_text(now.strftime("%H:%M:%S"))
        maj_label.set_text(
            f"Fuseau NC — {now.strftime('%A %d %m %Y').capitalize()}"
        )

    def _maj_alarme(unacked: set):
        """(Re)construit la bannière et pilote la sirène selon l'état."""
        etat["unacked"] = set(unacked)
        alarme_container.clear()
        if not unacked:
            alarme_container.classes(add="hidden")
            ui.run_javascript("window.__centaure_alarme && window.__centaure_alarme.stop && window.__centaure_alarme.stop();")
            return

        alarme_container.classes(remove="hidden")
        with alarme_container:
            with ui.row().classes(
                "w-full items-center justify-between bg-red-700/95 border-4 border-red-300 "
                "rounded-lg px-6 py-4 gap-4 shadow-2xl"
            ):
                with ui.row().classes("items-center gap-4"):
                    ui.icon("warning", size="xl", color="red-2").classes(
                        "animate-pulse"
                    )
                    with ui.column().classes("gap-0"):
                        ui.label("ALERTE S4 — CONFINEMENT").classes(
                            "text-2xl font-black text-white tracking-wider"
                        )
                        ui.label(", ".join(sorted(unacked))).classes(
                            "text-lg font-bold text-red-50"
                        )
                        if not etat["armed"]:
                            ui.label(
                                "⚠ Son non armé : cliquez sur « SON D'ALERTE » en haut à droite."
                            ).classes("text-xs text-amber-200")
                ack_btn = (
                    ui.button("ACQUITTER", icon="notifications_off")
                    .props("color=white text-color=red-10 size=md unelevated font-bold")
                    .classes("text-base font-black tracking-wide px-6 py-2")
                    .tooltip("Arrête la sirène — le site reste affiché en S4")
                )

                def acquitter():
                    # Le clic supprime ce bouton (reconstruction de la bannière) :
                    # le rafraîchissement doit donc porter son propre contexte
                    # client, en tâche de fond — sinon `ui.run_javascript`
                    # (stop sirène) lève une erreur d'élément supprimé.
                    etat["acked"].update(etat["unacked"])
                    etat["unacked"].clear()

                    async def _refresh():
                        with client_page:
                            await _maj_grille()

                    background_tasks.create(_refresh(), name="wall acquittement")

                ack_btn.on_click(acquitter)

        if etat["armed"]:
            ui.run_javascript("window.__centaure_alarme && window.__centaure_alarme.start && window.__centaure_alarme.start();")
        else:
            ui.run_javascript("window.__centaure_alarme && window.__centaure_alarme.stop && window.__centaure_alarme.stop();")

    async def _maj_grille():
        maj_label.set_text("Actualisation en cours…")
        try:
            sites = await asyncio.to_thread(DatabaseService.get_all_sites) or []
        except Exception as exc:  # liaison perdue : on garde le dernier rendu
            print(f"❌ [WALL] Erreur lecture sites : {exc}")
            erreur_liaison.classes(remove="hidden")
            erreur_liaison.set_text(
                "⚠ Perte de liaison avec la base — dernier état affiché."
            ).classes("text-amber-400 font-bold")
            maj_label.set_text(f"Dernière MaJ : {datetime.now(LOCAL_TZ).strftime('%H:%M:%S')}")
            return

        erreur_liaison.classes(add="hidden")
        nb_sites_label.set_text(
            f"{len(sites)} site(s) suivis — MaJ auto {int(REFRESH_SECONDS)} s"
        )

        # ---- Détection des passages en S4 (nouveaux épisodes) ----
        s4_now = {s.code_site for s in sites if s.surete_niveau == "S4"}
        for code in s4_now - etat["prev_s4"]:
            etat["acked"].discard(code)  # retour en S4 = nouvel épisode
        etat["acked"] &= s4_now  # on oublie les acquittements des sites sortis de S4
        etat["prev_s4"] = s4_now
        _maj_alarme(s4_now - etat["acked"])

        # ---- Bandeau KPI (seulement les niveaux en alerte) ----
        kpi_container.clear()
        stats = {
            "S4": sum(1 for s in sites if s.surete_niveau == "S4"),
            "S3": sum(1 for s in sites if s.surete_niveau == "S3"),
            "T4": sum(1 for s in sites if s.technique_niveau == "T4"),
            "T3": sum(1 for s in sites if s.technique_niveau == "T3"),
        }
        with kpi_container:
            for niveau, nb in stats.items():
                if nb > 0:
                    couleur = {
                        "S4": "red",
                        "S3": "amber",
                        "T4": "orange",
                        "T3": "orange-8",
                    }[niveau]
                    pulse = " animate-pulse" if niveau in ("S4", "S3") else ""
                    ui.badge(
                        f"{'🚨' if niveau in ('S4', 'T4') else '⚠️'} {nb} {niveau}",
                        color=couleur,
                    ).classes(f"text-xl font-bold px-6 py-3{pulse}")

        # ---- Tuiles sites ----
        sites_grid.clear()
        with sites_grid:
            for site in sites:
                anomalie_active = sum(
                    1 for a in (site.anomalies or []) if a.statut == "ACTIF"
                )
                with ui.card().classes(
                    f"{_statut_tile(site)} p-3 flex flex-col gap-1 min-h-[110px]"
                ):
                    with ui.row().classes("items-center justify-between w-full"):
                        ui.label(site.code_site).classes(
                            "font-extrabold text-lg text-slate-50"
                        )
                        with ui.row().classes("gap-1"):
                            _jeton_niveau(site.surete_niveau)
                            _jeton_niveau(site.technique_niveau)
                    ui.label(site.nom).classes(
                        "text-xs text-slate-300 ellipsis overflow-hidden whitespace-nowrap"
                    )
                    with ui.row().classes("justify-between items-center w-full mt-auto"):
                        ui.label(site.localisation or "N/C").classes(
                            "text-[10px] text-slate-400"
                        )
                        if anomalie_active:
                            ui.badge(
                                f"{anomalie_active} anomalie(s)", color="negative"
                            ).classes("text-[9px]")
                        elif getattr(site, "est_en_confinement", False):
                            ui.label("CONFINEMENT").classes(
                                "text-[9px] font-black text-red-400 tracking-wider"
                            )

        maj_label.set_text(
            f"Fuseau NC — dernière MaJ : {datetime.now(LOCAL_TZ).strftime('%H:%M:%S')}"
        )

    _maj_horloge()
    ui.timer(1.0, _maj_horloge)
    # Premier rendu de la grille dès l'ouverture, puis MaJ périodique
    ui.timer(0.1, _maj_grille, once=True)
    ui.timer(REFRESH_SECONDS, _maj_grille)
