from pydantic import BaseModel, Field
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

class RegisterModell(BaseModel):
    real_name: str = Field(..., min_length=3, description="Echter Vor- und Nachname")
    email: EmailStr  
    passwort: str = Field(..., min_length=6, description="Mindestens 6 Zeichen")
    agb_akzeptiert: bool = Field(False, description="Nutzer muss die AGB akzeptieren") # <--- WICHTIG: Kein '...' (Pflicht), sondern ein Standardwert!
    
# 1. Der versiegelte Träger für ein Thema / Sektor
# Das blockiert ungültige Daten und zwingt das System zur Ordnung.
class ThemaSchema(BaseModel):
    id: Optional[str] = Field(None, alias="_id")  # MongoDB ID als sauberer String
    titel: str
    sektor_nummer: int = Field(..., ge=1, le=20)  # Schützt vor Fehlern: Erlaubt exakt Sektor 1 bis 20!
    aktiv: bool = True

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

# 2. Die Ressourcenumwandlung für MongoDB-Daten
def wandle_mongo_daten_um(mongo_dokument: dict) -> dict:
    """
    Nimmt ein rohes Dokument aus der MongoDB, 
    wandelt die _id in einen String um und jagt es durch den Träger.
    """
    if not mongo_dokument:
        return {}
    
    if "_id" in mongo_dokument:
        mongo_dokument["_id"] = str(mongo_dokument["_id"])
    
    # Durch den Pydantic-Träger jagen (Validierung)
    gesichert = ThemaSchema(**mongo_dokument)
    
    # Als sauberes Dictionary zurückgeben
    return gesichert.model_dump(by_alias=True)