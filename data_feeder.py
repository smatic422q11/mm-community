import os
import subprocess

def feed_and_translate(filename, content):
    # 1. Daten einspeisen
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content + "\n")
        print(f"[+] Daten erfolgreich in {filename} geschrieben.")
        
        # 2. Automatische Übersetzung anstoßen
        print("[+] Starte Übersetzungsprozess...")
        subprocess.run(["C:\\Python314\\python.exe", "translator.py"], check=True)
        print("[+] Gesamter Prozess abgeschlossen.")
        
    except Exception as e:
        print(f"[!] Fehler: {e}")

if __name__ == "__main__":
    # Hier gibst du deinen neuen Content ein
    neuer_forensik_text = "FORENSIK-UPDATE: Intuition-Scan der KI-Zellen abgeschlossen. Integrität liegt bei 98%."
    
    # Ausführen
    feed_and_translate("dr_spirituelle_forensik.txt", neuer_forensik_text)