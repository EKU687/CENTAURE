"""Test simulation : écran mural /wall avec alerte sonore S4 (lecture seule).

Scénario 1 : /wall?token=<jeton DINUM réel> — page construite (titre,
horloge, tuiles S/T).

Scénario 2 : DatabaseService.get_all_sites stubé avec un site en S4 —
la bannière « ALERTE S4 — CONFINEMENT » apparaît avec le code du site ;
cliquer sur ACQUITTER masque la bannière (état python, le son dépend
du navigateur réel).

Sortie : TEST_WALL_OK / TEST_WALL_ECHEC.
"""
import asyncio

import httpx

from nicegui import core, ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

import app.services.database_service as db  # noqa: E402
from app.models.site import SiteCritique  # noqa: E402

JETON_DINUM = "c7c18717-1611-4ee2-a3e0-fb7192bcec0b"


def new_user() -> User:
    return User(
        httpx.AsyncClient(
            transport=httpx.ASGITransport(core.app), base_url="http://test"
        )
    )


async def attendre_tuiles(user: User, timeout: float = 40.0):
    pas = 0.2
    for _ in range(int(timeout / pas)):
        cartes = [
            el
            for el in user.client.elements.values()
            if isinstance(el, ui.card) and not el.is_deleted
        ]
        if len(cartes) >= 4:  # au moins 4 sites suivis
            return cartes
        await asyncio.sleep(pas)
    return []


async def scenario_site_reel() -> bool:
    user = new_user()
    await user.open(f"/wall?token={JETON_DINUM}")
    titre_present = any(
        "ÉCRAN DE SUPERVISION GLOBALE" in (getattr(el, "text", "") or "")
        for el in user.client.elements.values()
        if isinstance(el, ui.label)
    )
    cartes = await attendre_tuiles(user)
    print(f"[Site réel] Titre présent : {titre_present} | tuiles : {len(cartes)}")
    return titre_present and len(cartes) >= 4


async def scenario_s4() -> bool:
    sites_faux = [
        SiteCritique(
            code_site="TEST-S4",
            nom="Site test confinement",
            surete_niveau="S4",
            technique_niveau="T1",
            localisation="Nouméa",
        ),
        SiteCritique(
            code_site="TEST-OK",
            nom="Site test nominal",
            surete_niveau="S1",
            technique_niveau="T1",
            localisation="Nouméa",
        ),
    ]
    db.DatabaseService.get_all_sites = staticmethod(lambda: list(sites_faux))
    try:
        user = new_user()
        await user.open(f"/wall?token={JETON_DINUM}")

        banniere = None
        for _ in range(100):  # attend le rendu de la bannière
            banniere = next(
                (
                    el
                    for el in user.client.elements.values()
                    if isinstance(el, ui.label)
                    and "ALERTE S4 — CONFINEMENT" in (getattr(el, "text", "") or "")
                    and not el.is_deleted
                ),
                None,
            )
            if banniere:
                break
            await asyncio.sleep(0.2)
        site_dans_banniere = any(
            isinstance(el, ui.label)
            and getattr(el, "text", "") == "TEST-S4"
            for el in user.client.elements.values()
        )
        print(f"[S4] Bannière : {banniere is not None} | site listé : {site_dans_banniere}")
        if not (banniere and site_dans_banniere):
            return False

        user.find("ACQUITTER").click()
        await asyncio.sleep(1.0)
        restant = next(
            (
                el
                for el in user.client.elements.values()
                if isinstance(el, ui.label)
                and "ALERTE S4 — CONFINEMENT" in (getattr(el, "text", "") or "")
                and not el.is_deleted
            ),
            None,
        )
        print(f"[S4] Bannière après acquittement : {'encore visible' if restant else 'masquée'}")
        return restant is None
    finally:
        import importlib

        importlib.reload(db)


async def main():
    async with user_simulation():
        import main  # noqa: F401 - enregistre les routes

        ok1 = await scenario_site_reel()
        ok2 = await scenario_s4()
        print("TEST_WALL_OK" if ok1 and ok2 else "TEST_WALL_ECHEC")


asyncio.run(main())
