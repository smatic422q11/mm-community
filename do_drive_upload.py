import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from tools.google_agent import GoogleAgent
from tools.email_manager import EmailManager
from googleapiclient.http import MediaFileUpload

def upload_and_email():
    print("[DriveTest] Starte Google Drive Upload & E-Mail Versand...")
    agent = GoogleAgent()
    service = agent.get_service('drive', 'v3')
    folder_id = '1rR7yCKptukZ4JUP5xWt-xiknqu44vs2x'

    # 1. Dateien erstellen
    p1 = Path(r'C:\Users\Benutzername\Desktop\Jarvis\Bewerbung_Goran_Petrovic.txt')
    p1.write_text(
        "Goran Petrovic\nWien, Österreich\nE-Mail: mmcommunity22@gmail.com\n\n"
        "BEWERBUNG ALS SOFTWARE ENTWICKLER / FULLSTACK DEVELOPER\n\n"
        "Sehr geehrte Damen und Herren,\n\n"
        "hiermit bewerbe ich mich als erfahrener Software-Entwickler und Gründer der M&M Community.\n"
        "Ich besitze fundierte Erfahrung in der Entwicklung modularer Web-Plattformen, REST APIs,\n"
        "Python Backend-Systemen und automatisierter KI-Architekturen.\n\n"
        "Mit freundlichen Grüßen,\nGoran Petrovic",
        encoding='utf-8'
    )

    p2 = Path(r'C:\Users\Benutzername\Desktop\Jarvis\Lebenslauf_Goran_Petrovic.txt')
    p2.write_text(
        "LEBENSLAUF // GORAN PETROVIC\n\n"
        "Name: Goran Petrovic\nGeburtsdatum: 11.11.1981\nWohnort: Wien, Österreich\n"
        "E-Mail: mmcommunity22@gmail.com\n\n"
        "PROFIL & EXPERIENCE:\n- Founder & Lead Developer: M&M Community\n"
        "- Fullstack Software Architecture & AI Automation\n\n"
        "SKILLS:\n- Python, Flask, JavaScript, REST APIs, WebSockets\n- System Automation & AI Agents",
        encoding='utf-8'
    )

    uploaded_links = []
    for file_path in [p1, p2]:
        meta = {'name': file_path.name, 'parents': [folder_id]}
        media = MediaFileUpload(str(file_path), resumable=True)
        res = service.files().create(body=meta, media_body=media, fields='id, name, webViewLink').execute()
        file_id = res.get('id')
        link = res.get('webViewLink')
        print(f"[DriveTest] Datei hochgeladen: {file_path.name} -> ID: {file_id} | Link: {link}")
        uploaded_links.append((file_path.name, link))

    # 2. E-Mail senden
    em = EmailManager()
    body = (
        "Hallo Goran,\n\n"
        "deine Freigabe des Google Drive Ordners 'Jarvis' hat zu 100 % funktioniert!\n\n"
        "Ich habe folgende zwei Unterlagen direkt in deinen Google Drive Ordner hochgeladen:\n\n"
        f"1. {uploaded_links[0][0]}\nLink: {uploaded_links[0][1]}\n\n"
        f"2. {uploaded_links[1][0]}\nLink: {uploaded_links[1][1]}\n\n"
        "Der mobile E-Mail- & Google-Drive-Workflow ist ab sofort voll einsatzbereit!\n\n"
        "Beste Grüße,\nDein J.A.R.V.I.S."
    )
    email_res = em.send_email('admin', 'mmcommunity22@gmail.com', '🚀 Google Drive Upload Erfolgreich!', body)
    print(f"[DriveTest] E-Mail Ergebnis: {email_res}")

if __name__ == "__main__":
    upload_and_email()
