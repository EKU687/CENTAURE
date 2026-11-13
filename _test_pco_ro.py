"""Test fonctionnel PCO (lecture seule) contre la BDD réelle."""
from app.services.database_service import DatabaseService
from app.ui.crises.sitrep_dialog import SitrepService
from app.ui.crises.view import _charger_suivi_cellule, _chrono_depuis, _parse_dt

crises = DatabaseService.get_active_crises()
print(f"Cellules actives/veille : {len(crises)}")
for c in crises[:3]:
    print(" -", c.get("code_crise"), c.get("statut"), "activated_at:", c.get("activated_at"))

if crises:
    cid = crises[0]["id"]
    suivi = _charger_suivi_cellule(cid)
    print(
        f"Suivi {crises[0]['code_crise']}: membres={suivi['nb_membres']} "
        f"evt={suivi['nb_evt']} evt_apres_sitrep={suivi['nb_evt_apres_sitrep']} "
        f"directeur={suivi['directeur']}"
    )
    last = SitrepService.get_last_sitrep_by_crise(cid)
    print("Dernier SITREP:", {k: last.get(k) for k in ("numero_sitrep", "horodatage")} if last else None)
    chrono = _chrono_depuis(_parse_dt(crises[0].get("activated_at") or crises[0].get("created_at")))
    print("Chrono:", chrono)
    sum_fdj = SitrepService.generate_fin_de_journee_summary(cid)
    print("FDJ nb_evt_jour:", sum_fdj["nb_evt_jour"], "| synthèse pré-remplie (extraits):")
    print(sum_fdj["synthese_preremplie"][:300])
else:
    print("Aucune crise en base — test sur données vides OK.")

print("TEST_PCO_OK")
