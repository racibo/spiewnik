import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
import random
import re
from collections import Counter
import urllib.parse

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
#  LOGIKA BIZNESOWA
# ─────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def load_songs_cached():
    """Ładuje piosenki z cache'em 2 minuty — szybkie przełączanie bez callów API."""
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
                ratings_sum = int(row[2]) if len(row) > 2 and row[2].isdigit() else 0
                ratings_count = int(row[3]) if len(row) > 3 and row[3].isdigit() else 0
                tags_raw = row[4].strip() if len(row) > 4 else ""
                lyrics = []
                if lyrics_raw.startswith("["):
                    try:
                        for item in json.loads(lyrics_raw):
                            if isinstance(item, dict):
                                chords = item.get("chords", [])
                                if isinstance(chords, str):
                                    chords = chords.split()
                                lyrics.append({"text": item.get("text", "").strip(), "chords": chords})
                    except Exception:
                        lyrics.append({"text": lyrics_raw, "chords": []})
                else:
                    for line in lyrics_raw.split("\n"):
                        if "|" in line:
                            parts = line.split("|", 1)
                            lyrics.append({"text": parts[0].strip(), "chords": parts[1].strip().split() if parts[1].strip() else []})
                        else:
                            lyrics.append({"text": line.strip(), "chords": []})
                songs.append({
                    "title": title,
                    "lyrics": lyrics,
                    "ratings_sum": ratings_sum,
                    "ratings_count": ratings_count,
                    "tags": [t.strip() for t in tags_raw.split(",") if t.strip()],
                    "row": i,
                })
        return songs
    except Exception as e:
        st.error(f"Błąd podczas ładowania piosenek: {e}")
        return []

def reload_songs():
    """Czyści cache i przeładowuje piosenki, ZACHOWUJĄC bieżącą playlistę/filtr."""
    load_songs_cached.clear()
    st.session_state.songs = load_songs_cached()
    # Inicjalizacja tylko jeśli playlista nie istnieje, żeby nie niszczyć bieżącego kontekstu tagów
    if "playlist" not in st.session_state:
        st.session_state.playlist = list(range(len(st.session_state.songs)))
        st.session_state.playlist_name = "Wszystkie"

def save_song_to_sheets(row_idx, title, lyrics, ratings_sum, ratings_count, tags):
    if not ws:
        return False
    try:
        lyrics_str = "\n".join([f"{l['text']} | {' '.join(l.get('chords', []))}" for l in lyrics])
        ws.update([[title, lyrics_str, str(ratings_sum), str(ratings_count), ", ".join(tags)]], f"A{row_idx}:E{row_idx}", raw=False)
        return True
    except Exception as e:
        st.error(f"Błąd podczas zapisywania: {e}")
        return False

def add_song_to_sheets(title, lyrics, ratings_sum=0, ratings_count=0, tags=None):
    if tags is None:
        tags = []
    if not ws:
        return False
    try:
        lyrics_str = "\n".join([f"{l['text']} | {' '.join(l.get('chords', []))}" for l in lyrics])
        ws.append_row([title, lyrics_str, str(ratings_sum), str(ratings_count), ", ".join(tags)])
        return True
    except Exception as e:
        st.error(f"Błąd podczas dodawania piosenki: {e}")
        return False

def delete_song_from_sheets(row_idx):
    if not ws:
        return False
    try:
        ws.delete_rows(row_idx)
        return True
    except Exception as e:
        st.error(f"Błąd podczas usuwania: {e}")
        return False

def update_song_tags(row_idx, tags):
    if not ws:
        return False
    try:
        ws.update([[", ".join(tags)]], f"E{row_idx}")
        return True
    except Exception as e:
        st.error(f"Błąd podczas aktualizacji tagów: {e}")
        return False

def update_song_ratings(row_idx, ratings_sum, ratings_count):
    if not ws:
        return False
    try:
        ws.update([[str(ratings_sum), str(ratings_count)]], f"C{row_idx}")
        return True
    except Exception as e:
        st.error(f"Błąd podczas aktualizacji ocen: {e}")
        return False

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────

st.set_page_config(layout="wide", page_title="Śpiewnik", initial_sidebar_state="expanded")

ADMIN_PIN = "1234"

RATING_TAGS = {
    1: ["Nie lubię", "Nie graj", "Żenada", "Pomiń", "Trudne", "Słabe", "Nudne"],
    2: ["Później", "Kiedyś", "Nie teraz", "Ćwiczyć", "Średnie", "Zapomnij"],
    3: ["Zagraj", "OK", "Niezła", "Ognisko", "Spokojna", "Klasyk", "Może być"],
    4: ["Następne", "Ładna", "Polecam", "Częściej", "Wpadająca", "Energia", "Na start"],
    5: ["HIT", "Koniecznie", "Ulubiona", "TOP", "Mistrz", "Hymn", "Wszyscy", "Legenda"],
}

STOPWORDS = {"się","i","w","z","na","do","że","o","a","to","jak","nie","co","mnie","mi","ci","za","ale","bo","jest","tylko","przez","jeszcze","kiedy","już","dla","od","ten","ta"}

# ─────────────────────────────────────────────
#  CSS
# ─────────────────────────────────────────────

st.markdown("""
<style>
    .song-title {
        font-weight: bold;
        color: var(--text-color);
        text-align: center;
        line-height: 1.1;
        font-size: 28px !important;
        margin-bottom: 6px !important;
        margin-top: 6px;
    }

    /* Klikalne tagi nad piosenką - jako hiperłącza */
    .song-tags-header {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 6px;
        margin-bottom: 10px;
        flex-wrap: wrap;
    }
    a.song-tag-badge {
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(255,75,75,0.4);
        color: #ff4b4b;
        padding: 3px 10px;
        border-radius: 16px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        text-decoration: none;
        transition: background 0.15s;
    }
    a.song-tag-badge:hover { 
        background-color: rgba(255,75,75,0.15); 
        color: #ff4b4b;
        text-decoration: none;
    }

    /* Wiersz tekstu + chwytów */
    .song-row {
        display: flex;
        justify-content: flex-start;
        align-items: baseline;
        gap: 20px;
        margin-bottom: 0px !important;
        page-break-inside: avoid;
    }
    .lyrics-col {
        flex: 0 0 auto;
        min-width: 150px;
        font-size: 16px;
        color: var(--text-color);
    }
    .chords-col {
        color: #ff4b4b !important;
        font-weight: bold;
        font-size: 16px;
    }

    /* Przyciski nawigacji */
    div.stButton > button { border-radius: 8px; transition: all 0.2s; }

    .nav-btn div.stButton > button {
        padding: 0.5rem 0.2rem !important;
        font-size: 14px !important;
        height: auto !important;
    }
    .list-btn div.stButton > button {
        text-align: left !important;
        justify-content: flex-start !important;
        border: 1px solid var(--secondary-background-color) !important;
    }
    .tag-btn div.stButton > button {
        padding: 2px 8px !important;
        font-size: 12px !important;
        min-height: 0px !important;
        height: 28px !important;
        background-color: var(--secondary-background-color);
        border: 1px solid var(--secondary-background-color);
        color: var(--text-color);
    }
    [data-testid="stSidebar"] div.stButton > button {
        font-size: 11px !important;
        padding: 2px 8px !important;
    }

    hr { margin: 8px 0 !important; }

    /* Tryb pełnoekranowy (obsługa z sesji) */
    .fullscreen-active [data-testid="stSidebar"],
    .fullscreen-active [data-testid="stHeader"],
    .fullscreen-active .controls-section {
        display: none !important;
    }
    .fullscreen-active .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
    }

</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  HELPERS & NAWIGACJA Z PLAYLISTĄ
# ─────────────────────────────────────────────

def get_keywords(songs_list, source="lyrics", limit=40):
    all_words = []
    for s in songs_list:
        text = (" ".join([l["text"] for l in s["lyrics"]]) if source == "lyrics" else s["title"]).lower()
        all_words.extend([w for w in re.findall(r'\b\w{4,}\b', text) if w not in STOPWORDS])
    return Counter(all_words).most_common(limit)

def get_most_common_tags(songs, limit=10):
    c = Counter(t for s in songs for t in s.get("tags", []))
    return [t[0] for t in c.most_common(limit)]

def get_most_visited_songs(songs, limit=10):
    return sorted([s for s in songs if s["ratings_count"] > 0], key=lambda x: x["ratings_count"], reverse=True)[:limit]

def get_recommended_songs_rotational(songs, limit=5):
    if not songs:
        return []
    neg = set(RATING_TAGS.get(1, []))
    rated_safe = [s for s in songs if s["ratings_count"] > 0 and not any(t in neg for t in s.get("tags", []))]
    unexplored = [s for s in songs if s["ratings_count"] == 0 and not s.get("tags")]
    selection = []
    selection.extend(random.sample(rated_safe, min(2, len(rated_safe))))
    selection.extend(random.sample(unexplored, min(2, len(unexplored))))
    needed = max(0, (limit - 1) - len(selection))
    remaining = [s for s in songs if s not in selection]
    selection.extend(random.sample(remaining, min(needed, len(remaining))))
    if songs:
        selection.append(random.choice(songs))
    random.shuffle(selection)
    return selection[:limit]

def set_song_by_idx(idx, keep_playlist=False):
    if st.session_state.songs:
        st.session_state.current_idx = idx % len(st.session_state.songs)
        st.session_state.transposition = 0
        if not keep_playlist:
            st.session_state.playlist = list(range(len(st.session_state.songs)))
            st.session_state.playlist_name = "Wszystkie"

def go_next_song():
    pl = st.session_state.playlist
    curr = st.session_state.current_idx
    try:
        pl_idx = pl.index(curr)
        next_idx = pl[(pl_idx + 1) % len(pl)]
    except ValueError:
        next_idx = pl[0] if pl else 0
    set_song_by_idx(next_idx, keep_playlist=True)

def go_prev_song():
    pl = st.session_state.playlist
    curr = st.session_state.current_idx
    try:
        pl_idx = pl.index(curr)
        prev_idx = pl[(pl_idx - 1) % len(pl)]
    except ValueError:
        prev_idx = pl[-1] if pl else 0
    set_song_by_idx(prev_idx, keep_playlist=True)

def go_rand_song():
    pl = st.session_state.playlist
    if pl:
        set_song_by_idx(random.choice(pl), keep_playlist=True)

# ─────────────────────────────────────────────
#  RENDEROWANIE TAGÓW / CHMURY
# ─────────────────────────────────────────────

def render_expandable_cloud(items, key_prefix, on_click_action, initial_count=8):
    state_key = f"expanded_{key_prefix}"
    if state_key not in st.session_state:
        st.session_state[state_key] = False
    is_expanded = st.session_state[state_key]
    visible = items if (is_expanded or len(items) <= initial_count) else items[:initial_count]
    needs_toggle = len(items) > initial_count

    cols = st.columns(3)
    for i, item in enumerate(visible):
        label = item if isinstance(item, str) else item[0]
        with cols[i % 3]:
            if st.button(label, key=f"{key_prefix}_{i}", use_container_width=True):
                on_click_action(label)

    if needs_toggle:
        next_i = len(visible)
        with cols[next_i % 3]:
            if st.button("🔼" if is_expanded else "🔽", key=f"toggle_{key_prefix}", use_container_width=True):
                st.session_state[state_key] = not st.session_state[state_key]
                st.rerun()

def render_compact_tags(items, key_prefix, on_click_action, limit=None):
    if not items:
        return
    visible = items[:limit] if limit else items
    st.markdown('<div class="tag-btn">', unsafe_allow_html=True)
    rows = [visible[i:i+4] for i in range(0, len(visible), 4)]
    for r_idx, row_items in enumerate(rows):
        cols = st.columns(4)
        for i, item in enumerate(row_items):
            label = item if isinstance(item, str) else item[0]
            with cols[i]:
                if st.button(label, key=f"{key_prefix}_{r_idx}_{i}", use_container_width=True):
                    on_click_action(label)
    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  TRANSPOZYCJA
# ─────────────────────────────────────────────

_NOTES_MAJ = ["C","Cis","D","Dis","E","F","Fis","G","Gis","A","B","H"]
_NOTES_MIN = ["c","cis","d","dis","e","f","fis","g","gis","a","b","h"]

def transpose_chord(chord, steps):
    if steps == 0:
        return chord
    m = re.match(r"^([A-H][is]*|[a-h][is]*)(.*)$", chord)
    if m:
        base, suffix = m.groups()
        if base in _NOTES_MAJ:
            return _NOTES_MAJ[(_NOTES_MAJ.index(base) + steps) % 12] + suffix
        if base in _NOTES_MIN:
            return _NOTES_MIN[(_NOTES_MIN.index(base) + steps) % 12] + suffix
    return chord

def build_song_html(song, transposition):
    lines = []
    lines.append(f'<div class="song-title">{song["title"]}</div>')

    # Tagi jako linki URL (np. ?tag=Ognisko), które Streamlit natywnie wykrywa
    if song.get("tags"):
        tags_html = '<div class="song-tags-header">'
        for tag in song["tags"]:
            safe_tag = urllib.parse.quote(tag)
            tags_html += f'<a href="?tag={safe_tag}" target="_self" class="song-tag-badge">{tag}</a>'
        tags_html += '</div>'
        lines.append(tags_html)

    lines.append('<hr style="margin: 5px 0 12px 0; opacity: 0.2;">')

    lines.append('<div class="song-container" id="song-container">')
    for l in song["lyrics"]:
        text = l["text"].strip()
        orig_chords = l.get("chords", [])
        transposed = [transpose_chord(c, transposition) for c in orig_chords]
        c_str = " ".join(transposed)
        if text or orig_chords:
            lines.append(
                f'<div class="song-row">'
                f'<div class="lyrics-col">{text or "&nbsp;"}</div>'
                f'<div class="chords-col">{c_str or "&nbsp;"}</div>'
                f'</div>'
            )
        else:
            lines.append('<div style="height: 10px;"></div>')
    lines.append('</div>')
    return "\n".join(lines)

# ─────────────────────────────────────────────
#  STATE
# ─────────────────────────────────────────────

if "songs" not in st.session_state:
    st.session_state.songs = load_songs_cached()

if "playlist" not in st.session_state:
    if st.session_state.songs:
        st.session_state.playlist = list(range(len(st.session_state.songs)))
    else:
        st.session_state.playlist = []
    st.session_state.playlist_name = "Wszystkie"

if "current_idx" not in st.session_state:
    st.session_state.current_idx = random.randint(0, max(0, len(st.session_state.songs) - 1)) if st.session_state.songs else 0

if "transposition" not in st.session_state:
    st.session_state.transposition = 0

if "fullscreen" not in st.session_state:
    st.session_state.fullscreen = False

if "kw_lyrics" not in st.session_state:
    st.session_state.kw_lyrics = get_keywords(st.session_state.songs, "lyrics")

if "kw_titles" not in st.session_state:
    st.session_state.kw_titles = get_keywords(st.session_state.songs, "title")

if "random_sample" not in st.session_state:
    st.session_state.random_sample = get_recommended_songs_rotational(st.session_state.songs, limit=5)

# Obsługa kliknięcia tagu (Streamlit wychwytuje parametry URL)
if "tag" in st.query_params:
    tag = st.query_params.get("tag")
    matches = [j for j, s in enumerate(st.session_state.songs) if tag in s.get("tags", [])]
    if matches:
        st.session_state.playlist = matches
        st.session_state.playlist_name = f"Tag: {tag}"
        set_song_by_idx(matches[0], keep_playlist=True)
    st.query_params.clear()
    st.rerun()

# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────

with st.sidebar:
    st.title("Biblioteka")

    # ── Wyszukiwarka ──
    query = st.text_input("Szukaj:", placeholder="Tytuł lub tekst...", key="main_search_input").lower()
    if query:
        found = [i for i, s in enumerate(st.session_state.songs)
                 if query in (s["title"] + " " + " ".join(l["text"] for l in s["lyrics"])).lower()]
        if found:
            for idx in found:
                if st.button(st.session_state.songs[idx]["title"], key=f"search_res_{idx}", use_container_width=True):
                    set_song_by_idx(idx)
                    st.rerun()

    st.markdown("---")

    # ── TAGI ──
    st.caption("🏷️ TAGI")
    all_tags_flat = [t for s in st.session_state.songs for t in s.get("tags", [])]
    if all_tags_flat:
        common_tags = [t for t, _ in Counter(all_tags_flat).most_common(50)]

        def _jump_to_tag(t):
            m = [j for j, s in enumerate(st.session_state.songs) if t in s.get("tags", [])]
            if m:
                st.session_state.playlist = m
                st.session_state.playlist_name = f"Tag: {t}"
                set_song_by_idx(m[0], keep_playlist=True)
            st.rerun()

        render_expandable_cloud(common_tags, "side_tags", _jump_to_tag, initial_count=9)
    else:
        st.caption("Brak tagów.")

    st.markdown("---")
    st.caption("Z TEKSTU")
    if st.session_state.kw_lyrics:
        def _jump_to_lyrics_kw(w):
            m = [j for j, s in enumerate(st.session_state.songs) if w in " ".join(l["text"] for l in s["lyrics"]).lower()]
            if m: set_song_by_idx(random.choice(m))
            st.rerun()
        render_expandable_cloud([w for w, _ in st.session_state.kw_lyrics], "side_l", _jump_to_lyrics_kw, initial_count=9)

    st.markdown("---")
    st.caption("Z TYTUŁÓW")
    if st.session_state.kw_titles:
        def _jump_to_title_kw(w):
            m = [j for j, s in enumerate(st.session_state.songs) if w in s["title"].lower()]
            if m: set_song_by_idx(random.choice(m))
            st.rerun()
        render_expandable_cloud([w for w, _ in st.session_state.kw_titles], "side_t", _jump_to_title_kw, initial_count=6)

    st.markdown("---")
    if st.button("🔄 Odśwież bazę", key="refresh_sidebar", use_container_width=True):
        reload_songs()
        st.session_state.kw_lyrics = get_keywords(st.session_state.songs, "lyrics")
        st.session_state.kw_titles = get_keywords(st.session_state.songs, "title")
        st.rerun()

# ─────────────────────────────────────────────
#  GUARD
# ─────────────────────────────────────────────

if not st.session_state.songs:
    st.warning("Baza piosenek jest pusta lub brak połączenia.")
    st.stop()

song = st.session_state.songs[st.session_state.current_idx]

# ─────────────────────────────────────────────
#  TRYB PEŁNOEKRANOWY - ZAMKNIĘCIE (GÓRA)
# ─────────────────────────────────────────────
if st.session_state.fullscreen:
    st.markdown('<div class="fullscreen-active"></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    if c2.button("✕ Zamknij tryb gry", use_container_width=True, type="primary", key="exit_fs_top"):
        st.session_state.fullscreen = False
        st.rerun()
    st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  INFORMACJA O FILTRZE (PLAYLIŚCIE)
# ─────────────────────────────────────────────
if st.session_state.playlist_name != "Wszystkie":
    pl_len = len(st.session_state.playlist)
    try:
        pos = st.session_state.playlist.index(st.session_state.current_idx) + 1
    except:
        pos = 1
    
    col_inf1, col_inf2 = st.columns([4, 1])
    col_inf1.info(f"🎵 Aktywny filtr: **{st.session_state.playlist_name}** (Piosenka {pos} z {pl_len})")
    if col_inf2.button("✕ Wyczyść", use_container_width=True):
        st.session_state.playlist = list(range(len(st.session_state.songs)))
        st.session_state.playlist_name = "Wszystkie"
        st.rerun()

# ─────────────────────────────────────────────
#  PIOSENKA — widok główny
# ─────────────────────────────────────────────

song_html = build_song_html(song, st.session_state.transposition)
st.markdown(song_html, unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  PANEL STEROWANIA
# ─────────────────────────────────────────────

st.markdown('<div class="controls-section">', unsafe_allow_html=True)

with st.expander("🎛️ Sterowanie", expanded=False):

    # ── Nawigacja (działa w obrębie aktualnego filtra/tagu!) ──
    st.markdown('<div class="nav-btn">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("⬅️ Wstecz", key="nav_prev", use_container_width=True):
            go_prev_song()
            st.rerun()  # Wymagane, by ekran natychmiast odświeżył widok piosenki
    with c2:
        if st.button("➡️ Dalej", key="nav_next", use_container_width=True):
            go_next_song()
            st.rerun()  # Wymagane, by ekran natychmiast odświeżył widok piosenki
    with c3:
        if st.button("🎲 Losowa", key="nav_rand", use_container_width=True):
            go_rand_song()
            st.rerun()  # Wymagane, by ekran natychmiast odświeżył widok piosenki
    with c4:
        if st.button("⭐️ Ostatnia", key="nav_last", use_container_width=True):
            set_song_by_idx(st.session_state.playlist[-1], keep_playlist=True)
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<hr style="opacity: 0.15;">', unsafe_allow_html=True)

    # ── Transpozycja — natywna Streamlit (bezpośrednio modyfikuje stan) ──
    st.caption("Zmień tonację:")
    t_c1, t_c2, t_c3, t_c4 = st.columns([1, 1, 1, 1])
    with t_c1:
        if st.button("➖ W dół", key="tr_down", use_container_width=True):
            st.session_state.transposition -= 1
            st.rerun()
    with t_c2:
        st.markdown(f"<div style='text-align:center; padding-top:6px; font-weight:bold; font-size:18px;'>{st.session_state.transposition:+d}</div>", unsafe_allow_html=True)
    with t_c3:
        if st.button("➕ W górę", key="tr_up", use_container_width=True):
            st.session_state.transposition += 1
            st.rerun()
    with t_c4:
        if st.button("↺ Reset", key="tr_reset", use_container_width=True):
            st.session_state.transposition = 0
            st.rerun()

    st.markdown('<hr style="opacity: 0.15;">', unsafe_allow_html=True)

    # ── Ocena ──
    col_rate_info, col_rate_act = st.columns([1, 2])
    with col_rate_info:
        avg = song["ratings_sum"] / song["ratings_count"] if song["ratings_count"] > 0 else 0
        st.markdown(f"<div style='font-size:12px; opacity:0.7;'>Średnia: <b>{avg:.1f}</b><br>Głosów: {song['ratings_count']}</div>", unsafe_allow_html=True)
    with col_rate_act:
        score = st.feedback("stars", key="rating_feedback")
        if score is None:
            score_rad = st.radio("Oceń:", [1, 2, 3, 4, 5], horizontal=True, label_visibility="collapsed", key="rating_radio_backup")
            if st.button("Zapisz ocenę", key="save_rating_btn", use_container_width=True):
                new_sum = song["ratings_sum"] + score_rad
                new_count = song["ratings_count"] + 1
                update_song_ratings(song["row"], new_sum, new_count)
                st.success("Zapisano!")
                reload_songs()
                st.rerun()
        elif score is not None:
            r_val = score + 1
            if st.button(f"Wyślij ocenę {r_val}/5", key="send_stars", use_container_width=True):
                update_song_ratings(song["row"], song["ratings_sum"] + r_val, song["ratings_count"] + 1)
                st.toast("Ocena dodana!")
                reload_songs()
                st.rerun()

    st.markdown('<hr style="opacity: 0.15;">', unsafe_allow_html=True)

    # ── Tagi piosenki ──
    st.caption("Sugerowane tagi (kliknij by dodać):")
    score_for_tags = 3
    if "rating_radio_backup" in st.session_state:
        score_for_tags = st.session_state.rating_radio_backup
    if score_for_tags in RATING_TAGS:
        def _add_suggested_tag(t):
            if t not in song.get("tags", []):
                song["tags"].append(t)
                update_song_tags(song["row"], song["tags"])
                reload_songs()
                st.rerun()
        render_compact_tags(RATING_TAGS[score_for_tags], f"sug_{score_for_tags}", _add_suggested_tag)

    st.caption("Tagi tej piosenki (X = usuń):")
    current_tags = song.get("tags", [])
    if current_tags:
        st.markdown('<div class="tag-btn">', unsafe_allow_html=True)
        cols = st.columns(4)
        for i, tag in enumerate(current_tags):
            with cols[i % 4]:
                if st.button(f"✕ {tag}", key=f"del_tag_{i}", use_container_width=True):
                    song["tags"].remove(tag)
                    update_song_tags(song["row"], song["tags"])
                    reload_songs()
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    c_add_t1, c_add_t2 = st.columns([3, 1])
    with c_add_t1:
        new_tag_txt = st.text_input("Nowy tag", placeholder="Wpisz...", label_visibility="collapsed", key="new_tag_input")
    with c_add_t2:
        if st.button("➕", key="add_tag_plus", use_container_width=True):
            if new_tag_txt and new_tag_txt not in current_tags:
                song["tags"].append(new_tag_txt)
                update_song_tags(song["row"], song["tags"])
                reload_songs()
                # Czyszczenie pola input po udanym dodaniu tagu
                if "new_tag_input" in st.session_state:
                    del st.session_state["new_tag_input"]
                st.rerun()

    st.markdown('<hr style="opacity: 0.15;">', unsafe_allow_html=True)

    # ── Polecane ──
    st.subheader("📚 Polecane")
    tab_tags, tab_rand, tab_top = st.tabs(["🏷️ Wg Tagów", "🎲 Losowe", "🏆 Top"])

    with tab_tags:
        all_unique_tags = sorted(set(t for s in st.session_state.songs for t in s.get("tags", [])))
        selected_tag = st.selectbox("Wybierz tag:", [""] + all_unique_tags, key="tag_search_box")
        if selected_tag:
            tagged = [s for s in st.session_state.songs if selected_tag in s.get("tags", [])]
            st.caption(f"{len(tagged)} piosenek:")
            st.markdown('<div class="list-btn">', unsafe_allow_html=True)
            for i, ts in enumerate(tagged):
                if st.button(ts["title"], key=f"tag_search_res_{i}", use_container_width=True):
                    real_idx = next((j for j, s in enumerate(st.session_state.songs) if s["title"] == ts["title"]), 0)
                    set_song_by_idx(real_idx)
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    with tab_rand:
        if st.button("🔄 Losuj inne", key="reroll_recs", use_container_width=True):
            st.session_state.random_sample = get_recommended_songs_rotational(st.session_state.songs, limit=5)
            st.rerun()
        st.markdown('<div class="list-btn">', unsafe_allow_html=True)
        for i, rs in enumerate(st.session_state.random_sample):
            prefix = "⭐" if rs["ratings_count"] > 0 else "🆕"
            if st.button(f"{prefix} {rs['title']}", key=f"rec_r_{i}", use_container_width=True):
                set_song_by_idx(next((j for j, s in enumerate(st.session_state.songs) if s["title"] == rs["title"]), 0))
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_top:
        top_visited = get_most_visited_songs(st.session_state.songs, limit=5)
        st.markdown('<div class="list-btn">', unsafe_allow_html=True)
        for i, ts in enumerate(top_visited):
            if st.button(f"{i+1}. {ts['title']} ({ts['ratings_count']} głosów)", key=f"rec_t_{i}", use_container_width=True):
                set_song_by_idx(next((j for j, s in enumerate(st.session_state.songs) if s["title"] == ts["title"]), 0))
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Panel Administracyjny ──
    with st.expander("🛠️ Panel Administracyjny"):
        tab_edit, tab_add, tab_del, tab_stats = st.tabs(["✏️ Edytuj", "➕ Dodaj", "🗑️ Usuń", "📊 Statystyki"])

        with tab_edit:
            curr_id = st.session_state.current_idx
            et = st.text_input("Tytuł:", value=song["title"], key=f"edit_title_{curr_id}")
            el = [f"{l['text']} | {' '.join(l.get('chords', []))}" for l in song["lyrics"]]
            nc = st.text_area("Treść (Tekst | Chwyty):", value="\n".join(el), height=200, key=f"edit_area_{curr_id}")
            if st.button("Zapisz zmiany", key=f"btn_save_edit_{curr_id}", use_container_width=True):
                nl = []
                for line in nc.split("\n"):
                    p = line.split("|", 1)
                    if len(p) > 1:
                        nl.append({"text": p[0].strip(), "chords": p[1].strip().split() if p[1].strip() else []})
                    else:
                        nl.append({"text": line.strip(), "chords": []})
                if save_song_to_sheets(song["row"], et, nl, song["ratings_sum"], song["ratings_count"], song["tags"]):
                    st.success("Zmiany zapisane!")
                    reload_songs()
                    st.rerun()

        with tab_add:
            new_t = st.text_input("Tytuł piosenki:", key="add_new_title")
            new_l = st.text_area("Treść (Format: Tekst | Chwyty):",
                                 placeholder="Wpisz tekst piosenki...\nMożesz dodać chwyty po kresce |",
                                 height=200, key="add_new_area")
            if st.button("Dodaj do biblioteki", key="btn_add_new_song", use_container_width=True):
                if new_t and new_l:
                    parsed_lyrics = []
                    for line in new_l.split("\n"):
                        parts = line.split("|", 1)
                        if len(parts) > 1:
                            parsed_lyrics.append({"text": parts[0].strip(), "chords": parts[1].strip().split() if parts[1].strip() else []})
                        else:
                            parsed_lyrics.append({"text": line.strip(), "chords": []})
                    if add_song_to_sheets(new_t, parsed_lyrics):
                        st.success(f"Dodano: {new_t}")
                        reload_songs()
                        set_song_by_idx(len(st.session_state.songs) - 1)
                        st.rerun()
                else:
                    st.error("Podaj tytuł i treść!")

        with tab_del:
            pin_input = st.text_input("PIN blokady", type="password", key="del_pin")
            if pin_input == ADMIN_PIN:
                st.warning(f"⚠️ Zamierzasz usunąć: **{song['title']}**")
                if st.button("POTWIERDZAM USUNIĘCIE", type="primary", use_container_width=True):
                    if delete_song_from_sheets(song["row"]):
                        st.success("Piosenka usunięta!")
                        reload_songs()
                        set_song_by_idx(0)
                        st.rerun()
            elif pin_input:
                st.error("Błędny PIN!")

        with tab_stats:
            col1, col2, col3, col4 = st.columns(4)
            total_ratings = sum(s["ratings_count"] for s in st.session_state.songs)
            with col1:
                st.metric("📚 Piosenek", len(st.session_state.songs))
            with col2:
                st.metric("⭐ Ocenianych", len([s for s in st.session_state.songs if s["ratings_count"] > 0]))
            with col3:
                st.metric("🗳️ Ocen łącznie", total_ratings)
            with col4:
                avg_r = sum(s["ratings_sum"] for s in st.session_state.songs) / max(total_ratings, 1) if total_ratings else 0
                st.metric("⬇️ Średnia", f"{avg_r:.2f}")

            st.markdown("---")
            st.caption("🔥 Najczęściej odwiedzane:")
            for i, s in enumerate(get_most_visited_songs(st.session_state.songs, limit=10), 1):
                a = s["ratings_sum"] / s["ratings_count"] if s["ratings_count"] else 0
                st.write(f"{i}. **{s['title']}** — {s['ratings_count']} ocen (śr. {a:.1f})")

            st.markdown("---")
            st.caption("🏆 Najczęstsze tagi:")
            tag_counts = Counter(t for s in st.session_state.songs for t in s.get("tags", []))
            for i, (tag, count) in enumerate(tag_counts.most_common(20), 1):
                st.write(f"{i}. **{tag}** — {count}×")

st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  TRYB PEŁNOEKRANOWY (przycisk na dole)
# ─────────────────────────────────────────────
st.markdown("---")
c1, c2, c3 = st.columns([1,1,1])
with c2:
    if st.button("📖 Tryb gry (Pełny ekran)" if not st.session_state.fullscreen else "✕ Wyjdź z trybu gry", use_container_width=True, key="toggle_fs_bottom"):
        st.session_state.fullscreen = not st.session_state.fullscreen
        st.rerun()
