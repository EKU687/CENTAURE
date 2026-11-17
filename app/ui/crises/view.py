import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from nicegui import app, ui
from app.services.database_service import DatabaseService
from app.ui.crises.sitrep_dialog import SitrepService, open_sitrep_dialog
from app.ui.crises.main_courante_dialog import open_main_courante_dialog
from app.ui.crises.crise_dialogs import (
    activer_et_notifier_crise,
    open_new_crise_dialog,
    open_edit_crise_dialog,
    open_fichiers_crise_dialog,
)
from app.ui.crises.fin_de_journee_dialog import open_fin_de_journee_dialog

LOCAL_TZ = ZoneInfo("Pacific/Noumea")

# Échelle fixe des gravités de crise : N1 bleu, N2 ambre, N3 orange, N4 rouge.
GRAVITE_STYLES = {
    "1": ("text-blue-400", "blue"),
    "2": ("text-amber-400", "amber"),
    "3": ("text-orange-400", "orange"),
    "4": ("text-red-400", "red"),
}


def gravite_styles(niveau) -> tuple:
    """Retourne (classe texte Tailwind, couleur badge Quasar) pour une gravité."""
    n = str(niveau or "1").replace("N", "").strip() or "1"
    return GRAVITE_STYLES.get(n, ("text-slate-400", "grey"))


class _DialogStub:
    """Stub de dialogue pour l'activation lancée depuis la carte PCO
    (la page est rechargée automatiquement après activation)."""

    def close(self):
        pass


def _parse_dt(raw) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def _fmt_heure(dt: datetime | None) -> str:
    if dt is None:
        return "N/A"
    return dt.astimezone(LOCAL_TZ).strftime("%d/%m/%Y %H:%M")


def _chrono_depuis(dt_depart: datetime | None) -> str:
    """Durée écoulée formatée HH:MM:SS depuis l'activation."""
    if dt_depart is None:
        return "--:--:--"
    delta = datetime.now(LOCAL_TZ) - dt_depart.astimezone(LOCAL_TZ)
    total = max(0, int(delta.total_seconds()))
    h, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    if h >= 24:
        j = h // 24
        return f"{j}j {h % 24:02d}:{m:02d}:{s:02d}"
    return f"{h:02d}:{m:02d}:{s:02d}"


def _fmt_dernier_sitrep(dernier_sitrep: dict | None) -> str:
    """Texte affiché dans l'indicateur « Dernier SITREP » d'une carte PCO."""
    if not dernier_sitrep:
        return "Aucun"
    type_s = str(dernier_sitrep.get("type_sitrep", "STANDARD"))
    suffixe = " (fin de journée)" if type_s == "CLOTURE_JOURNALIERE" else ""
    return (
        f"#{dernier_sitrep.get('numero_sitrep', '?')}{suffixe} — "
        f"{_fmt_heure(_parse_dt(dernier_sitrep.get('horodatage')))}"
    )


def _charger_suivi_cellule(crise_id: str) -> dict:
    """Aggrège, pour une cellule, les indicateurs PCO (exécuté en thread)."""
    membres = DatabaseService.get_membres_crise(crise_id) or []
    logs = DatabaseService.get_main_courante_by_crise(crise_id) or []
    dernier_sitrep = SitrepService.get_last_sitrep_by_crise(crise_id)

    directeur = next(
        (
            m
            for m in membres
            if "directeur" in str(m.get("fonction_crise", "")).lower()
        ),
        None,
    )

    nb_evt = len(logs)
    nb_evt_apres_sitrep = nb_evt
    if dernier_sitrep:
        dt_sitrep = _parse_dt(dernier_sitrep.get("horodatage"))
        if dt_sitrep is not None:
            nb_evt_apres_sitrep = sum(
                1
                for l in logs
                if (_parse_dt(l.get("horodatage") or l.get("created_at")) or datetime.min.replace(tzinfo=LOCAL_TZ))
                > dt_sitrep
            )

    return {
        "membres": membres,
        "directeur": (
            f"{directeur.get('centaure_annuaire', {}).get('nom', '')} "
            f"{directeur.get('centaure_annuaire', {}).get('prenom', '')}".strip()
            if directeur
            else None
        ),
        "nb_membres": len(membres),
        "nb_evt": nb_evt,
        "nb_evt_apres_sitrep": nb_evt_apres_sitrep,
        "dernier_sitrep": dernier_sitrep,
    }


async def render_crises_view(is_sg_admin: bool = False):
    """Vue Poste de Commandement Opérationnel (PCO) — pilotage multi-cellules."""

    # Site dont la carte du cockpit a déclenché le branchement direct :
    # la cellule liée à ce site (site_impacte_id) est mise en évidence.
    try:
        focus_site_id = str(app.storage.client.get("crise_focus_site_id") or "")
    except Exception:
        focus_site_id = ""

    # Map id site -> code pour afficher le rattachement de chaque cellule.
    sites_map = {}
    try:
        for s in await asyncio.to_thread(DatabaseService.get_all_sites) or []:
            sid = getattr(s, "id", None)
            if sid:
                sites_map[str(sid)] = s.code_site
    except Exception as err:
        print(f"⚠️ Erreur chargement map sites : {err}")
    with ui.row().classes("items-center justify-between w-full mb-4 flex-wrap"):
        with ui.column().classes("gap-0"):
            ui.label("PCO — Poste de Commandement Opérationnel").classes(
                "text-2xl font-black"
            )
            ui.label(
                "Pilotage des cellules de crise & bulletins de fin de journée"
            ).classes("text-xs text-slate-400")

        with ui.row().classes("items-center gap-2"):
            if is_sg_admin:
                ui.button(
                    "🌙 SITREP FIN DE JOURNÉE",
                    icon="nightlight_round",
                    on_click=open_fin_de_journee_dialog,
                ).props("color=indigo font-bold sm")
                ui.button(
                    "DÉCLARER UNE CRISE",
                    icon="add_alert",
                    on_click=open_new_crise_dialog,
                ).props("color=red font-bold sm animate-pulse")

    crises = await asyncio.to_thread(DatabaseService.get_active_crises) or []

    # ------------------------------------------------------------------
    # Bandeau de synthèse PCO
    # ------------------------------------------------------------------
    activ = [c for c in crises if c.get("statut") == "ACTIVEE"]
    sommeil = [c for c in crises if c.get("statut") == "EN_SOMMEIL"]
    gravite_max = max(
        (str(c.get("niveau_gravite", "1")).replace("N", "") for c in crises),
        default="0",
    )

    with ui.row().classes("w-full gap-3 mb-4 flex-wrap"):
        gravite_libelle = (
            f"N{gravite_max}" if crises and gravite_max not in ("0", "") else "—"
        )
        g_txt, _g_badge = gravite_styles(gravite_max)
        for label, valeur, txt_cls in [
            ("Cellules ACTIVÉES", str(len(activ)), "text-red-400"),
            ("Cellules en VEILLE", str(len(sommeil)), "text-amber-400"),
            ("Gravité maximale", gravite_libelle, g_txt),
        ]:
            with ui.card().classes(
                "flex-1 min-w-[140px] bg-slate-800/60 border border-slate-700 p-3 "
                "items-center text-center"
            ):
                ui.label(valeur).classes(f"text-3xl font-black {txt_cls}")
                ui.label(label).classes("text-[11px] text-slate-400 uppercase tracking-wider")

        with ui.row().classes("w-full items-center gap-2 mb-4 text-[10px] text-slate-500"):
            ui.label("Légende gravité :").classes("font-bold text-slate-400")
            for n in ["1", "2", "3", "4"]:
                ui.badge(f"N{n}", color=gravite_styles(n)[1]).classes(
                    "text-[9px] font-mono"
                )

    if not crises:
        with ui.card().classes(
            "w-full bg-slate-800/40 border border-slate-700 p-8 text-center"
        ):
            ui.label(
                "Aucune cellule de crise en cours. Le PCO est en veille normale."
            ).classes("text-slate-400 italic text-base")
        return

    # ------------------------------------------------------------------
    # Cartes de suivi PCO (une par cellule)
    # ------------------------------------------------------------------
    chronos: list[dict] = []
    suivis_refs: list[dict] = []

    for crise in crises:
        c_id = crise.get("id")
        c_code = crise.get("code_crise", "CRISE")
        c_titre = crise.get("titre", "Sans titre")
        c_type = crise.get("type_crise", "SURETE")
        c_gravite = str(crise.get("niveau_gravite", "2")).replace("N", "")
        c_statut = crise.get("statut", "EN_SOMMEIL")
        c_lieu = crise.get("lieu_pc") or "PC non défini"

        suivi = await asyncio.to_thread(_charger_suivi_cellule, c_id)

        dt_activation = _parse_dt(crise.get("activated_at")) or _parse_dt(
            crise.get("created_at")
        )
        dernier_sitrep = suivi.get("dernier_sitrep")

        card_bg = (
            "bg-amber-950/20 border-amber-800/60"
            if c_statut == "EN_SOMMEIL"
            else "bg-red-950/30 border-red-800/80"
        )

        crise_site_id = str(crise.get("site_impacte_id") or "")
        is_focus = bool(focus_site_id) and crise_site_id == focus_site_id
        card_classes = f"w-full {card_bg} border p-5 shadow-lg mb-4 gap-3"
        if is_focus:
            card_classes += " crise-focus-ring"
        with ui.card().classes(card_classes) as crise_card:
            # Ancre pour le branchement direct depuis la carte site du cockpit.
            crise_card.props(f'data-crise-site="{crise_site_id}"')
            with ui.row().classes("justify-between items-start w-full flex-wrap gap-2"):
                with ui.column().classes("gap-1"):
                    with ui.row().classes("items-center gap-3 flex-wrap"):
                        ui.badge(
                            c_code,
                            color=("amber-9" if c_statut == "EN_SOMMEIL" else "red"),
                        ).classes("font-mono font-bold")
                        ui.label(c_titre).classes(
                            "text-xl font-bold text-slate-100"
                        )
                        ui.badge(
                            f"Gravité {c_gravite}", color=gravite_styles(c_gravite)[1]
                        ).classes("font-bold")
                        ui.badge(c_type, color="grey-8").classes("text-[10px]")
                        site_lie = sites_map.get(str(crise.get("site_impacte_id") or ""))
                        if site_lie:
                            ui.badge(f"🏢 {site_lie}", color="blue-9").classes(
                                "font-bold text-[10px]"
                            ).tooltip(f"Crise de niveau site — rattachée à {site_lie}")
                        else:
                            ui.badge("🌍 Nationale", color="grey-8").classes(
                                "text-[10px]"
                            ).tooltip("Crise nationale — aucun site rattaché")
                        if c_statut == "EN_SOMMEIL":
                            ui.badge("EN SOMMEIL", color="warning").classes(
                                "font-bold animate-pulse"
                            )
                        else:
                            ui.badge("ACTIVÉE", color="negative").classes(
                                "font-bold animate-pulse"
                            )

                    ui.label(
                        f"Lieu : {c_lieu} | Déclenchée par : {crise.get('declenchee_par', 'SG')}"
                    ).classes("text-xs text-slate-400")

                with ui.column().classes("items-end gap-1"):
                    chrono_label = ui.label(
                        _chrono_depuis(dt_activation)
                    ).classes("text-2xl font-mono font-black text-slate-100")
                    ui.label("chronomètre depuis activation").classes(
                        "text-[10px] text-slate-400"
                    )
                    chronos.append({"depart": dt_activation, "label": chrono_label})

            # Indicateurs de suivi (références conservées pour le
            # rafraîchissement périodique sans rechargement de la page)
            with ui.row().classes("w-full gap-3 mt-1 flex-wrap"):
                with ui.card().classes("flex-1 min-w-[150px] bg-slate-900/60 border border-slate-800 p-2"):
                    ui.label("Directeur de crise").classes(
                        "text-[10px] text-slate-400 uppercase tracking-wider"
                    )
                    suivi_directeur_label = ui.label(
                        suivi.get("directeur") or "Non désigné"
                    ).classes("text-sm font-bold text-slate-100")
                with ui.card().classes("flex-1 min-w-[110px] bg-slate-900/60 border border-slate-800 p-2"):
                    ui.label("Membres de cellule").classes(
                        "text-[10px] text-slate-400 uppercase tracking-wider"
                    )
                    suivi_membres_label = ui.label(str(suivi.get("nb_membres", 0))).classes(
                        "text-sm font-bold text-slate-100"
                    )
                with ui.card().classes("flex-1 min-w-[110px] bg-slate-900/60 border border-slate-800 p-2"):
                    ui.label("Événements consignés").classes(
                        "text-[10px] text-slate-400 uppercase tracking-wider"
                    )
                    suivi_evt_label = ui.label(str(suivi.get("nb_evt", 0))).classes(
                        "text-sm font-bold text-slate-100"
                    )
                with ui.card().classes("flex-1 min-w-[140px] bg-slate-900/60 border border-slate-800 p-2"):
                    ui.label("Événements depuis dernier SITREP").classes(
                        "text-[10px] text-slate-400 uppercase tracking-wider"
                    )
                    suivi_evt_sitrep_label = ui.label(str(suivi.get("nb_evt_apres_sitrep", 0))).classes(
                        "text-sm font-bold "
                        + ("text-amber-400" if suivi.get("nb_evt_apres_sitrep", 0) else "text-slate-100")
                    )
                with ui.card().classes("flex-1 min-w-[170px] bg-slate-900/60 border border-slate-800 p-2"):
                    ui.label("Dernier SITREP").classes(
                        "text-[10px] text-slate-400 uppercase tracking-wider"
                    )
                    suivi_sitrep_label = ui.label(
                        _fmt_dernier_sitrep(dernier_sitrep)
                    ).classes(
                        "text-sm font-bold "
                        + ("text-blue-300" if dernier_sitrep else "text-slate-400")
                    )
            suivis_refs.append(
                {
                    "id": c_id,
                    "directeur": suivi_directeur_label,
                    "membres": suivi_membres_label,
                    "evt": suivi_evt_label,
                    "evt_apres": suivi_evt_sitrep_label,
                    "sitrep": suivi_sitrep_label,
                }
            )

            with ui.row().classes("w-full justify-end items-center gap-2 flex-wrap"):
                if is_sg_admin:
                    if c_statut == "EN_SOMMEIL":
                        ui.button(
                            "ACTIVATION & ALERTER",
                            icon="notifications_active",
                            on_click=lambda c=crise: activer_et_notifier_crise(
                                c.get("id"),
                                c.get("code_crise"),
                                c.get("titre"),
                                _DialogStub(),
                            ),
                        ).props("color=red font-bold sm animate-pulse")
                    ui.button(
                        icon="manage_accounts",
                        on_click=lambda c=crise: open_edit_crise_dialog(c),
                    ).props("flat color=slate-400 sm").tooltip("Gérer la cellule")

                ui.button(
                    "Main Courante",
                    icon="assignment",
                    on_click=lambda c=crise: open_main_courante_dialog(c),
                ).props("color=red sm font-bold")

                ui.button(
                    icon="attach_file",
                    on_click=lambda c=crise: open_fichiers_crise_dialog(c),
                ).props("color=blue sm font-bold").tooltip("Pièces jointes de la crise")

                ui.button(
                    "SITREP",
                    icon="description",
                    on_click=lambda c=crise: open_sitrep_dialog(c),
                ).props("color=blue sm font-bold")

                ui.button(
                    "🌙 Fin de journée",
                    icon="nightlight_round",
                    on_click=lambda c=crise: open_fin_de_journee_dialog(c),
                ).props("color=indigo sm")

            if crise.get("description"):
                ui.label(crise["description"]).classes(
                    "text-sm text-slate-300 mt-1 bg-slate-900/40 p-3 rounded "
                    "border border-slate-800"
                )

    # Horloge PCO : mise à jour des chronomètres de toutes les cellules.
    def tick_chronos():
        for c in chronos:
            c["label"].set_text(_chrono_depuis(c["depart"]))

    ui.timer(1.0, tick_chronos)

    # Indicateurs de suivi : rafraîchissement périodique sans recharger la
    # page (les événements consignés apparaissent d'eux-mêmes sur les cartes).
    async def refresh_suivis():
        for ref in suivis_refs:
            suivi = await asyncio.to_thread(_charger_suivi_cellule, ref["id"])
            ref["directeur"].set_text(suivi.get("directeur") or "Non désigné")
            ref["membres"].set_text(str(suivi.get("nb_membres", 0)))
            ref["evt"].set_text(str(suivi.get("nb_evt", 0)))
            nb_apres = suivi.get("nb_evt_apres_sitrep", 0)
            ref["evt_apres"].set_text(str(nb_apres))
            ref["evt_apres"].classes(
                replace=f"text-sm font-bold "
                + ("text-amber-400" if nb_apres else "text-slate-100")
            )
            dernier = suivi.get("dernier_sitrep")
            ref["sitrep"].set_text(_fmt_dernier_sitrep(dernier))
            ref["sitrep"].classes(
                replace="text-sm font-bold "
                + ("text-blue-300" if dernier else "text-slate-400")
            )

    ui.timer(30.0, refresh_suivis)

    # ------------------------------------------------------------------
    # Chronologie consolidée du PCO (toutes cellules confondues)
    # ------------------------------------------------------------------
    ui.separator().classes("my-4 border-slate-700")
    with ui.row().classes("items-center gap-2"):
        ui.label("Chronologie consolidée des cellules").classes(
            "text-sm font-bold text-slate-200 uppercase tracking-wider"
        )
        ui.badge("Rafraîchissement auto 30s", color="slate-8").classes("text-[10px]")

    timeline_container = ui.column().classes(
        "w-full gap-2 bg-slate-950/60 border border-slate-800 p-3 rounded "
        "max-h-[320px] overflow-y-auto"
    )

    async def refresh_timeline():
        events = []
        for crise in crises:
            logs = await asyncio.to_thread(
                DatabaseService.get_main_courante_by_crise, crise.get("id")
            )
            for l in logs or []:
                events.append(
                    {
                        "code_crise": crise.get("code_crise", "CRISE"),
                        "categorie": str(l.get("categorie", "INFO")),
                        "priorite": str(l.get("niveau_priorite", "NORMALE")).upper(),
                        "description": str(l.get("description", "")),
                        "auteur": str(l.get("auteur", "")),
                        "horodatage": l.get("horodatage") or l.get("created_at"),
                    }
                )

        events.sort(
            key=lambda e: _parse_dt(e["horodatage"]) or datetime.min.replace(
                tzinfo=LOCAL_TZ
            ),
            reverse=True,
        )

        timeline_container.clear()
        with timeline_container:
            if not events:
                ui.label("Aucun événement consigné sur les cellules en cours.").classes(
                    "text-slate-500 italic text-xs p-2"
                )
                return

            for e in events[:15]:
                dt_evt = _parse_dt(e["horodatage"])
                prio_color = (
                    "red" if e["priorite"] == "CRITIQUE"
                    else ("amber" if e["priorite"] == "URGENT" else "slate-7")
                )
                with ui.row().classes(
                    "w-full items-center gap-2 bg-slate-800/70 border "
                    "border-slate-700 p-2 rounded text-xs flex-none"
                ):
                    ui.label(
                        dt_evt.astimezone(LOCAL_TZ).strftime("%H:%M")
                        if dt_evt
                        else "--:--"
                    ).classes("font-mono font-bold text-slate-300 w-10")
                    ui.badge(e["code_crise"], color="red-9").classes(
                        "font-mono text-[10px]"
                    )
                    ui.badge(e["categorie"], color="grey-8").classes("text-[10px]")
                    ui.badge(e["priorite"], color=prio_color).classes("text-[10px]")
                    ui.label(e["description"]).classes(
                        "text-slate-200 flex-grow truncate"
                    ).tooltip(e["description"])
                    ui.label(e["auteur"]).classes(
                        "text-slate-400 font-bold whitespace-nowrap"
                    )

    await refresh_timeline()
    ui.timer(30.0, refresh_timeline)
