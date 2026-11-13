"""Test simulation : routing par rôle après connexion (lecture seule BDD).

Pour chaque rôle RBAC, simule une connexion via le vrai écran de login
(authentification stubée — aucun identifiant réel requis) et vérifie
l'onglet actif à l'arrivée dans le cockpit :

- ADMIN / SUPERVISEUR_SG / OPERATEUR_SG => Hypervision des Sites Sensibles
- CRISE_SG / CELLULE_CRISE             => Cellules de Crise (jamais les sites)

Sortie : TEST_ROUTING_OK / TEST_ROUTING_ECHEC.
"""
import asyncio

import httpx

from nicegui import core, ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

import app.services.database_service as db  # noqa: E402

ROLES_SITES = {"ADMIN", "SUPERVISEUR_SG", "OPERATEUR_SG"}
ROLES_CRISES = {"CRISE_SG", "CELLULE_CRISE"}


def new_user() -> User:
    return User(
        httpx.AsyncClient(
            transport=httpx.ASGITransport(core.app), base_url="http://test"
        )
    )


async def attendre_onglets(user: User, timeout: float = 40.0):
    """Attend que le cockpit soit construit (premier tab_panels formé)."""
    pas = 0.1
    for _ in range(int(timeout / pas)):
        panels = [
            el
            for el in user.client.elements.values()
            if isinstance(el, ui.tab_panels)
        ]
        if panels:
            return panels[0]
        await asyncio.sleep(pas)
    return None


async def scenario(role: str) -> str | None:
    db.DatabaseService.authenticate_user = staticmethod(
        lambda username, password: {
            "id": "test-id",
            "username": username,
            "nom_complet": f"Test {role}",
            "role": role,
        }
    )
    user = new_user()
    await user.open("/login")

    inputs = {
        el.props.get("label"): el
        for el in user.client.elements.values()
        if isinstance(el, ui.input) and el.props.get("label")
    }
    inputs["Identifiant SG"].value = f"user_{role}"
    inputs["Mot de passe"].value = "motdepasse"

    user.find("SE CONNECTER").click()

    panels = await attendre_onglets(user)
    if panels is None:
        print(f"[{role}] ECHEC : cockpit non construit dans le délai")
        return None

    onglets_visibles = [
        el.props.get("name")
        for el in user.client.elements.values()
        if isinstance(el, ui.tab) and not el.is_deleted
    ]
    actif = panels.value
    actif_nom = (
        actif.props.get("name", str(actif))
        if isinstance(actif, ui.tab)
        else str(actif)
    )
    print(f"[{role}] onglets visibles={onglets_visibles} | actif={actif_nom!r}")
    return actif_nom


async def main():
    resultats = {}
    async with user_simulation():
        import main  # noqa: F401 - enregistre les routes /, /login, /kiosk, /site

        for role in [*sorted(ROLES_SITES), *sorted(ROLES_CRISES)]:
            resultats[role] = await scenario(role)

    ok = True
    for role, actif in resultats.items():
        est_sites = isinstance(actif, str) and "Sites" in actif
        est_crises = isinstance(actif, str) and "Crise" in actif
        attendu_sites = role in ROLES_SITES
        conforme = est_sites if attendu_sites else est_crises
        print(f"  {role}: {'OK' if conforme else 'ECHEC'} (actif={actif!r})")
        ok = ok and conforme
    print("TEST_ROUTING_OK" if ok else "TEST_ROUTING_ECHEC")


asyncio.run(main())
