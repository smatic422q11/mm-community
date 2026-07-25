import os
from dotenv import load_dotenv

# Lädt die Variablen aus der .env Datei
load_dotenv()

# Definiert den Schlüssel, damit der Translator ihn finden kann
DEEPL_KEY = os.getenv("DEEPL_API_KEY")

class ConfigService:
    def __init__(self):
        self.deepl_key = DEEPL_KEY

config_service = ConfigService()