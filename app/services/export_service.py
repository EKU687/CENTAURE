# app/services/export_service.py
import csv
import io
from typing import List, Dict, Any


class ExportService:
    @staticmethod
    def exporter_csv_main_courante(logs: List[Dict[str, Any]]) -> bytes:
        """Génère un buffer d'octets CSV encodé en UTF-8-SIG (compatible Excel)."""
        output = io.StringIO()
        fieldnames = ["horodatage", "categorie", "auteur", "message"]

        writer = csv.DictWriter(
            output, fieldnames=fieldnames, extrasaction="ignore", delimiter=";"
        )
        writer.writeheader()
        for log in logs:
            writer.writerow(log)

        return output.getvalue().encode("utf-8-sig")
