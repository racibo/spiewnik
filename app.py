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
    """Publikuje songs.json do GitHub i weryfikuje zapis przez SHA blobu.

    Nie pobieramy ponownie całej zawartości pliku przez Contents API, ponieważ
    GitHub ma ograniczenia odpowiedzi dla dużych plików. Zamiast tego:
      1. pobieramy aktualny SHA pliku,
      2. zapisujemy nową treść,
      3. GitHub zwraca SHA nowego bloba,
      4. lokalnie obliczamy SHA Git bloba z dokładnie wysłanej treści,
      5. ponownie sprawdzamy SHA pliku na branchu.
    """
    GITHUB_TOKEN = st.secrets.get("github_token", "")
    GITHUB_REPO = st.secrets.get("github_repo", "")
    GITHUB_BRANCH = st.secrets.get("github_branch", "main")
    GITHUB_FILE_PATH = "songs.json"

    if not GITHUB_TOKEN:
        return False, "Brak github_token w Streamlit secrets."
    if not GITHUB_REPO:
        return False, "Brak github_repo w Streamlit secrets."

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        json.loads(json_content_str)
    except Exception as e:
        return False, f"Niepoprawny JSON przed publikacją: {e}"

    content_bytes = json_content_str.encode("utf-8")
    content_b64 = base64.b64encode(content_bytes).decode("ascii")

    # SHA używany przez Git dla blobu: SHA1("blob <długość>\\0<treść>").
    expected_blob_sha = hashlib.sha1(
        f"blob {len(content_bytes)}\\0".encode("ascii") + content_bytes
    ).hexdigest()

    for attempt in range(2):
        try:
            get_res = requests.get(
                url,
                headers=headers,
                params={"ref": GITHUB_BRANCH},
                timeout=20,
            )
        except Exception as e:
            return False, f"GET GitHub nie powiódł się: {e}"

        if get_res.status_code != 200:
            return False, f"GitHub GET {get_res.status_code}: {get_res.text}"

        current = get_res.json()
        current_blob_sha = current.get("sha")
        if not current_blob_sha:
            return False, f"GitHub nie zwrócił SHA pliku songs.json: {get_res.text}"

        payload = {
            "message": "Aktualizacja bazy utworów via Streamlit",
            "content": content_b64,
            "sha": current_blob_sha,
            "branch": GITHUB_BRANCH,
        }

        try:
            put_res = requests.put(
                url,
                headers=headers,
                json=payload,
                timeout=30,
            )
        except Exception as e:
            return False, f"PUT GitHub nie powiódł się: {e}"

        if put_res.status_code in (200, 201):
            put_data = put_res.json()
            commit_sha = put_data.get("commit", {}).get("sha", "")
            written_blob_sha = put_data.get("content", {}).get("sha", "")

            # Najważniejsza weryfikacja: SHA bloba zwrócone przez GitHub musi
            # być identyczne z SHA obliczonym z treści wysłanej przez Streamlit.
            if written_blob_sha != expected_blob_sha:
                return False, (
                    f"GitHub przyjął zapis (commit {commit_sha}), ale SHA "
                    f"zapisanego songs.json jest inne niż SHA wysłanych danych. "
                    f"oczekiwano {expected_blob_sha}, otrzymano {written_blob_sha or 'brak'}."
                )

            # Druga weryfikacja: branch main wskazuje teraz na ten sam blob.
            try:
                verify_res = requests.get(
                    url,
                    headers=headers,
                    params={"ref": GITHUB_BRANCH},
                    timeout=20,
                )
            except Exception as e:
                return False, (
                    f"GitHub przyjął zapis (commit {commit_sha}), ale "
                    f"weryfikacja branchu nie powiodła się: {e}"
                )

            if verify_res.status_code != 200:
                return False, (
                    f"GitHub przyjął zapis (commit {commit_sha}), ale "
                    f"weryfikacja branchu zwróciła HTTP {verify_res.status_code}: "
                    f"{verify_res.text}"
                )

            verified_blob_sha = verify_res.json().get("sha", "")
            if verified_blob_sha != expected_blob_sha:
                return False, (
                    f"GitHub przyjął zapis (commit {commit_sha}), ale branch "
                    f"{GITHUB_BRANCH} nie wskazuje na wysłaną wersję songs.json. "
                    f"oczekiwano {expected_blob_sha}, otrzymano {verified_blob_sha or 'brak'}."
                )

            return True, (
                f"Opublikowano i zweryfikowano na GitHub. "
                f"Branch: {GITHUB_BRANCH}; commit: {commit_sha or 'brak'}."
            )

        if put_res.status_code == 409 and attempt == 0:
            continue

        return False, f"GitHub PUT {put_res.status_code}: {put_res.text}"

    return False, "Publikacja nie powiodła się po ponowieniu próby."


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
        # Nowy format przechowuje cały układ akordów jako jeden element.
        # Zachowujemy wtedy również spacje na początku i końcu.
        if len(chords) == 1:
            value = "" if chords[0] is None else str(chords[0])
            return [value] if value.strip() else []

        # Stary format tablicowy: każdy element jest osobnym akordem.
        result = []
        for item in chords:
            if item is None:
                continue
            value = str(item).strip()
            if value:
                result.append(value)
        return result

    # Dla nowego zapisu spacje są częścią danych pozycyjnych.
    # Nie usuwamy ich, bo spacje po "|" oraz między akordami określają
    # położenie akordów w trybie "nad tekstem".
    value = str(chords)
    return [value] if value.strip() else []


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
        chord_parts = parse_chords(line.get("chords", []))
        if len(chord_parts) == 1:
            # Nowy zapis przechowuje cały układ akordów jako jeden string.
            # Zachowujemy dokładnie wszystkie spacje.
            chords = chord_parts[0]
        else:
            chords = " ".join(chord_parts)
        if chords.strip():
            lines.append(f"{text} |{chords}")
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
        return [], False, "Nie udało się ponownie odczytać danych z Google Sheets."
    ok, resp = publish_songs(fresh_songs)
    return fresh_songs, ok, resp

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
                fresh_songs, ok, resp = save_and_publish_from_sheets()
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
                fresh_songs, ok, resp = save_and_publish_from_sheets()
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
                    # Usunięcie również musi przejść przez ten sam pipeline:
                    # Google Sheets -> świeży odczyt -> songs.json -> weryfikacja GitHub.
                    fresh_songs, ok, resp = save_and_publish_from_sheets()
                    if ok:
                        st.session_state.songs = fresh_songs
                        select_song(0)
                        st.success(f"Usunięto „{song_to_del['title']}” i opublikowano zmianę na GitHub.")
                        st.rerun()
                    else:
                        st.error(
                            "⚠️ Piosenkę usunięto z Google Sheets, ale publikacja na GitHub nie powiodła się.\n\n"
                            + resp
                        )
        else:
            st.info("Brak piosenek.")
    elif pin:
        st.error("Błędny PIN!")

# Publikacja jest automatyczna po dodaniu lub zapisaniu zmian.
