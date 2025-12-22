import json
import re

def clean_songs():
    filename = "songs.json"
    
    try:
        with open(filename, "r", encoding="utf-8") as f:
            songs = json.load(f)
        
        cleaned_count = 0
        
        # To wyrażenie regularne szuka <br>, <br/>, <br  >, <br><br> itd.
        # Usuwa też "---" oraz nadmiarowe spacje na końcach
        pattern = re.compile(r'(<br\s*/?>\s*)+|---', re.IGNORECASE)

        for song in songs:
            for line in song.get("lyrics", []):
                original_text = line["text"]
                
                # Usuwamy znaczniki i czyścimy końcówki tekstu
                new_text = pattern.sub('', original_text).strip()
                
                if original_text != new_text:
                    line["text"] = new_text
                    cleaned_count += 1
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(songs, f, ensure_ascii=False, indent=2)
            
        print(f"Sukces! Oczyszczono {cleaned_count} wystąpień błędnych znaków.")
        
    except Exception as e:
        print(f"Błąd podczas czyszczenia: {e}")

if __name__ == "__main__":
    clean_songs()