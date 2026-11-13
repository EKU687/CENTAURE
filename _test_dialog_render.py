"""Reproduction locale v5 : parcours correct de l'arbre via slots/default_slot."""
import asyncio
from nicegui import Client
from app.services.database_service import DatabaseService
from app.ui.crises.main_courante_dialog import open_main_courante_dialog


def walk(el, depth=0, out=None):
    """Parcours récursif via les slots déclarés de l'élément."""
    from nicegui.slot import Slot
    out = out if out is not None else []
    out.append((depth, el))
    slots = getattr(el, "slots", None) or {}
    for name, slot in slots.items():
        if isinstance(slot, Slot):
            contenu = getattr(slot, "elements", None) or getattr(slot, "_elements", None)
            if contenu is None:
                contenu = getattr(slot, "children", None) or []
            for child in contenu:
                walk(child, depth + 1, out)
    return out


async def main():
    crises = DatabaseService.get_active_crises()
    crise = crises[0]

    with Client(page="/_test_mc") as client:
        await open_main_courante_dialog(crise)

        dialog = next(e for e in client.elements.values() if e.__class__.__name__ == "Dialog")
        journal = next(e for e in client.elements.values()
                       if e.__class__.__name__ == "Column" and "bg-slate-950/60" in str(getattr(e, "_classes", "")))

        # Slot attributes introspection
        from nicegui.slot import Slot
        print("attrs Slot:", [a for a in dir(Slot) if not a.startswith("__")][:20])

        # Le conteneur journal est-il dans le dialogue ?
        arb = walk(dialog)
        ids = {id(e) for _, e in arb}
        print("journal dans l'arbre du dialogue ?", id(journal) in ids)

        # Où sont les cartes d'événements ?
        labels = [(d, e) for d, e in walk(next(iter([e for e in client.elements.values()
                       if e.__class__.__name__ == "Page"]), None))
                  if "4eme essai" in str(getattr(e, "text", "") or "")]
        print("labels '4eme essai' repérés dans l'arbre PAGE:", len(labels))

        # enfants du slot du conteneur journal
        jslots = getattr(journal, "slots", None) or {}
        print("slots du journal:", {k: (getattr(v, "elements", None) or getattr(v, "_elements", None) or getattr(v, "children", None)) for k, v in jslots.items()} if jslots else jslots)

        # compter les cartes (ui.card) dans l'arbre du dialogue
        cards_arb = [e for _, e in arb if e.__class__.__name__ == "Card"]
        print("nb Card dans l'arbre dialogue:", len(cards_arb))


asyncio.run(main())
