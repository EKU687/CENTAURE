import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    APP_NAME: str = "CENTAURE"
    APP_VERSION: str = "0.1.0"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev_secret_key_change_in_prod")

settings = Settings()