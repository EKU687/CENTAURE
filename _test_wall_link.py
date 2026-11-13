"""Test simulation : bouton « Écran mural » du cockpit (ADMIN, BDD réelle).

Connexion ADMIN simulée -> page Sites -> clic sur « Écran mural » ->
le dialogue doit afficher une URL /wall?token=... copiable.
Sortie : TEST_WALL_LINK_OK / TEST_WALL_LINK_ECHEC.
"""
import asyncio

import httpx

from nicegui import core, ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

import app.services.database_service as db  # noqa: E402
from app.models.site import SiteCritique  # noqa: E402

JETON_FICTIF = "12345678-1234-1234-1234-123456789abc"


def stub_bdd():
    """Isoler le test du réseau Supabase (WinError 10035 en simulation Windows)."""
    db.DatabaseService.get_all_sites = staticmethod(
        lambda: [
            SiteCritique(
                code_site="DINUM",
                nom="Direction du Numérique",
                surete_niveau="S1",
                technique_niveau="T1",
            ),
            SiteCritique(
                code_site="DOUMER",
                nom="Immeuble Doumer",
                surete_niveau="S1",
                technique_niveau="T1",
            ),
        ]
    )
    db.DatabaseService.get_kiosk_url_for_site = staticmethod(
        lambda code_site, base_url=None: (
            f"http://localhost:8080/kiosk?token={JETON_FICTIF}"
        )
    )


def new_user() -> User:
    return User(
        httpx.AsyncClient(
            transport=httpx.ASGITransport(core.app), base_url="http://test"
        )
    )


async def main():
    ok_login = ok_bouton = ok_url = False
    stub_bdd()
    async with user_simulation():
        import main  # noqa: F401

        db.DatabaseService.authenticate_user = staticmethod(
            lambda u, p: {
                "id": "test-id",
                "username": u,
                "nom_complet": "Test ADMIN",
                "role": "ADMIN",
            }
        )
        user = new_user()
        await user.open("/login")
        inputs = {
            el.props.get("label"): el
            for el in user.client.elements.values()
            if isinstance(el, ui.input) and el.props.get("label")
        }
        inputs["Identifiant SG"].value = "admin"
        inputs["Mot de passe"].value = "x"
        user.find("SE CONNECTER").click()

        for _ in range(100):  # attend la construction du cockpit
            if any(
                isinstance(el, ui.tab_panels)
                for el in user.client.elements.values()
                if not el.is_deleted
            ):
                break
            await asyncio.sleep(0.2)

        bouton = next(
            (
                el
                for el in user.client.elements.values()
                if isinstance(el, ui.button)
                and getattr(el, "text", "") == "Écran mural"
                and not el.is_deleted
            ),
            None,
        )
        ok_login = bouton is not None
        print(f"[ADMIN] Cockpit chargé, bouton « Écran mural » visible : {ok_login}")
        if not bouton:
            print("TEST_WALL_LINK_ECHEC")
            return

        # clic via le mécanisme standard du plugin
        user.find("Écran mural").click()
        for _ in range(100):  # attend le dialogue
            champ = next(
                (
                    el
                    for el in user.client.elements.values()
                    if isinstance(el, ui.input)
                    and isinstance(el.value, str)
                    and "/wall?token=" in el.value
                    and not el.is_deleted
                ),
                None,
            )
            if champ:
                break
            await asyncio.sleep(0.2)
        ok_url = champ is not None
        if ok_url:
            print(f"[ADMIN] URL murale affichée : {champ.value[:60]}...")

        ok_bouton = ok_url and any(
            isinstance(el, ui.button)
            and getattr(el, "text", "") in ("COPIER", "OUVRIR L'ÉCRAN")
            for el in user.client.elements.values()
        )
        print("TEST_WALL_LINK_OK" if (ok_login and ok_url and ok_bouton) else "TEST_WALL_LINK_ECHEC")


asyncio.run(main())
