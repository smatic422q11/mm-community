import os
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()

try:
    import certifi
    from pymongo import MongoClient
    from pymongo.server_api import ServerApi
except Exception:  # pragma: no cover
    certifi = None
    MongoClient = None
    ServerApi = None


class DatabaseService:
    """Zentrale, robuste Datenbank-Abstraktion für die Community."""

    def __init__(self) -> None:
        self.client: Optional[Any] = None
        self.db: Optional[Any] = None
        self.connected = False
        self.error: Optional[str] = None
        self._initialize()

    def _initialize(self) -> None:
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            self.error = "MONGO_URI ist nicht gesetzt."
            print("[-] database.py: MONGO_URI ist nicht gesetzt.")
            return

        if MongoClient is None or ServerApi is None or certifi is None:
            self.error = "pymongo oder certifi ist nicht verfügbar."
            print("[-] database.py: pymongo/certifi ist nicht verfügbar.")
            return

        try:
            ca_file = certifi.where()
            self.client = MongoClient(
                mongo_uri,
                server_api=ServerApi("1"),
                tlsCAFile=ca_file,
                serverSelectionTimeoutMS=5000,
            )
            self.client.admin.command("ping")
            self.db = self.client["mm-community"]
            self.connected = True
            print("[+] database.py: MongoDB-Verbindung erfolgreich.")
        except Exception as exc:
            self.error = str(exc)
            self.client = None
            self.db = None
            self.connected = False
            print(f"[-] database.py: MongoDB-Verbindung fehlgeschlagen: {exc}")

    def get_db(self) -> Optional[Any]:
        return self.db

    def is_connected(self) -> bool:
        return self.connected

    def get_collection(self, name: str) -> Optional[Any]:
        if self.db is None:
            raise RuntimeError("Datenbank ist nicht initialisiert.")
        return self.db[name]


database_service = DatabaseService()
db = database_service.get_db()

# --- Die einzige Ergänzung, damit die anderen Dateien nicht crashen ---
def _get_db():
    return database_service.get_db()