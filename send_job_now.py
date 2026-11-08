import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from tools.email_manager import EmailManager

def send_job_documents():
    em = EmailManager()
    subject = "📄 Deine Bewerbungsunterlagen & Lebenslauf (Goran Petrovic)"
    body = (
        "Hallo Goran,\n\n"
        "hier sind deine angeforderten Bewerbungsunterlagen für deine Jobsuche:\n\n"
        "=======================================================\n"
        "1. BEWERBUNGSSCHREIBEN (Fullstack Software Entwickler)\n"
        "=======================================================\n"
        "Goran Petrovic\n"
        "Wien, Österreich\n"
        "E-Mail: mmcommunity22@gmail.com\n\n"
        "AN DIE PERSONALABTEILUNG\n\n"
        "BEWERBUNG ALS FULLSTACK DEVELOPER / SOFTWARE ENTWICKLER (m/w/d)\n\n"
        "Sehr geehrte Damen und Herren,\n\n"
        "hiermit bewerbe ich mich als erfahrener Software-Entwickler und Gründer der M&M Community.\n"
        "Ich besitze fundierte Erfahrung in der Entwicklung modularer Web-Plattformen, REST APIs, Python Backend-Systemen und automatisierter KI-Architekturen.\n\n"
        "Meine Schwerpunkte:\n"
        "- Python (Flask, REST APIs, Automation Services)\n"
        "- JavaScript, HTML5/CSS3 (Live UI/UX, WebSockets)\n"
        "- System-Architektur & Autonome KI-Agenten (Jarvis OS)\n\n"
        "Ich freue mich über ein persönliches Kennenlernen.\n\n"
        "Mit freundlichen Grüßen,\n"
        "Goran Petrovic\n\n\n"
        "=======================================================\n"
        "2. LEBENSLAUF // GORAN PETROVIC\n"
        "=======================================================\n"
        "PERSÖNLICHE DATEN:\n"
        "Name: Goran Petrovic\n"
        "Geburtsdatum: 11.11.1981\n"
        "Wohnort: Wien, Österreich\n"
        "E-Mail: mmcommunity22@gmail.com / info@mm-community.online\n\n"
        "BERUFLICHES PROFIL:\n"
        "- Founder & Lead Developer: M&M Community (Modulare Themen- & Live-Plattform)\n"
        "- System-Architektur & KI-Entwicklung (Jarvis OS)\n\n"
        "SKILLS & TECHNOLOGIEN:\n"
        "- Python, Flask, REST & WebSocket APIs\n"
        "- JavaScript, Frontend Architecture\n"
        "- Git, Google Cloud APIs, Automation Tools\n\n"
        "SPRACHEN:\n"
        "- Deutsch (Verhandlungssicher)\n"
        "- Englisch (Gut)\n\n"
        "=======================================================\n\n"
        "Deine Bewerbungsunterlagen stehen dir ab sofort mobil auf deinem Smartphone zur Verfügung!\n\n"
        "Beste Grüße,\n"
        "Dein J.A.R.V.I.S."
    )
    res = em.send_email("admin", "mmcommunity22@gmail.com", subject, body)
    print(f"[SendJobResult]: {res}")

if __name__ == "__main__":
    send_job_documents()
