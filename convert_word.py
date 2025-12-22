from docx import Document
import json
import re

# Plik Word
doc = Document("spiewnik.docx")  # zmień na swoją nazwę

songs = []
current_song = None

# Polskie akordy
polish_chords = ["C","Cis","D","Dis","E","F","Fis","G","Gis","A","B","H",
                 "c","cis","d","dis","e","f","fis","g","gis","a","b","h"]

chord_pattern = re.compile(r"^(?:" + "|".join(polish_chords) + r")$")

for para in doc.paragraphs:
    text = para.text.strip()
    if not text:
        continue

    # Tytuł – Heading lub bold
    if para.style.name.startswith("Heading") or (para.runs and para.runs[0].bold):
        if current_song:
            songs.append(current_song)
        current_song = {"title": text, "lyrics": [], "tags": []}
        continue

    # Rozdziel wiersz na słowa i sprawdź akordy na końcu
    words = text.split()
    chords = []
    if words:
        while words and chord_pattern.match(words[-1]):
            chords.insert(0, words.pop(-1))
    text_clean = " ".join(words)

    if current_song:
        current_song["lyrics"].append({"text": text_clean, "chords": chords})

# Dodaj ostatnią pieśń
if current_song:
    songs.append(current_song)

# Zapis do JSON
with open("songs.json", "w", encoding="utf-8") as f:
    json.dump(songs, f, ensure_ascii=False, indent=2)

print(f"Zapisano {len(songs)} pieśni do songs.json")
