import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Chargement des variables du fichier .env
load_dotenv()

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "⚠️ Configuration Supabase introuvable ! "
        "Vérifie que SUPABASE_URL et SUPABASE_KEY sont correctement définis dans ton fichier .env."
    )

# Instanciation globale du client Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def test_connection() -> bool:
    """Vérifie la joignabilité de l'API Supabase."""
    try:
        # Interrogation basique de l'API Supabase
        supabase.auth.get_session()
        print("✅ Connexion à Supabase établie avec succès !")
        return True
    except Exception as e:
        print(f"❌ Erreur de connexion à Supabase : {e}")
        return False


if __name__ == "__main__":
    test_connection()
