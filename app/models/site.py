from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class AnomalieTechnique(BaseModel):
    id: Optional[str] = None
    site_id: str
    domaine: str
    equipement: str
    description: Optional[str] = None
    statut: str = "ACTIF"
    created_at: Optional[datetime] = None


class SiteCritique(BaseModel):
    id: Optional[str] = None
    code_site: str
    nom: str
    surete_niveau: str = "S1"
    technique_niveau: str = "T1"
    localisation: Optional[str] = None
    protocole_confinement: Optional[str] = None
    updated_at: Optional[datetime] = None
    anomalies: List[AnomalieTechnique] = []

    @property
    def est_en_confinement(self) -> bool:
        return self.surete_niveau == "S4"
