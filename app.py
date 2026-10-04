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

    sha = None
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        sha = res.json().get("sha")

    content_b64 = base64.b64encode(json_content_str.encode('utf-8')).decode('utf-8')
    payload = {
        "message": "Aktualizacja bazy utworów via Streamlit",
        "content": content_b64
    }
    if sha:
        payload["sha"] = sha

    put_res = requests.put(url, headers=headers, json=payload)
    return put_res.status_code in [200, 201], put_res.text

# ─────────────────────────────────────────────
#  ŁADOWANIE / ZAPIS
# ─────────────────────────────────────────────

def parse_chords(chords):
    """Normalizuje zapis akordów, zachowując dodatkowe znaczniki |.

    Przykłady:
      'A G'   -> ['A', 'G']
      'A |G'  -> ['A', '|G']
      'A | G' -> ['A', '|', 'G']

    Nie usuwamy kolejnych '|', ponieważ frontend używa ich
    do ustawiania dodatkowych odstępów w trybie „akordy nad”.
    """
    if chords is None:
        return []

    if isinstance(chords, list):
        result = []
        for item in chords:
            if item is None:
                continue
            result.extend(str(item).split())
        return result

    return str(chords).strip().split()


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



def publish_current_songs():
    """Generuje aktualny songs.json i publikuje go na GitHub."""
    load_songs_cache = load_songs()
    clean = []
    for s in load_songs_cache:
        sc = s.copy()
        sc.pop("row", None)
        clean.append(sc)
    json_str = json.dumps(clean, ensure_ascii=False, indent=2)
    return push_json_to_github(json_str)

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
- Po każdym wersie wstawiaj znak **|** (SHIFT plus ENTER) i to, co umieścisz za tym znakiem, jest odczytywane jako akord.
- Jeśli w tym samym wersie znowu powtórzysz ten znak, zwiększy się odstęp między akordami w trybie **„akordy nad tekstem”**."""
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

tab_add, tab_edit, tab_del, tab_pub = st.tabs(["➕ Dodaj", "✏️ Edytuj", "🗑️ Usuń", "🚀 Publikuj"])

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
                st.session_state.songs = load_songs()
                ok, resp = publish_current_songs()
                if ok:
                    st.success(f"Dodano i opublikowano: {new_title}")
                else:
                    st.warning(f"Dodano piosenkę, ale publikacja na GitHub nie powiodła się: {resp}")
                st.rerun()
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
                st.session_state.songs = load_songs()
                ok, resp = publish_current_songs()
                if ok:
                    st.success("Zapisano i opublikowano!")
                else:
                    st.warning(f"Zapisano zmiany, ale publikacja na GitHub nie powiodła się: {resp}")
                st.rerun()
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

# ── PUBLIKUJ ──
with tab_pub:
    st.subheader("Publikacja na stronie")

    if st.button("⚡ GENERUJ I PUBLIKUJ NA GITHUB", type="primary", use_container_width=True):
        with st.spinner("Pobieranie danych i wysyłanie..."):
            ok, resp = publish_current_songs()
            if ok:
                st.success("🎉 Opublikowano!")
            else:
                st.error(f"Błąd: {resp}")

    st.markdown("---")

    if st.button("📥 Pobierz songs.json", use_container_width=True):
        clean = []
        for s in songs:
            sc = s.copy()
            sc.pop("row", None)
            clean.append(sc)
        json_str = json.dumps(clean, ensure_ascii=False, indent=2)
        st.download_button(
            label="📥 Kliknij by pobrać",
            data=json_str,
            file_name="songs.json",
            mime="application/json",
        )
