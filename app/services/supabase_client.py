import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Chargement du fichier .env local (s'il existe)
load_dotenv()

# Récupération et nettoyage strict des variables d'environnement système (Fly.io / Docker / Local)
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip().strip('"').strip("'")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "").strip().strip('"').strip("'")

# Validation de la présence des identifiants au démarrage
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "⚠️ Configuration Supabase introuvable ! "
        "Vérifie que SUPABASE_URL et SUPABASE_KEY sont correctement définis."
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
