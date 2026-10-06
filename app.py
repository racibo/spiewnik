import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
import requests
import base64

# ─────────────────────────────────────────────
#  POŁĄCZENIE Z GOOGLE SHEETS
# ─────────────────────────────────────────────

def init_gsheet():
    try:
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )
            client = gspread.authorize(creds)
            return client.open_by_key("1RG82ZtUZfNsOjXI7xHKDnwbnDUl2SwE5oDLMNJNYdkw").worksheet("Songs")
        else:
            st.error("Brak konfiguracji 'gcp_service_account' w secrets.toml")
            return None
    except Exception as e:
        st.error(f"Błąd połączenia z Google Sheets: {e}")
        return None

ws = init_gsheet()

# ─────────────────────────────────────────────
#  GITHUB API
# ─────────────────────────────────────────────

def push_json_to_github(json_content_str):
    GITHUB_TOKEN = st.secrets.get("github_token", "")
    GITHUB_REPO = st.secrets.get("github_repo", "")
    GITHUB_FILE_PATH = "songs.json"

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        res = requests.get(url, headers=headers, timeout=20)
    except Exception as e:
        return False, f"GET GitHub nie powiódł się: {e}"

    if res.status_code != 200:
        return False, f"GitHub GET {res.status_code}: {res.text}"

    sha = res.json().get("sha")
    if not sha:
        return False, f"GitHub nie zwrócił SHA pliku songs.json: {res.text}"

    content_b64 = base64.b64encode(json_content_str.encode('utf-8')).decode('utf-8')
    payload = {
        "message": "Aktualizacja bazy utworów via Streamlit",
        "content": content_b64,
        "sha": sha
    }

    try:
        put_res = requests.put(url, headers=headers, json=payload, timeout=20)
    except Exception as e:
        return False, f"PUT GitHub nie powiódł się: {e}"

    if put_res.status_code in [200, 201]:
        return True, put_res.text

    return False, f"GitHub PUT {put_res.status_code}: {put_res.text}"

# ─────────────────────────────────────────────
#  ŁADOWANIE / ZAPIS
# ─────────────────────────────────────────────

def parse_chords(chords):
    """Normalizuje akordy, zachowując odstępy wewnątrz nowego zapisu.

    Nowy zapis może być przechowywany jako jeden string, np.
    'A       G   D'. Odstępy są wtedy informacją o położeniu akordów
    w trybie „akordy nad tekstem”.

    Stary zapis tablicowy, np. ['A', '|', 'G'], pozostaje obsługiwany
    bez zmian.
    """
    if chords is None:
        return []

    if isinstance(chords, list):
        result = []
        for item in chords:
            if item is None:
                continue
            value = str(item).strip()
            if value:
                result.append(value)
        return result

    value = str(chords).strip()
    return [value] if value else []


def parse_lyrics_line(line):
    """Rozdziela tekst od akordów tylko przy pierwszym |.

    Wszystkie kolejne | należą już do zapisu akordów i muszą zostać
    zachowane, np.:
        Tekst | A |G
    """
    if "|" not in line:
        return {"text": line.strip(), "chords": []}

    text, chord_text = line.split("|", 1)
    return {
        "text": text.strip(),
        "chords": parse_chords(chord_text),
    }


def load_songs():
    if not ws:
        return []
    try:
        rows = ws.get_all_values()
        if not rows or len(rows) < 2:
            return []
        songs = []
        for i, row in enumerate(rows[1:], start=2):
            if len(row) >= 2 and row[0].strip():
                title = row[0].strip()
                lyrics_raw = row[1].strip() if len(row) > 1 else ""
                tags_raw = row[4].strip() if len(row) > 4 else ""
                lyrics = []

                if lyrics_raw.startswith("["):
                    try:
                        for item in json.loads(lyrics_raw):
                            if isinstance(item, dict):
                                lyrics.append({
                                    "text": item.get("text", "").strip(),
                                    "chords": parse_chords(item.get("chords", [])),
                                })
                    except Exception:
                        lyrics.append({"text": lyrics_raw, "chords": []})
                else:
                    for line in lyrics_raw.split("\n"):
                        lyrics.append(parse_lyrics_line(line))

                songs.append({
                    "title": title,
                    "lyrics": lyrics,
                    "tags": [t.strip() for t in tags_raw.split(",") if t.strip()],
                    "row": i,
                })
        return songs
    except Exception as e:
        st.error(f"Błąd ładowania: {e}")
        return []


def lyrics_to_text(lyrics):
    lines = []
    for line in lyrics:
        text = line.get("text", "")
        chords = " ".join(parse_chords(line.get("chords", [])))
        if chords:
            lines.append(f"{text} | {chords}")
        else:
            lines.append(text)
    return "\n".join(lines)


def text_to_lyrics(text):
    return [parse_lyrics_line(line) for line in text.split("\n")]


def add_song(title, lyrics_text, tags_text=""):
    if not ws:
        return False
    try:
        lyrics_str = lyrics_text
        tags = [t.strip() for t in tags_text.split(",") if t.strip()]
        ws.append_row([title, lyrics_str, "0", "0", ", ".join(tags)])
        return True
    except Exception as e:
        st.error(f"Błąd dodawania: {e}")
        return False


def save_song(row_idx, title, lyrics_text, tags_text):
    if not ws:
        return False
    try:
        tags = [t.strip() for t in tags_text.split(",") if t.strip()]
        existing = ws.row_values(row_idx)
        ratings_sum = existing[2] if len(existing) > 2 else "0"
        ratings_count = existing[3] if len(existing) > 3 else "0"
        ws.update([[title, lyrics_text, ratings_sum, ratings_count, ", ".join(tags)]], f"A{row_idx}:E{row_idx}", raw=False)
        return True
    except Exception as e:
        st.error(f"Błąd zapisu: {e}")
        return False



def build_song(title, lyrics_text, tags_text, row_idx):
    """Buduje rekord w tym samym formacie co load_songs()."""
    tags = [t.strip() for t in tags_text.split(",") if t.strip()]
    return {
        "title": title.strip(),
        "lyrics": text_to_lyrics(lyrics_text),
        "tags": tags,
        "row": row_idx,
    }



def publish_songs(songs):
    """Publikuje dokładnie listę songs przekazaną przez wywołującego."""
    clean = []
    for song in songs:
        item = dict(song)
        item.pop("row", None)
        clean.append(item)
    json_str = json.dumps(clean, ensure_ascii=False, indent=2)
    return push_json_to_github(json_str)


def publish_current_songs():
    """Publikuje świeżo odczytane dane z Google Sheets."""
    fresh_songs = load_songs()
    if not fresh_songs:
        return False, "Nie udało się odczytać piosenek z Google Sheets."
    return publish_songs(fresh_songs)


def save_and_publish_from_sheets():
    """Po zapisie zawsze pobiera aktualny stan Sheets i publikuje właśnie jego."""
    fresh_songs = load_songs()
    if not fresh_songs:
        return False, "Nie udało się ponownie odczytać danych z Google Sheets."
    return fresh_songs, publish_songs(fresh_songs)

def delete_song(row_idx):
    if not ws:
        return False
    try:
        ws.delete_rows(row_idx)
        return True
    except Exception as e:
        st.error(f"Błąd usuwania: {e}")
        return False

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────

st.set_page_config(page_title="Śpiewnik — Warsztat", page_icon="🎵", layout="wide")
ADMIN_PIN = "1234"

st.title("🎵 Warsztat piosenek")

st.info(
    """**Instrukcja**

Najpierw wybierz piosenkę do edycji lub kliknij **Dodaj piosenkę**.

Następnie edytuj zachowując następujące zasady:
- Po każdym wersie wstawiaj znak **|** (przycisk nad klawiszem ENTER) i to, co umieścisz za tym znakiem, jest odczytywane jako akord.
- Odstępy pomiędzy kolejnymi akordami możesz wykorzystać do ustawienia ich pozycji nad tekstem — np. **A       G   D** zachowa te odstępy w trybie **„akordy nad tekstem”**.
- W trybie **„akordy obok tekstu”** te duże odstępy zostaną automatycznie zmniejszone.
- Stary sposób z ponownym wpisaniem znaku **|** nadal działa i zwiększa odstęp między akordami w trybie **„akordy nad tekstem”**.
- Naciśnięcie **ENTER** rozpoczyna nowy wers. Zawijanie tekstu na ekranie nie tworzy nowego wersu."""
)

# ─────────────────────────────────────────────
#  ŁADOWANIE
# ─────────────────────────────────────────────

if "songs" not in st.session_state:
    st.session_state.songs = load_songs()
if "edit_idx" not in st.session_state:
    st.session_state.edit_idx = 0

songs = st.session_state.songs

def select_song(idx):
    st.session_state.edit_idx = idx
    for k in ["edit_title", "edit_lyrics", "edit_tags", "del_pin"]:
        st.session_state.pop(k, None)

# ─────────────────────────────────────────────
#  SIDEBAR — lista + szukaj
# ─────────────────────────────────────────────

with st.sidebar:
    st.header(f"Lista ({len(songs)})")

    query = st.text_input("Szukaj:", placeholder="Tytuł...", key="search")
    if query:
        filtered = [(i, s) for i, s in enumerate(songs) if query.lower() in s["title"].lower()]
    else:
        filtered = [(i, s) for i, s in enumerate(songs)]

    for i, s in filtered:
        tags_str = ", ".join(s.get("tags", [])) if s.get("tags") else ""
        label = f"{s['title']}" + (f" [{tags_str}]" if tags_str else "")
        if st.button(label, key=f"pick_{i}", use_container_width=True):
            select_song(i)
            st.rerun()

# ─────────────────────────────────────────────
#  GŁÓWNY PANEL
# ─────────────────────────────────────────────

tab_add, tab_edit, tab_del = st.tabs(["➕ Dodaj", "✏️ Edytuj", "🗑️ Usuń"])

# ── DODAJ ──
with tab_add:
    st.subheader("Nowa piosenka")
    new_title = st.text_input("Tytuł:", key="add_title")
    new_lyrics = st.text_area(
        "Tekst (format: tekst | chwyty):",
        placeholder="Zwrotka 1\nRefren\n\nTekst | C F G C",
        height=300, key="add_lyrics"
    )
    new_tags = st.text_input("Tagi (przecinki):", key="add_tags", placeholder="np. ognisko, klasyk")

    if st.button("➕ Dodaj piosenkę", type="primary", use_container_width=True):
        if new_title.strip() and new_lyrics.strip():
            if add_song(new_title.strip(), new_lyrics, new_tags):
                # Google Sheets jest źródłem prawdy.
                fresh_songs, result = save_and_publish_from_sheets()
                ok, resp = result
                if ok:
                    st.session_state.songs = fresh_songs
                    st.success(f"Dodano i opublikowano: {new_title}")
                    st.rerun()
                else:
                    st.error(f"⚠️ Piosenkę zapisano w Google Sheets, ale publikacja na GitHub nie powiodła się.\n\n{resp}")
        else:
            st.error("Podaj tytuł i tekst!")

# ── EDYTUJ ──
with tab_edit:
    st.subheader("Edytuj piosenkę")

    if songs:
        idx = st.session_state.edit_idx
        if idx < 0 or idx >= len(songs):
            idx = 0
            st.session_state.edit_idx = idx
        song = songs[idx]

        st.caption(f"Edytujesz: **{song['title']}**")

        edit_title = st.text_input("Tytuł:", value=song["title"], key=f"edit_title_{idx}")
        edit_lyrics = st.text_area(
            "Tekst (format: tekst | chwyty):",
            value=lyrics_to_text(song["lyrics"]),
            height=300, key=f"edit_lyrics_{idx}"
        )
        edit_tags = st.text_input("Tagi (przecinki):", value=", ".join(song.get("tags", [])), key=f"edit_tags_{idx}")

        if st.button("💾 Zapisz zmiany", type="primary", use_container_width=True):
            if save_song(song["row"], edit_title, edit_lyrics, edit_tags):
                # Po zapisie ponownie czytamy cały arkusz. Dzięki temu
                # songs.json zawsze odpowiada rzeczywistemu stanowi Sheets.
                fresh_songs, result = save_and_publish_from_sheets()
                ok, resp = result
                if ok:
                    st.session_state.songs = fresh_songs
                    # Po publikacji wyszukujemy edytowany utwór w świeżej bazie.
                    for new_idx, fresh_song in enumerate(fresh_songs):
                        if fresh_song["row"] == song["row"]:
                            st.session_state.edit_idx = new_idx
                            break
                    st.success("Zapisano w Google Sheets i opublikowano na GitHub!")
                    st.rerun()
                else:
                    st.error(f"⚠️ Zmiany zapisano w Google Sheets, ale publikacja na GitHub nie powiodła się.\n\n{resp}")
    else:
        st.info("Brak piosenek w bazie.")

# ── USUŃ ──
with tab_del:
    st.subheader("Usuń piosenkę")

    pin = st.text_input("PIN:", type="password", key="del_pin")
    if pin == ADMIN_PIN:
        if songs:
            idx = st.session_state.edit_idx
            if idx < 0 or idx >= len(songs):
                idx = 0
            song_to_del = songs[idx]

            st.warning(f"⚠️ Usunąć **{song_to_del['title']}**?")
            if st.button("🗑️ POTWIERDZAM USUNIĘCIE", type="primary", use_container_width=True):
                if delete_song(song_to_del["row"]):
                    st.success("Usunięto!")
                    st.session_state.songs = load_songs()
                    select_song(0)
                    st.rerun()
        else:
            st.info("Brak piosenek.")
    elif pin:
        st.error("Błędny PIN!")

# Publikacja jest automatyczna po dodaniu lub zapisaniu zmian.
