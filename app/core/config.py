# =========================================================================
# APPLICATION CONFIGURATION & VERSIONING (config.py)
# Projet CENTAURE - Gouvernement de la Nouvelle-Calédonie
# =========================================================================

import os

# 🎯 Semantic Versioning (SemVer) : MAJOR.MINOR.PATCH
APP_VERSION = "1.0.0"
APP_DATE = "30/09/2026"
APP_ENV = "PRODUCTION"  # "BETA" ou "PRODUCTION"

APP_NAME = "CENTAURE"
APP_SUBTITLE = "Hypervision & Gestion de crises"
APP_AUTHOR = "Éric KUTER"

# Dynamic display string for UI Headers
DISPLAY_VERSION = (
    f"v{APP_VERSION}" if APP_ENV == "PRODUCTION" else f"v{APP_VERSION}-{APP_ENV}"
)

# Supabase & Application Settings
SECRET_KEY = os.getenv("SECRET_KEY", "centaure_secret_key_prod_2026")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
