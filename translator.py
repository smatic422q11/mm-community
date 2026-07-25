import os
import deepl
from config import DEEPL_KEY

def batch_translate():
    translator = deepl.Translator(DEEPL_KEY)
    
    # Wir suchen alle .txt Dateien, die wir übersetzen wollen
    for filename in os.listdir("."):
        if filename.endswith(".txt") and "translator" not in filename:
            print(f"[+] Verarbeite: {filename}...")
            
            with open(filename, 'r', encoding='utf-8') as f:
                text = f.read()
            
            if text.strip(): # Nur übersetzen, wenn Text drin ist
                result = translator.translate_text(text, target_lang="DE")
                
                # Speichern als übersetzte Datei
                new_filename = filename.replace(".txt", "_DE.txt")
                with open(new_filename, 'w', encoding='utf-8') as f:
                    f.write(result.text)
                print(f"[+] Fertig: {new_filename} gespeichert.")

if __name__ == "__main__":
    batch_translate()
