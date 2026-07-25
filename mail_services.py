from __future__ import annotations

import os
import requests
from pathlib import Path
from dotenv import load_dotenv

# Lädt die Umgebungsvariablen einmalig sauber ein
load_dotenv(Path(__file__).resolve().parent / ".env")

class MailService:
    """Einfacher, direkter Mail-Service."""

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        if not to_email:
            return False
            
        API_TOKEN = os.getenv('MAILTRAP_API_TOKEN')
        ABSENDER_EMAIL = "info@mm-community.online" 
        
        if not API_TOKEN:
            print("!!! FEHLER: MAILTRAP_API_TOKEN fehlt in der .env !!!")
            return False
            
        url = "https://send.api.mailtrap.io/api/send"
        headers = {
            "Authorization": f"Bearer {API_TOKEN}", 
            "Content-Type": "application/json"
        }
        
        payload = {
            "from": {"email": ABSENDER_EMAIL, "name": "M&M Community"},
            "to": [{"email": to_email.strip()}],
            "subject": subject,
            "text": body
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            print(f"Mailtrap API Response: {response.status_code} - {response.text}")
            return response.status_code in [200, 201, 202]
        except Exception as e:
            print(f"Fehler beim Senden: {e}")
            return False

    def send_verification_email(self, to_email: str, code: str) -> bool:
        subject = "Dein Verifizierungscode"
        body = f"Dein Code für die M&M Community lautet: {code}"
        return self.send_email(to_email, subject, body)

    def send_email_with_attachment(
        self,
        to_email: str,
        subject: str,
        body: str,
        attachment_path: str,
        attachment_name: str | None = None,
    ) -> bool:
        # Falls du hier Anhänge brauchst, greift derselbe saubere Token
        API_TOKEN = os.getenv('MAILTRAP_API_TOKEN')
        if not API_TOKEN:
            return False

        url = "https://send.api.mailtrap.io/api/send"
        headers = {
            "Authorization": f"Bearer {API_TOKEN}", 
            "Content-Type": "application/json"
        }

        attachment_data = ""
        if attachment_path and os.path.exists(attachment_path):
            import base64
            with open(attachment_path, "rb") as f:
                attachment_data = base64.b64encode(f.read()).decode('utf-8')

        payload = {
            "from": {"email": "info@mm-community.online", "name": "M&M Community"},
            "to": [{"email": to_email.strip()}],
            "subject": subject,
            "text": body,
        }

        if attachment_data:
            payload["attachments"] = [{
                "content": attachment_data,
                "filename": attachment_name or os.path.basename(attachment_path),
                "type": "application/pdf",
                "disposition": "attachment"
            }]

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            return response.status_code in [200, 201, 202]
        except Exception:
            return False

mail_service = MailService()

def send_verification_email(user_email: str, code: str) -> bool:
    return mail_service.send_verification_email(user_email, code)

def send_email_with_attachment(to_email: str, subject: str, body: str, attachment_path: str, attachment_name: str | None = None) -> bool:
    return mail_service.send_email_with_attachment(to_email, subject, body, attachment_path, attachment_name)