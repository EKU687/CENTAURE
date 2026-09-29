from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CriseStrategique(BaseModel):
    id: Optional[str] = None
    code_crise: str  # ex: 'CRISE-2026-IRAN-NC'
    titre: str
    type_crise: str  # 'GEOPOLITIQUE', 'SOCIALE', 'CYCLONE', 'INFRASTRUCTURE'
    niveau_gravite: str = "N1"  # N1 (Suivi), N2 (Cellule Activée), N3 (Majeure)
    statut: str = "ACTIVEE"  # 'VEILLE', 'ACTIVEE', 'CLOTUREE'
    declenchee_par: str = "SG"
    site_impacte_id: Optional[str] = None  # None si crise macro / non liée à un site
    description: Optional[str] = None
    created_at: Optional[datetime] = None
