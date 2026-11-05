import os
import logging
from dotenv import load_dotenv
from supabase import create_client, Client, ClientOptions

logger = logging.getLogger(__name__)

# Chargement du fichier .env local (s'il existe)
load_dotenv()

# Récupération et nettoyage strict des variables d'environnement
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip().strip('"').strip("'")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "").strip().strip('"').strip("'")

# Validation de la présence des identifiants au démarrage
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "⚠️ Configuration Supabase introuvable ! "
        "Vérifie que SUPABASE_URL et SUPABASE_KEY sont correctement définis."
    )


def _build_supabase_client() -> Client:
    """Instancie un client Supabase avec options de résilience HTTP."""
    options = ClientOptions(
        postgrest_client_timeout=15,
        storage_client_timeout=15,
    )
    return create_client(SUPABASE_URL, SUPABASE_KEY, options=options)


# Instance courante
_supabase_instance: Client = _build_supabase_client()


def get_supabase() -> Client:
    """Retourne l'instance client Supabase active."""
    global _supabase_instance
    return _supabase_instance


def reset_supabase_client() -> Client:
    """Recrée une nouvelle session HTTP/2 si la précédente a été coupée."""
    global _supabase_instance
    logger.warning("🔄 Réinitialisation de la session Supabase...")
    _supabase_instance = _build_supabase_client()
    return _supabase_instance


# Proxy de compatibilité pour le code existant important directement `supabase`
class SupabaseProxy:
    def __getattr__(self, name):
        return getattr(get_supabase(), name)


supabase: Client = SupabaseProxy()


def test_connection() -> bool:
    """Vérifie la joignabilité de l'API Supabase."""
    try:
        supabase.auth.get_session()
        print("✅ Connexion à Supabase établie avec succès !")
        return True
    except Exception as e:
        print(f"❌ Erreur de connexion à Supabase : {e}")
        return False


if __name__ == "__main__":
    test_connection()
